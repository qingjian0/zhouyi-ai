"""Portable process-memory sampling and explicit logical memory-pool budgets.

This module measures process RSS where the operating system exposes it and
tracks application-declared pool usage. Logical pool counters are not a
substitute for RSS: both must be reported.

Run:
    python -m prototype.memory_budget --json
    python -m prototype.memory_budget --json --tracemalloc

The measurement context samples RSS periodically. Short-lived allocations
between samples may be missed; use an isolated subprocess and OS peak-RSS
facilities for strict release gates.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
import os
import sys
import threading
import time
from typing import Any


MIB = 1024 * 1024


class MemoryMeasurementUnavailable(RuntimeError):
    """Raised when the current process RSS cannot be sampled on this host."""


class MemoryBudgetExceeded(MemoryError):
    """Raised before a logical pool or aggregate budget would be exceeded."""


def _linux_memory() -> tuple[int, int] | None:
    try:
        values: dict[str, int] = {}
        with open("/proc/self/status", encoding="ascii") as stream:
            for line in stream:
                if line.startswith(("VmRSS:", "VmHWM:")):
                    key, raw, unit = line.split()[:3]
                    if unit != "kB":
                        continue
                    values[key.rstrip(":")] = int(raw) * 1024
        rss = values.get("VmRSS")
        peak = values.get("VmHWM", rss)
        if rss is not None:
            return rss, peak if peak is not None else rss
    except (OSError, ValueError):
        return None
    return None


def _windows_memory() -> tuple[int, int] | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        psapi = ctypes.WinDLL("Psapi.dll")
        kernel32 = ctypes.WinDLL("Kernel32.dll")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            wintypes.DWORD,
        )
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        ok = psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(),
            ctypes.byref(counters),
            counters.cb,
        )
        if not ok:
            return None
        return int(counters.WorkingSetSize), int(counters.PeakWorkingSetSize)
    except (AttributeError, OSError, TypeError):
        return None


def _psutil_memory() -> tuple[int, int | None] | None:
    try:
        import psutil  # Optional; the core module has no psutil dependency.

        info = psutil.Process(os.getpid()).memory_info()
        current = int(info.rss)
        peak_value = getattr(info, "peak_wset", None)
        peak = int(peak_value) if peak_value else None
        return current, max(current, peak) if peak is not None else None
    except (ImportError, OSError, AttributeError):
        return None


def _resource_peak_bytes() -> int | None:
    try:
        import resource

        raw = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # macOS reports bytes; Linux and the BSDs commonly report KiB.
        return raw if sys.platform == "darwin" else raw * 1024
    except (ImportError, AttributeError, OSError, ValueError):
        return None


@dataclass(frozen=True)
class ProcessMemorySample:
    timestamp_ns: int
    rss_bytes: int | None
    os_peak_rss_bytes: int | None
    source: str
    python_traced_current_bytes: int | None = None
    python_traced_peak_bytes: int | None = None

    @property
    def rss_mib(self) -> float | None:
        return None if self.rss_bytes is None else self.rss_bytes / MIB

    @property
    def os_peak_rss_mib(self) -> float | None:
        return (
            None
            if self.os_peak_rss_bytes is None
            else self.os_peak_rss_bytes / MIB
        )


def sample_process_memory(*, include_tracemalloc: bool = False) -> ProcessMemorySample:
    """Return current RSS and OS high-water RSS when available.

    Linux /proc and Windows PSAPI are preferred. psutil is an optional fallback.
    On platforms without a current-RSS provider, OS peak RSS may still be
    reported, but rss_bytes remains None rather than being guessed.
    """
    observed: tuple[int, int | None] | None = None
    source = "unavailable"

    if sys.platform.startswith("linux"):
        observed = _linux_memory()
        if observed is not None:
            source = "procfs"
    elif os.name == "nt":
        observed = _windows_memory()
        if observed is not None:
            source = "windows-psapi"

    if observed is None:
        observed = _psutil_memory()
        if observed is not None:
            source = "psutil"

    rss = observed[0] if observed is not None else None
    peak = observed[1] if observed is not None else None
    if peak is None:
        peak = _resource_peak_bytes()
    if peak is not None and rss is not None:
        peak = max(peak, rss)

    traced_current = traced_peak = None
    if include_tracemalloc:
        import tracemalloc

        if tracemalloc.is_tracing():
            traced_current, traced_peak = tracemalloc.get_traced_memory()

    return ProcessMemorySample(
        timestamp_ns=time.time_ns(),
        rss_bytes=rss,
        os_peak_rss_bytes=peak,
        source=source,
        python_traced_current_bytes=traced_current,
        python_traced_peak_bytes=traced_peak,
    )


@dataclass(frozen=True)
class ProcessMemoryReport:
    baseline_rss_bytes: int
    sampled_peak_rss_bytes: int
    final_rss_bytes: int
    peak_increment_bytes: int
    final_increment_bytes: int
    sample_count: int
    interval_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "baseline_rss_mib": self.baseline_rss_bytes / MIB,
            "sampled_peak_rss_mib": self.sampled_peak_rss_bytes / MIB,
            "final_rss_mib": self.final_rss_bytes / MIB,
            "peak_increment_mib": self.peak_increment_bytes / MIB,
            "final_increment_mib": self.final_increment_bytes / MIB,
        }


class ProcessMemoryMeasurement:
    """Sample process RSS during a bounded operation using a small poller.

    The polling thread itself contributes a small amount of runtime overhead.
    The report is a sampled peak, not a mathematically guaranteed peak.
    """

    def __init__(self, interval_seconds: float = 0.01) -> None:
        if (
            isinstance(interval_seconds, bool)
            or not isinstance(interval_seconds, (int, float))
            or not math.isfinite(interval_seconds)
            or interval_seconds <= 0
        ):
            raise ValueError("interval_seconds must be a finite positive number")
        self.interval_seconds = float(interval_seconds)
        self.baseline: ProcessMemorySample | None = None
        self.report: ProcessMemoryReport | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._peak = 0
        self._count = 0

    def _sample(self) -> None:
        sample = sample_process_memory()
        if sample.rss_bytes is None:
            return
        self._peak = max(self._peak, sample.rss_bytes)
        self._count += 1

    def _poll(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def __enter__(self) -> "ProcessMemoryMeasurement":
        self.baseline = sample_process_memory()
        if self.baseline.rss_bytes is None:
            raise MemoryMeasurementUnavailable(
                "current RSS is unavailable; install psutil or use Linux /proc "
                "or Windows PSAPI"
            )
        self._peak = self.baseline.rss_bytes
        self._count = 1
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._poll, name="zhouyi-rss-sampler", daemon=True
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        final = sample_process_memory()
        if self.baseline is None or final.rss_bytes is None:
            return
        self._peak = max(self._peak, final.rss_bytes)
        self._count += 1
        baseline = self.baseline.rss_bytes
        assert baseline is not None
        self.report = ProcessMemoryReport(
            baseline_rss_bytes=baseline,
            sampled_peak_rss_bytes=self._peak,
            final_rss_bytes=final.rss_bytes,
            peak_increment_bytes=max(0, self._peak - baseline),
            final_increment_bytes=max(0, final.rss_bytes - baseline),
            sample_count=self._count,
            interval_seconds=self.interval_seconds,
        )


@dataclass(frozen=True)
class MemoryPoolSnapshot:
    name: str
    limit_bytes: int
    current_bytes: int
    peak_bytes: int
    reserve_count: int
    release_count: int
    eviction_count: int
    evicted_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "limit_mib": self.limit_bytes / MIB,
            "current_mib": self.current_bytes / MIB,
            "peak_mib": self.peak_bytes / MIB,
        }


@dataclass
class _PoolState:
    limit_bytes: int
    current_bytes: int = 0
    peak_bytes: int = 0
    reserve_count: int = 0
    release_count: int = 0
    eviction_count: int = 0
    evicted_bytes: int = 0


class MemoryPoolLedger:
    """Track declared pool budgets; this does not allocate or measure RAM."""

    def __init__(self, total_limit_bytes: int) -> None:
        self._validate_amount(total_limit_bytes, "total_limit_bytes", allow_zero=False)
        self.total_limit_bytes = total_limit_bytes
        self._pools: dict[str, _PoolState] = {}
        self._peak_total_bytes = 0

    @staticmethod
    def _validate_amount(amount: int, field: str, *, allow_zero: bool = True) -> None:
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ValueError(f"{field} must be an integer byte count")
        if amount < 0 or (not allow_zero and amount == 0):
            raise ValueError(f"{field} is out of range")

    def register_pool(self, name: str, limit_bytes: int) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("pool name must be non-empty")
        self._validate_amount(limit_bytes, "limit_bytes", allow_zero=False)
        if name in self._pools:
            raise ValueError(f"pool already registered: {name}")
        # Per-pool limits may sum above the global cap; the aggregate check
        # below remains authoritative when reservations are made.
        self._pools[name] = _PoolState(limit_bytes=limit_bytes)

    def reserve(self, name: str, amount_bytes: int) -> None:
        self._validate_amount(amount_bytes, "amount_bytes")
        pool = self._get(name)
        new_pool = pool.current_bytes + amount_bytes
        new_total = self.current_bytes + amount_bytes
        if new_pool > pool.limit_bytes:
            raise MemoryBudgetExceeded(f"pool budget exceeded: {name}")
        if new_total > self.total_limit_bytes:
            raise MemoryBudgetExceeded("aggregate memory budget exceeded")
        pool.current_bytes = new_pool
        pool.peak_bytes = max(pool.peak_bytes, new_pool)
        self._peak_total_bytes = max(self._peak_total_bytes, new_total)
        if amount_bytes:
            pool.reserve_count += 1

    def release(self, name: str, amount_bytes: int) -> None:
        self._validate_amount(amount_bytes, "amount_bytes")
        pool = self._get(name)
        if amount_bytes > pool.current_bytes:
            raise ValueError(f"release exceeds current pool usage: {name}")
        pool.current_bytes -= amount_bytes
        if amount_bytes:
            pool.release_count += 1

    def record_eviction(self, name: str, amount_bytes: int) -> None:
        self._validate_amount(amount_bytes, "amount_bytes", allow_zero=False)
        pool = self._get(name)
        self.release(name, amount_bytes)
        pool.eviction_count += 1
        pool.evicted_bytes += amount_bytes

    def _get(self, name: str) -> _PoolState:
        try:
            return self._pools[name]
        except KeyError as exc:
            raise KeyError(f"unknown memory pool: {name}") from exc

    @property
    def current_bytes(self) -> int:
        return sum(pool.current_bytes for pool in self._pools.values())

    @property
    def peak_bytes(self) -> int:
        return self._peak_total_bytes

    def snapshot(self) -> tuple[MemoryPoolSnapshot, ...]:
        return tuple(
            MemoryPoolSnapshot(
                name=name,
                limit_bytes=pool.limit_bytes,
                current_bytes=pool.current_bytes,
                peak_bytes=pool.peak_bytes,
                reserve_count=pool.reserve_count,
                release_count=pool.release_count,
                eviction_count=pool.eviction_count,
                evicted_bytes=pool.evicted_bytes,
            )
            for name, pool in sorted(self._pools.items())
        )

    def assert_within_budget(self) -> None:
        if self.current_bytes > self.total_limit_bytes:
            raise MemoryBudgetExceeded("aggregate memory budget exceeded")


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--tracemalloc",
        action="store_true",
        help="start and report Python allocation tracing (not process RSS)",
    )
    args = parser.parse_args()

    if args.tracemalloc:
        import tracemalloc

        if not tracemalloc.is_tracing():
            tracemalloc.start()

    sample = sample_process_memory(include_tracemalloc=args.tracemalloc)
    payload = asdict(sample)
    payload["rss_mib"] = sample.rss_mib
    payload["os_peak_rss_mib"] = sample.os_peak_rss_mib
    payload["unit"] = "bytes; MiB fields use 1024*1024"
    payload["warning"] = (
        "A standalone sample is not a workload peak. Use "
        "ProcessMemoryMeasurement around the operation; its peak is sampled."
    )
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"RSS: {sample.rss_mib!r} MiB ({sample.source})")
        print(f"OS peak RSS: {sample.os_peak_rss_mib!r} MiB")
        print(payload["warning"])
    return 0 if sample.rss_bytes is not None else 2


if __name__ == "__main__":
    raise SystemExit(_main())

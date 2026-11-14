"""Shared bounded-stream scan budget signal."""

class ScanBudgetExceeded(RuntimeError):
    """A bounded stream stopped before its source was fully exhausted."""

    def __init__(self, records_scanned: int):
        self.records_scanned = records_scanned
        super().__init__(f"scan budget exhausted after {records_scanned} records")

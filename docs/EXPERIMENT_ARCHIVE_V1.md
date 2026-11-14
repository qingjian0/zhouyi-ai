# Experiment Archive v1

Status: implementation candidate; local execution and CI validation pending.

`archive_benchmark_report` stores one JSON envelope per run ID. It records UTC creation time, Python/runtime platform metadata, optional caller-supplied code revision, task-set digest, report digest, and the complete benchmark report.

Archive publication is append-only: an existing run ID is never overwritten. The implementation writes and fsyncs a temporary file, then publishes it with an atomic hard link. The archive directory must support hard links; callers should use a local filesystem with that capability.

The caller must supply a trustworthy code revision. The archive does not guess the current Git commit. The report digest covers canonical JSON for the report object, not the envelope metadata.

Next validation: run archive tests on supported operating systems and verify hard-link behavior on the target filesystem. Then connect benchmark output to this archive and include the experiment-matrix digest and source revision in every research run.
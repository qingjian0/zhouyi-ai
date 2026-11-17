# E12-A6 Single-Writer Runtime v1

## Contract

`E12A6WriterRuntime` is the process-lifetime composition root for the E12-A6 writer. It acquires an exclusive POSIX `flock` before opening SQLite, constructs the ZPCM memory and persistent lifecycle ledger only while holding that lock, and releases the lock only after closing the database.

The lock is non-blocking and fails closed when another writer owns the state. The lock file is never unlinked during normal release; unlinking a live lock file can create split-brain lock inodes.

## Filesystem requirements

- Run the writer under a dedicated unprivileged OS account.
- Pre-create the state directory; it must be owned by that account and have mode `0700`.
- The lock file is opened with `O_NOFOLLOW`, must be a regular file owned by the service account, and is forced to mode `0600`.
- The database path must not be a symbolic link and its file mode is forced to `0600`.
- Keep the runtime object alive for the entire writer lifetime; do not open `ZPCMMemory` independently in a second process.

## Usage

Construct `E12A6WriterRuntime` once during dedicated service startup, then route all authenticated submissions through `runtime.service`. Call `runtime.close()` during orderly shutdown. Process termination releases the kernel flock automatically; startup must still run lifecycle replay validation before accepting traffic.

## Limitations

This is a POSIX single-writer guard and private-file permission baseline, not a complete IPC server. It does not authenticate remote clients, protect against root, prevent a same-UID malicious process from opening the database, or provide network transport. Deploy the service under a dedicated UID and expose a separately authenticated local IPC boundary (for example, Unix-domain socket with `SO_PEERCRED`) before treating it as a multi-process production service. Windows requires a separate locking backend and is deliberately unsupported by this implementation.

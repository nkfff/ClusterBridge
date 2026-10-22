# ClusterBridge

ClusterBridge is a lightweight SSH data relay desktop application. It connects to a source and a destination at the same time, forwarding data through the local computer in bounded memory instead of storing the complete file on disk.

## Release history

All timestamps use `Asia/Shanghai` (`UTC+08:00`) and are recorded to the second.

| Version | Released at | Highlights |
|---|---|---|
| [V1.0.0](https://github.com/nkfff/ClusterBridge/releases/tag/v1.0.0) | 2026-10-22 16:35:00 +08:00 | Cross-platform packaging workflow, concurrent resumable transfer queue, and release automation |
| [V0.1.0](https://github.com/nkfff/ClusterBridge/releases/tag/v0.1.0) | 2026-10-22 16:31:04 +08:00 | Initial PySide6 desktop MVP and single-file SSH streaming |

## MVP scope

- Stream a single file between cluster-to-cluster, cluster-to-local, and local-to-cluster endpoints
- Store SSH connection metadata in local SQLite; keep passwords in the operating system keychain through `keyring`
- Let AsyncSSH validate SSH host keys using its configured `known_hosts` policy
- Use a configurable 4 MiB default memory buffer
- Resume a destination file from its existing size
- Report progress and surface transfer failures

The MVP intentionally supports one transfer at a time. Recursive directories, concurrent small-file transfers, ProxyJump, segment-level checksums, and sleep prevention are planned for later releases.

V1 adds a bounded-concurrency task queue through `transfer_many()`. Each task remains an independent SFTP stream and resumes from the existing destination size, so a failed task does not restart completed tasks. This is the bridge-safe equivalent of `rsync --partial --relative`: it preserves relative remote paths with `join_remote_path()` without requiring the two clusters to connect to each other.

## Run from source

Python 3.11 or newer is required:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m clusterbridge
```

On first launch, the application creates `~/.clusterbridge/clusterbridge.sqlite3`. The database contains connection metadata only; passwords are stored in the operating system keychain under `clusterbridge/<connection-id>`.

## Transfer model

```text
source SFTP/local file -> bounded async buffer -> destination SFTP/local file
```

The buffer has a fixed capacity and applies backpressure between the reader and writer, so local memory usage does not grow with file size. Source and destination connections are closed when the transfer finishes or fails.

## Security notes

- Passwords are never written to SQLite, logs, or transfer history.
- SSH host-key verification must remain enabled. Do not disable it for convenience.
- Connection names, addresses, and paths can still be sensitive metadata; use the default per-user database permissions.
- Relayed data passes through the local computer's network stack and memory. Confirm that this workflow complies with your cluster and research-data policies.

## Is this already a desktop app?

It is a runnable desktop application in source form, built with PySide6. V1 adds a GitHub Actions packaging workflow which builds standalone bundles on native macOS, Windows, and Linux runners when a `v*` tag is pushed:

- macOS `.app` archive
- Windows `.zip` containing the `.exe`
- Linux `.tar.gz` bundle

The bundles are produced by CI rather than by this macOS development machine. Users of a release asset do not need to install Python or the project dependencies. SSH keychain integration still needs validation on each target operating system.

## Project structure

- `clusterbridge/models.py`: connection and transfer request models
- `clusterbridge/storage.py`: SQLite metadata storage
- `clusterbridge/secrets.py`: operating-system keychain adapter
- `clusterbridge/transfer.py`: backpressure-controlled local/SSH streaming
- `clusterbridge/ui.py`: PySide6 desktop window

## Roadmap

1. Connection management dialog for creating, editing, and deleting SSH profiles
2. Recursive directory discovery with per-file resume
3. Segment-level checksums and source-file snapshot validation
4. Bandwidth limiting and task cancellation
5. ProxyJump, connection testing, and sleep prevention

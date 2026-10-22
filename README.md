# ClusterBridge

ClusterBridge is a lightweight SSH data relay desktop application. It connects to a source and a destination at the same time, forwarding data through the local computer in bounded memory instead of storing the complete file on disk.

## MVP scope

- Stream a single file between cluster-to-cluster, cluster-to-local, and local-to-cluster endpoints
- Store SSH connection metadata in local SQLite; keep passwords in the operating system keychain through `keyring`
- Let AsyncSSH validate SSH host keys using its configured `known_hosts` policy
- Use a configurable 4 MiB default memory buffer
- Resume a destination file from its existing size
- Report progress and surface transfer failures

The MVP intentionally supports one transfer at a time. Recursive directories, concurrent small-file transfers, ProxyJump, segment-level checksums, and sleep prevention are planned for later releases.

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

It is a runnable desktop application in source form, built with PySide6. It is not yet packaged as a standalone distributable application:

- macOS `.app` / `.dmg`: not built yet
- Windows `.exe`: not built yet
- Linux AppImage / package: not built yet

Until packaging is added, users need Python and the project dependencies installed. The next release should use PyInstaller to create platform-specific bundles and then test SSH keychain integration on each target operating system.

## Project structure

- `clusterbridge/models.py`: connection and transfer request models
- `clusterbridge/storage.py`: SQLite metadata storage
- `clusterbridge/secrets.py`: operating-system keychain adapter
- `clusterbridge/transfer.py`: backpressure-controlled local/SSH streaming
- `clusterbridge/ui.py`: PySide6 desktop window

## Roadmap

1. Connection management dialog for creating, editing, and deleting SSH profiles
2. Recursive directory transfer with per-file resume
3. Segment-level checksums and source-file snapshot validation
4. Concurrent small-file queue and bandwidth limiting
5. ProxyJump, connection testing, and sleep prevention
6. PyInstaller bundles and macOS, Windows, and Linux release testing

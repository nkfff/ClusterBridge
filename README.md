# ClusterBridge

ClusterBridge is a lightweight SSH data relay desktop application. It connects to a source and a destination at the same time, forwarding data through the local computer in bounded memory instead of storing the complete file on disk.

## Release history

All timestamps use `Asia/Shanghai` (`UTC+08:00`) and are recorded to the second.

| Version | Released at | Highlights |
|---|---|---|
| [V2.0.0](https://github.com/nkfff/ClusterBridge/releases/tag/v2.0.0) | 2026-10-23 17:18:59 +08:00 | Glass-flow blue UI redesign, transparent brand icon, and refined desktop interaction |
| [V1.0.1](https://github.com/nkfff/ClusterBridge/releases/tag/v1.0.1) | 2026-10-22 17:10:50 +08:00 | Fixed app startup and Qt thread crash, added connection manager, icons, and replacement bundles |
| [V1.0.0](https://github.com/nkfff/ClusterBridge/releases/tag/v1.0.0) | 2026-10-22 16:35:53 +08:00 | Cross-platform packaging workflow, concurrent resumable transfer queue, and release automation |
| [V0.1.0](https://github.com/nkfff/ClusterBridge/releases/tag/v0.1.0) | 2026-10-22 16:31:42 +08:00 | Initial PySide6 desktop MVP and single-file SSH streaming |

## Version update notes

### V2.0.0 — Glass-flow desktop redesign

Released at `2026-10-23 17:18:59 +08:00`.

- Redesigned the main window around the ClusterBridge blue glass-flow visual language.
- Added branded header treatment with the application icon and relay subtitle.
- Reorganized Source and Destination into separate endpoint cards with a visible transfer arrow.
- Improved task queue hierarchy, action buttons, spacing, status text, and progress bar presentation.
- Removed the baked-in white background from the application icon and regenerated transparent PNG, ICNS, and ICO assets.
- Updated the application and package version to `2.0.0`.

### V1.0.1 — Fixed standalone release

Released at `2026-10-22 17:10:50 +08:00`.

- Fixed the packaged-app startup failure caused by a relative import in the PyInstaller launcher.
- Added a startup bootstrap that records uncaught startup errors in `~/.clusterbridge/logs/startup.log`.
- Added a fallback error dialog for packaged environments where no terminal is visible.
- Added delayed loading of the transfer module so UI startup is less sensitive to optional runtime import failures.
- Updated PyInstaller collection rules for AsyncSSH and cryptography.
- Rebuilt and published macOS, Windows, and Linux standalone bundles.
- Published the detailed [`tutorial.html`](https://github.com/nkfff/ClusterBridge/releases/download/v1.0.1/tutorial.html) guide.
- Added the in-app SSH connection manager for saved cluster profiles and keychain passwords.
- Fixed a macOS Qt crash caused by updating the progress bar from the transfer worker thread.
- Added exception type and message to failed-task status output.
- Added the glass-flow icon in macOS, Windows, and Linux packaging formats.
- Documented the current single-file limitation, absolute remote paths, and directory/file path rules.

### V1.0.0 — Cross-platform desktop release

Released at `2026-10-22 16:35:53 +08:00`.

- Added a bounded-concurrency task queue for multiple independent transfers.
- Added per-task resume behavior based on the existing destination file size.
- Added failure isolation so completed tasks are not restarted when another task fails.
- Added relative remote path joining for rsync-like `--relative` behavior through the local relay.
- Added GitHub Actions builds for native macOS, Windows, and Linux runners.
- Added PyInstaller packaging for standalone desktop bundles.
- Added the first V1 release assets and release automation.

### V0.1.0 — Initial desktop MVP

Released at `2026-10-22 16:31:42 +08:00`.

- Added the PySide6 desktop application shell.
- Added local-memory streaming between local files and SSH/SFTP endpoints.
- Added SQLite storage for SSH connection metadata.
- Added operating-system keychain storage for passwords through `keyring`.
- Added bounded 4 MiB transfer buffers.
- Added basic destination-size resume behavior for interrupted single-file transfers.
- Added progress reporting, validation, and explicit transfer errors.
- Added an English README and initial cross-platform project structure.

## About

- Product name: ClusterBridge
- Current app version: `2.0.0`
- Last updated: `2026-10-23 17:18:59 +08:00`
- Maintainer repository: `nkfff/ClusterBridge`
- Releases page: <https://github.com/nkfff/ClusterBridge/releases>
- Current release assets: macOS, Windows, Linux, and [`tutorial.html`](https://github.com/nkfff/ClusterBridge/releases/download/v2.0.0/tutorial.html)
- Core design: stream data through local memory with bounded buffers, no full-file local staging
- Connection setup: use `Manage SSH connections` in the desktop app to save host, port, username, and keychain password

## MVP scope

- Stream a single file between cluster-to-cluster, cluster-to-local, and local-to-cluster endpoints
- Store SSH connection metadata in local SQLite; keep passwords in the operating system keychain through `keyring`
- Let AsyncSSH validate SSH host keys using its configured `known_hosts` policy
- Use a configurable 4 MiB default memory buffer
- Resume a destination file from its existing size
- Report progress and surface transfer failures

V1.0.1 currently transfers one file per task. A source directory is not recursive input yet; use a complete source filename and a complete destination filename.

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

For remote SFTP paths, use absolute paths. `~` is not expanded by SFTP; run `echo "$HOME"` on the cluster and use the returned path.

## Detailed tutorial

You can open a complete step-by-step guide from:

- In-app button: `Open tutorial`
- Local file: [`docs/tutorial.html`](/Users/george/ClusterBridge/docs/tutorial.html)
- Downloadable release copy: [`tutorial.html`](https://github.com/nkfff/ClusterBridge/releases/download/v2.0.0/tutorial.html)

## Startup troubleshooting for packaged app

If you double-click the packaged app and no window appears:

1. Check startup diagnostics at:
   - macOS/Linux: `~/.clusterbridge/logs/startup.log`
   - Windows: `%USERPROFILE%/.clusterbridge/logs/startup.log`
2. Verify macOS Gatekeeper did not block launch:
   - `xattr -dr com.apple.quarantine /Applications/ClusterBridge.app`
3. Launch from terminal once to capture platform-level errors:
   - `open /Applications/ClusterBridge.app` (macOS)
   - `./ClusterBridge` (Linux extracted bundle)
   - `ClusterBridge.exe` (Windows extracted bundle)

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

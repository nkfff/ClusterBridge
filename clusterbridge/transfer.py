import asyncio
import posixpath
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import asyncssh

from .models import ConnectionProfile, Endpoint, EndpointKind, TransferRequest
from .secrets import load_password

ProgressCallback = Callable[[int, int], Awaitable[None] | None]


class _AsyncLocalFile:
    def __init__(self, file_object) -> None:
        self._file = file_object

    async def read(self, size: int) -> bytes:
        return await asyncio.to_thread(self._file.read, size)

    async def write(self, data: bytes) -> int:
        return await asyncio.to_thread(self._file.write, data)

    async def seek(self, offset: int) -> None:
        await asyncio.to_thread(self._file.seek, offset)

    async def close(self) -> None:
        await asyncio.to_thread(self._file.close)


@dataclass(frozen=True, slots=True)
class TransferResult:
    bytes_transferred: int
    resumed_from: int


@dataclass(frozen=True, slots=True)
class BatchTransferResult:
    completed: int
    failed: int
    bytes_transferred: int
    resumed_from: int
    errors: tuple[str, ...] = ()


async def _notify(callback: ProgressCallback | None, current: int, total: int) -> None:
    if callback:
        result = callback(current, total)
        if asyncio.iscoroutine(result):
            await result


async def _connect(profile: ConnectionProfile) -> asyncssh.SSHClientConnection:
    password = load_password(profile.id)
    return await asyncssh.connect(
        profile.host,
        port=profile.port,
        username=profile.username,
        password=password,
    )


async def transfer_file(
    request: TransferRequest,
    profiles: dict[str, ConnectionProfile],
    progress: ProgressCallback | None = None,
) -> TransferResult:
    """Relay one file with bounded memory and optional size-based resume.

    Host-key verification is intentionally delegated to AsyncSSH's known_hosts
    configuration in production builds; this MVP's UI does not expose a bypass.
    """
    request.validate()
    source_connection = destination_connection = None
    source_sftp = destination_sftp = None
    source_file = destination_file = None
    try:
        if request.source.kind is EndpointKind.SSH:
            source_profile = profiles[request.source.connection_id or ""]
            source_connection = await _connect(source_profile)
            source_sftp = await source_connection.start_sftp_client()
            source_stat = await source_sftp.stat(request.source.path)
            source_file = await source_sftp.open(request.source.path, "rb")
        else:
            source_path = Path(request.source.path).expanduser()
            source_stat = source_path.stat()
            source_file = _AsyncLocalFile(
                await asyncio.to_thread(source_path.open, "rb")
            )

        total = source_stat.size if hasattr(source_stat, "size") else source_stat.st_size
        offset = 0
        if request.destination.kind is EndpointKind.SSH:
            destination_profile = profiles[request.destination.connection_id or ""]
            destination_connection = await _connect(destination_profile)
            destination_sftp = await destination_connection.start_sftp_client()
            try:
                destination_stat = await destination_sftp.stat(request.destination.path)
                if request.resume and destination_stat.size <= total:
                    offset = destination_stat.size
            except asyncssh.SFTPError:
                offset = 0
            destination_file = await destination_sftp.open(
                request.destination.path, "ab" if offset else "wb"
            )
        else:
            destination_path = Path(request.destination.path).expanduser()
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_file = _AsyncLocalFile(
                await asyncio.to_thread(
                    destination_path.open, "ab" if offset else "wb"
                )
            )

        if offset:
            await source_file.seek(offset)
        transferred = offset
        await _notify(progress, transferred, total)
        while True:
            chunk = await source_file.read(request.chunk_size)
            if not chunk:
                break
            await destination_file.write(chunk)
            transferred += len(chunk)
            await _notify(progress, transferred, total)
        await destination_file.close()
        destination_file = None
        await source_file.close()
        source_file = None
        return TransferResult(transferred, offset)
    finally:
        if source_file:
            await source_file.close()
        if destination_file:
            await destination_file.close()
        if source_sftp:
            source_sftp.exit()
        if destination_sftp:
            destination_sftp.exit()
        if source_connection:
            source_connection.close()
            await source_connection.wait_closed()
        if destination_connection:
            destination_connection.close()
            await destination_connection.wait_closed()


async def transfer_many(
    requests: list[TransferRequest],
    profiles: dict[str, ConnectionProfile],
    progress: ProgressCallback | None = None,
    max_concurrency: int = 3,
) -> BatchTransferResult:
    """Run an independent, resumable transfer queue with bounded concurrency.

    Each task opens its own source and destination streams, so a failed task
    can be retried without restarting completed tasks.
    """
    if not requests:
        return BatchTransferResult(0, 0, 0, 0)
    if not 1 <= max_concurrency <= 16:
        raise ValueError("max_concurrency must be between 1 and 16")

    semaphore = asyncio.Semaphore(max_concurrency)
    completed = failed = bytes_transferred = resumed_from = 0
    errors: list[str] = []
    lock = asyncio.Lock()

    async def run_one(request: TransferRequest) -> None:
        nonlocal completed, failed, bytes_transferred, resumed_from
        async with semaphore:
            try:
                result = await transfer_file(request, profiles)
            except Exception as exc:
                async with lock:
                    failed += 1
                    errors.append(str(exc))
                return
            async with lock:
                completed += 1
                bytes_transferred += result.bytes_transferred
                resumed_from += result.resumed_from
                await _notify(progress, bytes_transferred, 0)

    await asyncio.gather(*(run_one(request) for request in requests))
    return BatchTransferResult(
        completed, failed, bytes_transferred, resumed_from, tuple(errors)
    )


def join_remote_path(directory: str, relative_path: str) -> str:
    """Join a POSIX remote directory without allowing an absolute child path."""
    return posixpath.join(directory.rstrip("/"), relative_path.lstrip("/"))

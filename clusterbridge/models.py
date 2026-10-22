from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class EndpointKind(StrEnum):
    LOCAL = "local"
    SSH = "ssh"


@dataclass(frozen=True, slots=True)
class ConnectionProfile:
    id: str
    name: str
    host: str
    username: str
    port: int = 22
    default_path: str = "/"


@dataclass(frozen=True, slots=True)
class Endpoint:
    kind: EndpointKind
    path: str
    connection_id: str | None = None

    def validate(self) -> None:
        if not self.path.strip():
            raise ValueError("路径不能为空")
        if self.kind is EndpointKind.SSH and not self.connection_id:
            raise ValueError("SSH 端点必须选择连接配置")
        if self.kind is EndpointKind.LOCAL:
            Path(self.path).expanduser()


@dataclass(frozen=True, slots=True)
class TransferRequest:
    source: Endpoint
    destination: Endpoint
    chunk_size: int = 4 * 1024 * 1024
    resume: bool = True

    def validate(self) -> None:
        self.source.validate()
        self.destination.validate()
        if self.source == self.destination:
            raise ValueError("源和目标不能相同")
        if not 64 * 1024 <= self.chunk_size <= 64 * 1024 * 1024:
            raise ValueError("缓冲区必须在 64 KiB 到 64 MiB 之间")

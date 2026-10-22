import pytest

from clusterbridge.models import Endpoint, EndpointKind, TransferRequest
from clusterbridge.transfer import join_remote_path


def test_ssh_endpoint_requires_connection() -> None:
    with pytest.raises(ValueError, match="SSH"):
        Endpoint(EndpointKind.SSH, "/data").validate()


def test_transfer_rejects_same_endpoint() -> None:
    endpoint = Endpoint(EndpointKind.LOCAL, "/tmp/data")
    with pytest.raises(ValueError, match="相同"):
        TransferRequest(endpoint, endpoint).validate()


def test_chunk_size_is_bounded() -> None:
    source = Endpoint(EndpointKind.LOCAL, "/tmp/source")
    destination = Endpoint(EndpointKind.LOCAL, "/tmp/destination")
    with pytest.raises(ValueError, match="缓冲区"):
        TransferRequest(source, destination, chunk_size=1).validate()


def test_remote_path_preserves_relative_structure() -> None:
    assert join_remote_path("/backup/run", "sample/a.fastq.gz") == (
        "/backup/run/sample/a.fastq.gz"
    )
    assert join_remote_path("/backup/run", "/sample/a.fastq.gz") == (
        "/backup/run/sample/a.fastq.gz"
    )

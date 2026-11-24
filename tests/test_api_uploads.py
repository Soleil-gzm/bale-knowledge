from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from backend import api_integration


class FakeIngestion:
    def __init__(self):
        self.file_path = None
        self.namespace = None
        self.content = None
        self.chunk_count = 1

    def ingest_file(self, file_path, *, namespace):
        self.file_path = file_path
        self.namespace = namespace
        self.content = Path(file_path).read_bytes()
        return self.chunk_count


class FakeCollections:
    def info(self, namespace):
        return {"collection_name": namespace, "document_count": 1}


@pytest.fixture
def client_and_services(monkeypatch):
    container = SimpleNamespace(
        ingestion=FakeIngestion(),
        collections=FakeCollections(),
    )
    monkeypatch.setattr(api_integration, "services", container)
    app = Flask(__name__)
    app.register_blueprint(api_integration.vector_bp)
    return app.test_client(), container


@pytest.mark.parametrize("filename", ["notes.txt", "report.pdf"])
def test_multipart_upload_uses_temporary_file(client_and_services, filename):
    client, container = client_and_services

    response = client.post(
        "/api/vector/upload_file",
        data={
            "collection_name": "docs",
            "file": (BytesIO(b"document content"), filename),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "message": f"文件上传并处理成功: {filename}",
        "database_info": {"collection_name": "docs", "document_count": 1},
    }
    assert container.ingestion.content == b"document content"
    assert container.ingestion.namespace == "docs"
    assert Path(container.ingestion.file_path).suffix == Path(filename).suffix
    assert not Path(container.ingestion.file_path).exists()


def test_upload_returns_error_when_no_chunks_are_written(client_and_services):
    client, container = client_and_services
    container.ingestion.chunk_count = 0

    response = client.post(
        "/api/vector/upload_file",
        data={"file": (BytesIO(b""), "empty.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 500
    assert response.get_json() == {"success": False, "message": "文件处理失败"}


def test_upload_rejects_unsupported_extension(client_and_services):
    client, container = client_and_services

    response = client.post(
        "/api/vector/upload_file",
        data={"file": (BytesIO(b"print('unsafe')"), "script.py")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert container.ingestion.file_path is None


def test_upload_rejects_oversized_request(client_and_services, monkeypatch):
    client, container = client_and_services
    monkeypatch.setattr(api_integration, "MAX_UPLOAD_BYTES", 8)

    response = client.post(
        "/api/vector/upload_file",
        data={"file": (BytesIO(b"too large"), "notes.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert container.ingestion.file_path is None


def test_arbitrary_server_path_upload_is_not_available(client_and_services):
    client, container = client_and_services

    response = client.post(
        "/api/vector/upload_document",
        json={"file_path": "/etc/passwd", "collection_name": "docs"},
    )

    assert response.status_code == 404
    assert container.ingestion.file_path is None

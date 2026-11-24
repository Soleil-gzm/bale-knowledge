from io import BytesIO
from pathlib import Path

import pytest
from flask import Flask

from backend import api_integration


class FakeManager:
    def __init__(self):
        self.file_path = None
        self.collection_name = None
        self.content = None

    def process_file(self, file_path, collection_name):
        self.file_path = file_path
        self.collection_name = collection_name
        self.content = Path(file_path).read_bytes()
        return True

    def get_database_info(self, collection_name):
        return {"collection_name": collection_name, "document_count": 1}


@pytest.fixture
def client_and_manager(monkeypatch):
    manager = FakeManager()
    monkeypatch.setattr(api_integration, "vector_manager", manager)
    app = Flask(__name__)
    app.register_blueprint(api_integration.vector_bp)
    return app.test_client(), manager


@pytest.mark.parametrize("filename", ["notes.txt", "report.pdf"])
def test_multipart_upload_uses_temporary_file(client_and_manager, filename):
    client, manager = client_and_manager

    response = client.post(
        "/api/vector/upload_file",
        data={
            "collection_name": "docs",
            "file": (BytesIO(b"document content"), filename),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert manager.content == b"document content"
    assert manager.collection_name == "docs"
    assert Path(manager.file_path).suffix == Path(filename).suffix
    assert not Path(manager.file_path).exists()


def test_upload_rejects_unsupported_extension(client_and_manager):
    client, manager = client_and_manager

    response = client.post(
        "/api/vector/upload_file",
        data={"file": (BytesIO(b"print('unsafe')"), "script.py")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert manager.file_path is None


def test_upload_rejects_oversized_request(client_and_manager, monkeypatch):
    client, manager = client_and_manager
    monkeypatch.setattr(api_integration, "MAX_UPLOAD_BYTES", 8)

    response = client.post(
        "/api/vector/upload_file",
        data={"file": (BytesIO(b"too large"), "notes.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert manager.file_path is None


def test_arbitrary_server_path_upload_is_not_available(client_and_manager):
    client, manager = client_and_manager

    response = client.post(
        "/api/vector/upload_document",
        json={"file_path": "/etc/passwd", "collection_name": "docs"},
    )

    assert response.status_code == 404
    assert manager.file_path is None

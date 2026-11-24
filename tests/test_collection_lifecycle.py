from types import SimpleNamespace

import pytest
from flask import Flask
from langchain_core.documents import Document

from backend import api_integration
from backend import vector_db_manager as manager_module
from backend.vector_db_manager import VectorDatabaseManager


def make_manager() -> VectorDatabaseManager:
    manager = VectorDatabaseManager.__new__(VectorDatabaseManager)
    manager.collection_name = "current"
    manager.vectorstore = None
    manager.milvus_host = "localhost"
    manager.milvus_port = "19530"
    manager.embeddings = object()
    return manager


def test_schema_failure_never_drops_collection(monkeypatch):
    dropped = []
    monkeypatch.setattr(manager_module.utility, "has_collection", lambda name: True)
    monkeypatch.setattr(manager_module.utility, "drop_collection", dropped.append)

    class FailingStore:
        def add_documents(self, documents):
            raise RuntimeError("inconsistent with defined schema")

    manager = make_manager()
    manager.vectorstore = FailingStore()

    with pytest.raises(RuntimeError, match="inconsistent with defined schema"):
        manager.add_documents_to_db([Document(page_content="content")])

    assert dropped == []


def test_clear_database_only_resets_current_vectorstore(monkeypatch):
    existing = {"current", "other"}
    dropped = []
    monkeypatch.setattr(manager_module.utility, "has_collection", lambda name: name in existing)
    monkeypatch.setattr(manager_module.utility, "drop_collection", dropped.append)

    manager = make_manager()
    current_store = object()
    manager.vectorstore = current_store

    assert manager.clear_database("other") is True
    assert manager.vectorstore is current_store
    assert manager.clear_database("current") is True
    assert manager.vectorstore is None
    assert manager.clear_database("missing") is False
    assert dropped == ["other", "current"]


def make_collection_client(monkeypatch):
    class FakeCollections:
        def __init__(self):
            self.calls = []

        def info(self, namespace):
            self.calls.append(("info", namespace))
            return {"collection_name": namespace, "document_count": 1}

        def clear(self, namespace):
            self.calls.append(("clear", namespace))
            return namespace != "missing"

    collections = FakeCollections()
    monkeypatch.setattr(
        api_integration,
        "services",
        SimpleNamespace(collections=collections),
    )
    app = Flask(__name__)
    app.register_blueprint(api_integration.vector_bp)
    return app.test_client(), collections


def test_clear_collection_api_passes_collection_name(monkeypatch):
    client, collections = make_collection_client(monkeypatch)

    response = client.post("/api/vector/clear_collection", json={"collection_name": "docs"})
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "message": "集合 'docs' 已清空"}

    response = client.post("/api/vector/clear_collection", json={"collection_name": "missing"})
    assert response.status_code == 404
    assert response.get_json() == {"success": False, "message": "集合 'missing' 不存在"}
    assert collections.calls == [("clear", "docs"), ("clear", "missing")]


def test_collection_info_api_uses_collection_service(monkeypatch):
    client, collections = make_collection_client(monkeypatch)

    response = client.get("/api/vector/collection_info?collection_name=docs")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "database_info": {"collection_name": "docs", "document_count": 1},
    }
    assert collections.calls == [("info", "docs")]

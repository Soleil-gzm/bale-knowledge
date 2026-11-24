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


def test_clear_collection_api_passes_collection_name(monkeypatch):
    class FakeManager:
        def __init__(self):
            self.calls = []

        def clear_database(self, collection_name):
            self.calls.append(collection_name)
            return collection_name != "missing"

    manager = FakeManager()
    monkeypatch.setattr(api_integration, "vector_manager", manager)
    app = Flask(__name__)
    app.register_blueprint(api_integration.vector_bp)
    client = app.test_client()

    response = client.post("/api/vector/clear_collection", json={"collection_name": "docs"})
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    response = client.post("/api/vector/clear_collection", json={"collection_name": "missing"})
    assert response.status_code == 404
    assert response.get_json()["success"] is False
    assert manager.calls == ["docs", "missing"]

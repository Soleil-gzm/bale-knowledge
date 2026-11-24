import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from backend import api_integration, composition


def test_composition_root_shares_store_between_services(monkeypatch):
    manager = object()
    captured = {}

    def fake_manager(**kwargs):
        captured.update(kwargs)
        return manager

    monkeypatch.setattr(composition, "VectorDatabaseManager", fake_manager)

    container = composition.create_services(
        milvus_host="localhost",
        milvus_port="19530",
        embedding_model="model",
        dashscope_api_key="secret",
    )

    assert captured == {
        "milvus_host": "localhost",
        "milvus_port": "19530",
        "embedding_model": "model",
        "dashscope_api_key": "secret",
    }
    assert container.ingestion.processor.manager is manager
    assert container.ingestion.store is container.retrieval.store
    assert container.generation.retriever is container.retrieval
    assert container.collections.store is container.retrieval.store


def test_register_vector_routes_accepts_injected_services(monkeypatch):
    container = SimpleNamespace()
    monkeypatch.setattr(api_integration, "services", None)
    monkeypatch.setattr(
        api_integration,
        "init_vector_system",
        lambda: (_ for _ in ()).throw(AssertionError("default initialization was called")),
    )
    app = Flask(__name__)

    api_integration.register_vector_routes(app, container)

    assert api_integration.services is container


def test_flask_adapter_import_does_not_load_milvus_or_model_sdks():
    project_root = Path(__file__).resolve().parents[1]
    code = """
import builtins
import sys

blocked = {"pymilvus", "langchain", "langchain_core", "langchain_community", "langchain_milvus", "openai"}
original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name.split(".")[0] in blocked:
        raise AssertionError(f"forbidden Flask adapter dependency: {name}")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
from backend import api_integration
assert "backend.vector_db_manager" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

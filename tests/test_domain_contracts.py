import asyncio
import subprocess
import sys
from pathlib import Path

from backend.domain.models import SearchHit
from backend.domain.retriever import Retriever
from backend.domain.testing import FakeRetriever


def test_domain_imports_do_not_require_frameworks_or_external_sdks():
    project_root = Path(__file__).resolve().parents[1]
    code = """
import builtins

blocked = {"flask", "pymilvus", "langchain", "langchain_core", "langchain_community", "langchain_milvus", "openai"}
original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name.split(".")[0] in blocked:
        raise AssertionError(f"forbidden domain dependency: {name}")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
from backend.domain.models import Answer, Chunk, SearchHit
from backend.domain.ports import AnswerGenerator, DocumentProcessor, VectorStore
from backend.domain.retriever import Retriever
from backend.domain.testing import FakeRetriever
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_fake_retriever_implements_async_contract_and_filters_deterministically():
    hits = [
        SearchHit("first", 0.9, "docs", {"kind": "guide"}),
        SearchHit("second", 0.8, "docs", {"kind": "api"}),
        SearchHit("other", 0.7, "other", {"kind": "guide"}),
    ]
    retriever = FakeRetriever(hits)

    assert isinstance(retriever, Retriever)
    results = asyncio.run(retriever.search(
        "query",
        namespace="docs",
        filters={"kind": "guide"},
        top_k=1,
    ))

    assert results == [hits[0]]
    assert retriever.calls == [{
        "query": "query",
        "namespace": "docs",
        "filters": {"kind": "guide"},
        "top_k": 1,
    }]
    assert asyncio.run(retriever.search("query", namespace="missing")) == []

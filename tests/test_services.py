import pytest

from backend.domain.models import Chunk, SearchHit
from backend.services.collections import CollectionService
from backend.services.generation import GenerationService
from backend.services.ingestion import IngestionService
from backend.services.retrieval import RetrievalService


class FakeProcessor:
    def __init__(self, chunks):
        self.chunks = chunks
        self.paths = []

    def load_and_split(self, file_path):
        self.paths.append(file_path)
        return self.chunks


class FakeStore:
    def __init__(self, hits=()):
        self.hits = list(hits)
        self.calls = []

    def add(self, chunks, *, namespace):
        self.calls.append(("add", chunks, namespace))

    def search(self, query, *, namespace, top_k, filter_expression=None):
        self.calls.append(("search", query, namespace, top_k, filter_expression))
        return self.hits

    def info(self, namespace):
        self.calls.append(("info", namespace))
        return {"collection_name": namespace}

    def clear(self, namespace):
        self.calls.append(("clear", namespace))
        return namespace != "missing"


class FakeGenerator:
    def __init__(self, answer="answer"):
        self.answer = answer
        self.calls = []

    def generate(self, question, context):
        self.calls.append((question, context))
        return self.answer


def test_ingestion_service_orchestrates_processor_and_store():
    chunks = [Chunk("first"), Chunk("second")]
    processor = FakeProcessor(chunks)
    store = FakeStore()
    service = IngestionService(processor, store)

    assert service.ingest_file("/tmp/doc.txt", namespace="docs") == 2
    assert processor.paths == ["/tmp/doc.txt"]
    assert store.calls == [("add", chunks, "docs")]


def test_ingestion_service_does_not_write_empty_documents():
    store = FakeStore()
    service = IngestionService(FakeProcessor([]), store)

    assert service.ingest_file("/tmp/empty.txt", namespace="docs") == 0
    assert store.calls == []


def test_retrieval_service_applies_threshold_and_preserves_legacy_filter():
    hits = [SearchHit("high", 0.8, "docs"), SearchHit("low", 0.2, "docs")]
    store = FakeStore(hits)
    service = RetrievalService(store, similarity_threshold=0.5)

    results = service.search_sync(
        "query",
        namespace="docs",
        top_k=3,
        filter_expression='kb_id == "docs"',
    )

    assert results == [hits[0]]
    assert store.calls == [("search", "query", "docs", 3, 'kb_id == "docs"')]


def test_retrieval_service_rejects_unimplemented_structured_filters():
    store = FakeStore()
    service = RetrievalService(store)

    with pytest.raises(NotImplementedError, match="K3"):
        service.search_sync("query", namespace="docs", filters={"kb_id": "docs"})

    assert store.calls == []


def test_generation_service_builds_context_and_returns_search_hit_sources():
    hits = [SearchHit("first", 0.9, "docs"), SearchHit("second", 0.8, "docs")]
    retriever = RetrievalService(FakeStore(hits))
    generator = FakeGenerator()
    service = GenerationService(retriever, generator)

    answer = service.answer("question", namespace="docs", top_k=2)

    assert answer.answer == "answer"
    assert answer.question_type == "通用查询"
    assert answer.sources == hits
    assert generator.calls == [(
        "question",
        "参考资料1: first\n\n参考资料2: second",
    )]


def test_generation_service_preserves_legacy_error_answer():
    class FailingRetriever:
        def search_sync(self, *args, **kwargs):
            raise RuntimeError("boom")

    service = GenerationService(FailingRetriever(), FakeGenerator())

    answer = service.answer("question", namespace="docs")

    assert answer.answer == "处理问题时出现错误: boom"
    assert answer.question_type == "错误"
    assert answer.sources == []


def test_collection_service_delegates_info_and_clear():
    store = FakeStore()
    service = CollectionService(store)

    assert service.info("docs") == {"collection_name": "docs"}
    assert service.clear("docs") is True
    assert service.clear("missing") is False
    assert store.calls == [("info", "docs"), ("clear", "docs"), ("clear", "missing")]

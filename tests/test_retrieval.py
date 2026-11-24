from types import SimpleNamespace

from flask import Flask
from langchain_core.documents import Document

from backend import api_integration
from backend.domain.models import Answer, SearchHit
from backend import vector_db_manager as manager_module
from backend.vector_db_manager import VectorDatabaseManager
from backend.vector_retriever import VectorRetriever


def make_manager() -> VectorDatabaseManager:
    manager = VectorDatabaseManager.__new__(VectorDatabaseManager)
    manager.collection_name = "docs"
    manager.vectorstore = None
    manager.milvus_host = "localhost"
    manager.milvus_port = "19530"
    manager.embeddings = object()
    return manager


def test_new_collection_uses_cosine_metric(monkeypatch):
    captured = {}
    store = object()
    monkeypatch.setattr(manager_module.utility, "has_collection", lambda name: False)

    def from_documents(**kwargs):
        captured.update(kwargs)
        return store

    monkeypatch.setattr(manager_module.Milvus, "from_documents", from_documents)
    manager = make_manager()

    manager.add_documents_to_db([Document(page_content="content")])

    assert captured["index_params"]["metric_type"] == "COSINE"
    assert captured["drop_old"] is False
    assert manager.vectorstore is store


def test_manager_passes_metadata_filter_to_milvus():
    class FakeStore:
        def __init__(self):
            self.kwargs = None

        def similarity_search_with_score(self, **kwargs):
            self.kwargs = kwargs
            return [(Document(page_content="matched"), 0.8)]

    manager = make_manager()
    manager.vectorstore = FakeStore()

    results = manager.search(
        "query",
        filter_expression='kb_id == "docs"',
        collection_name="docs",
    )

    assert results[0][1] == 0.8
    assert manager.vectorstore.kwargs["expr"] == 'kb_id == "docs"'


def test_retriever_applies_threshold_without_hiding_filter():
    class FakeManager:
        def __init__(self):
            self.kwargs = None

        def search(self, **kwargs):
            self.kwargs = kwargs
            return [
                (Document(page_content="high"), 0.8),
                (Document(page_content="low"), 0.2),
            ]

    manager = FakeManager()
    retriever = VectorRetriever(manager, similarity_threshold=0.5)

    results = retriever.search_similar_content(
        "query",
        collection_name="docs",
        filter_expression='kb_id == "docs"',
    )

    assert [(doc.page_content, score) for doc, score in results] == [("high", 0.8)]
    assert manager.kwargs["filter_expression"] == 'kb_id == "docs"'


def test_search_api_passes_metadata_filter(monkeypatch):
    class FakeRetriever:
        def __init__(self):
            self.kwargs = None

        def search_similar_content(self, query, **kwargs):
            self.kwargs = kwargs
            return [(Document(page_content="matched", metadata={"kb_id": "docs"}), 0.8)]

    retriever = FakeRetriever()
    monkeypatch.setattr(api_integration, "vector_retriever", retriever)
    app = Flask(__name__)
    app.register_blueprint(api_integration.vector_bp)

    response = app.test_client().post(
        "/api/vector/search",
        json={
            "query": "query",
            "collection_name": "docs",
            "filter_expression": 'kb_id == "docs"',
        },
    )

    assert response.status_code == 200
    assert response.get_json()["results"][0]["score"] == 0.8
    assert retriever.kwargs["filter_expression"] == 'kb_id == "docs"'


def test_query_api_does_not_report_synthetic_confidence(monkeypatch):
    class FakeRetriever:
        def answer_question(self, question, **kwargs):
            return SimpleNamespace(
                answer="answer",
                question_type="通用查询",
                source_documents=[],
                scores=[],
            )

    monkeypatch.setattr(api_integration, "vector_retriever", FakeRetriever())
    app = Flask(__name__)
    app.register_blueprint(api_integration.vector_bp)

    response = app.test_client().post(
        "/api/vector/query",
        json={"question": "question", "collection_name": "docs"},
    )

    assert response.status_code == 200
    assert "confidence" not in response.get_json()


def test_legacy_answer_question_converts_domain_answer_to_answer_result():
    class FakeGenerationService:
        def answer(self, question, **kwargs):
            assert question == "question"
            assert kwargs == {
                "namespace": "docs",
                "top_k": 2,
                "filter_expression": 'kb_id == "docs"',
            }
            return Answer(
                answer="answer",
                question_type="通用查询",
                sources=[SearchHit("evidence", 0.8, "docs", {"source": "guide.md"})],
            )

    retriever = VectorRetriever.__new__(VectorRetriever)
    retriever.generation_service = FakeGenerationService()

    result = retriever.answer_question(
        "question",
        collection_name="docs",
        k=2,
        filter_expression='kb_id == "docs"',
    )

    assert result.answer == "answer"
    assert result.question_type == "通用查询"
    assert result.scores == [0.8]
    assert len(result.source_documents) == 1
    assert result.source_documents[0].page_content == "evidence"
    assert result.source_documents[0].metadata == {"source": "guide.md"}

from types import SimpleNamespace

from langchain_core.documents import Document

from backend.adapters.legacy_documents import LegacyDocumentProcessor
from backend.adapters.openai_generator import OpenAICompatibleGenerator
from backend.domain.models import Chunk
from backend.stores.vector import MilvusVectorStore


class FakeManager:
    def __init__(self):
        self.calls = []
        self.search_results = []
        self.loaded = []
        self.split = []

    def load_document(self, file_path):
        self.calls.append(("load", file_path))
        return self.loaded

    def split_documents(self, documents):
        self.calls.append(("split", documents))
        return self.split

    def add_documents_to_db(self, documents, collection_name):
        self.calls.append(("add", documents, collection_name))

    def search(self, **kwargs):
        self.calls.append(("search", kwargs))
        return self.search_results

    def get_database_info(self, namespace):
        self.calls.append(("info", namespace))
        return {"collection_name": namespace, "document_count": 2}

    def clear_database(self, namespace):
        self.calls.append(("clear", namespace))
        return True


def test_legacy_document_processor_reuses_loading_and_splitting():
    manager = FakeManager()
    manager.loaded = [Document(page_content="loaded")]
    manager.split = [Document(page_content="chunk", metadata={"page": 1})]
    processor = LegacyDocumentProcessor(manager)

    chunks = processor.load_and_split("/tmp/document.txt")

    assert chunks == [Chunk(content="chunk", metadata={"page": 1})]
    assert manager.calls == [
        ("load", "/tmp/document.txt"),
        ("split", manager.loaded),
    ]


def test_milvus_vector_store_converts_documents_and_delegates_operations():
    manager = FakeManager()
    manager.search_results = [(
        Document(
            page_content="matched",
            metadata={"source": "guide.md", "chunk_id": 7, "document_id": 9},
        ),
        0.8,
    )]
    store = MilvusVectorStore(manager)

    store.add([Chunk("chunk", {"page": 1})], namespace="docs")
    hits = store.search(
        "query",
        namespace="docs",
        top_k=3,
        filter_expression='kb_id == "docs"',
    )

    added_documents = manager.calls[0][1]
    assert manager.calls[0][0] == "add"
    assert manager.calls[0][2] == "docs"
    assert added_documents[0].page_content == "chunk"
    assert added_documents[0].metadata == {"page": 1}
    assert manager.calls[1] == ("search", {
        "query": "query",
        "k": 3,
        "filter_expression": 'kb_id == "docs"',
        "collection_name": "docs",
    })
    assert hits[0].content == "matched"
    assert hits[0].score == 0.8
    assert hits[0].namespace == "docs"
    assert hits[0].source == "guide.md"
    assert hits[0].chunk_id == "7"
    assert hits[0].document_id == "9"
    assert store.info("docs") == {"collection_name": "docs", "document_count": 2}
    assert store.clear("docs") is True


def test_openai_generator_preserves_prompt_and_environment_configuration(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.local/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    answer = OpenAICompatibleGenerator().generate("question", "evidence")

    assert answer == "answer"
    assert captured["client"] == {"api_key": "secret", "base_url": "http://llm.local/v1"}
    assert captured["model"] == "test-model"
    assert captured["messages"][1]["content"] == "问题：question\n\n【参考资料】：\nevidence"

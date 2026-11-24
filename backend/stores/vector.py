"""现有 Milvus Manager 的 VectorStore 适配器。"""

from typing import Any

from langchain_core.documents import Document

from backend.domain.models import Chunk, SearchHit
from backend.vector_db_manager import VectorDatabaseManager


class MilvusVectorStore:
    def __init__(self, manager: VectorDatabaseManager):
        self.manager = manager

    def add(self, chunks: list[Chunk], *, namespace: str) -> None:
        documents = [
            Document(page_content=chunk.content, metadata=dict(chunk.metadata))
            for chunk in chunks
        ]
        self.manager.add_documents_to_db(documents, collection_name=namespace)

    def search(
        self,
        query: str,
        *,
        namespace: str,
        top_k: int,
        filter_expression: str | None = None,
    ) -> list[SearchHit]:
        results = self.manager.search(
            query=query,
            k=top_k,
            filter_expression=filter_expression,
            collection_name=namespace,
        )
        return [self._to_hit(document, score, namespace) for document, score in results]

    def info(self, namespace: str) -> dict[str, Any]:
        return self.manager.get_database_info(namespace)

    def clear(self, namespace: str) -> bool:
        return self.manager.clear_database(namespace)

    @staticmethod
    def _to_hit(document: Document, score: float, namespace: str) -> SearchHit:
        metadata = dict(document.metadata)
        return SearchHit(
            content=document.page_content,
            score=score,
            namespace=namespace,
            metadata=metadata,
            source=MilvusVectorStore._optional_string(metadata.get("source")),
            chunk_id=MilvusVectorStore._optional_string(metadata.get("chunk_id")),
            document_id=MilvusVectorStore._optional_string(metadata.get("document_id")),
        )

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return str(value) if value is not None else None

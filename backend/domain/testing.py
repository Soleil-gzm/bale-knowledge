"""可复用的确定性检索测试实现。"""

from typing import Any, Iterable

from .models import SearchHit


class FakeRetriever:
    """按 namespace 和 metadata 等值条件筛选的内存 Retriever。"""

    def __init__(self, hits: Iterable[SearchHit] = ()):
        self.hits = list(hits)
        self.calls: list[dict[str, Any]] = []

    def search_sync(
        self,
        query: str,
        *,
        namespace: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[SearchHit]:
        self.calls.append({
            "query": query,
            "namespace": namespace,
            "filters": dict(filters) if filters is not None else None,
            "top_k": top_k,
        })
        filters = filters or {}
        results = [
            hit
            for hit in self.hits
            if hit.namespace == namespace
            and all(hit.metadata.get(key) == value for key, value in filters.items())
        ]
        return results[:top_k]

    async def search(
        self,
        query: str,
        *,
        namespace: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[SearchHit]:
        return self.search_sync(
            query,
            namespace=namespace,
            filters=filters,
            top_k=top_k,
        )

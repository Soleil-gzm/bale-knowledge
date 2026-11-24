"""独立于 Web 和向量 SDK 的检索应用服务。"""

import asyncio
import logging
from typing import Any

from backend.domain.models import SearchHit
from backend.domain.ports import VectorStore

logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(
        self,
        store: VectorStore,
        similarity_threshold: float = 0.5,
        max_results: int = 10,
    ):
        self.store = store
        self.similarity_threshold = similarity_threshold
        self.max_results = max_results

    def search_sync(
        self,
        query: str,
        *,
        namespace: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
        filter_expression: str | None = None,
    ) -> list[SearchHit]:
        """同步检索；filter_expression 仅用于旧 API 兼容路径。"""
        if filters:
            raise NotImplementedError("结构化 Metadata Filter 将在 K3 实现")

        try:
            results = self.store.search(
                query,
                namespace=namespace,
                top_k=top_k,
                filter_expression=filter_expression,
            )
            hits = [hit for hit in results if hit.score >= self.similarity_threshold]
            logger.info(
                "在命名空间 '%s' 中检索查询: '%s', 返回 %d 个结果",
                namespace,
                query,
                len(hits),
            )
            return hits
        except Exception:
            logger.exception("在命名空间 '%s' 中检索失败", namespace)
            raise

    async def search(
        self,
        query: str,
        *,
        namespace: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[SearchHit]:
        """将同步向量调用卸载到线程，提供 Bale Retriever 契约。"""
        return await asyncio.to_thread(
            self.search_sync,
            query,
            namespace=namespace,
            filters=filters,
            top_k=top_k,
        )

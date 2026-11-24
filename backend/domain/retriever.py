"""供 Bale 等调用方依赖的检索契约。"""

from typing import Any, Protocol, runtime_checkable

from .models import SearchHit


@runtime_checkable
class Retriever(Protocol):
    """不依赖 Web 框架的异步检索接口。"""

    async def search(
        self,
        query: str,
        *,
        namespace: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[SearchHit]:
        """返回指定命名空间内的检索证据。"""
        ...

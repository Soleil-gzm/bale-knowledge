"""集合管理应用服务。"""

from typing import Any

from backend.domain.ports import VectorStore


class CollectionService:
    def __init__(self, store: VectorStore):
        self.store = store

    def info(self, namespace: str) -> dict[str, Any]:
        return self.store.info(namespace)

    def clear(self, namespace: str) -> bool:
        return self.store.clear(namespace)

"""应用服务依赖的外部能力端口。"""

from typing import Any, Protocol

from .models import Chunk, SearchHit


class DocumentProcessor(Protocol):
    def load_and_split(self, file_path: str) -> list[Chunk]:
        """加载并切分内部文件路径指向的文档。"""
        ...


class VectorStore(Protocol):
    def add(self, chunks: list[Chunk], *, namespace: str) -> None:
        """向指定命名空间写入文档块。"""
        ...

    def search(
        self,
        query: str,
        *,
        namespace: str,
        top_k: int,
        filter_expression: str | None = None,
    ) -> list[SearchHit]:
        """检索文档块；filter_expression 仅供旧 API 兼容路径使用。"""
        ...

    def info(self, namespace: str) -> dict[str, Any]:
        """返回指定命名空间的存储信息。"""
        ...

    def clear(self, namespace: str) -> bool:
        """显式清空指定命名空间。"""
        ...


class AnswerGenerator(Protocol):
    def generate(self, question: str, context: str) -> str:
        """根据问题和检索上下文生成答案。"""
        ...

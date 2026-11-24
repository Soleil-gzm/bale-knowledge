"""知识库应用服务使用的轻量领域模型。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Chunk:
    """待写入向量存储的文档块。"""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchHit:
    """一条检索证据；score 是相似度分数，不是答案置信度。"""

    content: str
    score: float
    namespace: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    chunk_id: str | None = None
    document_id: str | None = None


@dataclass(frozen=True, slots=True)
class Answer:
    """生成答案及其检索来源。"""

    answer: str
    question_type: str
    sources: list[SearchHit] = field(default_factory=list)

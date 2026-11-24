"""框架无关的知识库领域契约。"""

from .models import Answer, Chunk, SearchHit
from .retriever import Retriever

__all__ = ["Answer", "Chunk", "Retriever", "SearchHit"]

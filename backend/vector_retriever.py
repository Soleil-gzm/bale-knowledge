"""旧向量检索入口的兼容门面；新代码应直接使用应用服务。"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from langchain_core.documents import Document

from .adapters.openai_generator import OpenAICompatibleGenerator
from .domain.models import SearchHit
from .services.collections import CollectionService
from .services.generation import GenerationService
from .services.retrieval import RetrievalService
from .stores.vector import MilvusVectorStore
from .vector_db_manager import VectorDatabaseManager

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果数据类。"""

    content: str
    score: float
    metadata: Dict[str, Any]
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
            "source": self.source,
        }


@dataclass
class AnswerResult:
    """旧问答入口的返回结构。"""

    answer: str
    question_type: str
    source_documents: List[Document]
    scores: List[float]


class VectorRetriever:
    """将旧 Document API 委托给 Retrieval/Generation Service。"""

    def __init__(
        self,
        db_manager: VectorDatabaseManager,
        similarity_threshold: float = 0.5,
        max_results: int = 10,
    ):
        self.db_manager = db_manager
        self.similarity_threshold = similarity_threshold
        self.max_results = max_results
        self.vector_store = MilvusVectorStore(db_manager)
        self.retrieval_service = RetrievalService(
            self.vector_store,
            similarity_threshold=similarity_threshold,
            max_results=max_results,
        )
        self.generation_service = GenerationService(
            self.retrieval_service,
            OpenAICompatibleGenerator(),
        )
        self.collection_service = CollectionService(self.vector_store)

    def search_similar_content(
        self,
        query: str,
        collection_name: str,
        k: int = None,
        filter_expression: str = None,
        include_scores: bool = True,
    ) -> List[Tuple[Document, float]]:
        """保留旧 `(Document, score)` 返回结构。"""
        hits = self.retrieval_service.search_sync(
            query,
            namespace=collection_name,
            top_k=self.max_results if k is None else k,
            filter_expression=filter_expression,
        )
        return [(self._to_document(hit), hit.score) for hit in hits]

    def answer_question(
        self,
        question: str,
        collection_name: str,
        k: int = 5,
        filter_expression: str = None,
    ) -> AnswerResult:
        """保留旧 AnswerResult，同时由 GenerationService 编排。"""
        result = self.generation_service.answer(
            question,
            namespace=collection_name,
            top_k=k,
            filter_expression=filter_expression,
        )
        return AnswerResult(
            answer=result.answer,
            question_type=result.question_type,
            source_documents=[self._to_document(hit) for hit in result.sources],
            scores=[hit.score for hit in result.sources],
        )

    def _generate_answer_with_llm(self, question: str, context: str) -> str:
        return self.generation_service.generator.generate(question, context)

    def get_statistics(self, collection_name: str) -> Dict[str, Any]:
        db_info = self.collection_service.info(collection_name)
        return {
            "database_info": db_info,
            "similarity_threshold": self.similarity_threshold,
            "max_results": self.max_results,
            "retriever_status": "active" if db_info.get("is_initialized") else "inactive",
        }

    @staticmethod
    def _to_document(hit: SearchHit) -> Document:
        return Document(page_content=hit.content, metadata=dict(hit.metadata))


class QuestionClassifier:
    @classmethod
    def classify_question(cls, question: str) -> str:
        return GenerationService.classify_question(question)


def main():
    """手动测试旧问答入口。"""
    try:
        db_manager = VectorDatabaseManager(
            milvus_host="localhost",
            milvus_port="19530",
        )
        retriever = VectorRetriever(db_manager)
        collection_name = "agent_rag"
        print("向量系统初始化成功")
    except Exception as exc:
        print(f"向量系统初始化失败: {exc}")
        return

    info = db_manager.get_database_info()
    if not info.get("is_initialized"):
        print(f"集合 '{collection_name}' 不存在，正在创建并添加数据...")
        print("请先手动上传数据以进行测试。")

    test_questions = [
        "Milvus 是什么？",
        "如何将文本上传到向量数据库？",
        "RAG 工作流程的关键步骤是什么？",
    ]

    print("\n--- 测试问答功能 ---")
    for question in test_questions:
        print(f"\n问题: {question}")
        result = retriever.answer_question(question, collection_name=collection_name)
        print(f"回答: {result.answer}")
        print(f"检索分数: {result.scores}")
        print(f"问题类型: {result.question_type}")
        print(f"参考来源数: {len(result.source_documents)}")


if __name__ == "__main__":
    main()

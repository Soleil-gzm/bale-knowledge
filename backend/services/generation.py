"""检索与答案生成解耦的应用服务。"""

import logging
from typing import Any

from backend.domain.models import Answer
from backend.domain.ports import AnswerGenerator
from backend.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)


class GenerationService:
    def __init__(self, retriever: RetrievalService, generator: AnswerGenerator):
        self.retriever = retriever
        self.generator = generator

    def answer(
        self,
        question: str,
        *,
        namespace: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
        filter_expression: str | None = None,
    ) -> Answer:
        try:
            question_type = self.classify_question(question)
            sources = self.retriever.search_sync(
                question,
                namespace=namespace,
                filters=filters,
                top_k=top_k,
                filter_expression=filter_expression,
            )
            context = "\n\n".join(
                f"参考资料{index}: {hit.content}"
                for index, hit in enumerate(sources, start=1)
            )
            answer = self.generator.generate(question, context)
            return Answer(
                answer=answer,
                question_type=question_type,
                sources=sources,
            )
        except Exception as exc:
            logger.error("回答问题失败: %s", exc)
            return Answer(
                answer=f"处理问题时出现错误: {exc}",
                question_type="错误",
                sources=[],
            )

    @staticmethod
    def classify_question(question: str) -> str:
        return "通用查询"

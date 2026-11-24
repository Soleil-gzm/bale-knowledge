"""具体外部依赖与应用服务的唯一组装点。"""

from dataclasses import dataclass

from .adapters.legacy_documents import LegacyDocumentProcessor
from .adapters.openai_generator import OpenAICompatibleGenerator
from .services.collections import CollectionService
from .services.generation import GenerationService
from .services.ingestion import IngestionService
from .services.retrieval import RetrievalService
from .stores.vector import MilvusVectorStore
from .vector_db_manager import VectorDatabaseManager


@dataclass(frozen=True, slots=True)
class ServiceContainer:
    ingestion: IngestionService
    retrieval: RetrievalService
    generation: GenerationService
    collections: CollectionService


def create_services(
    milvus_host: str | None = None,
    milvus_port: str | None = None,
    embedding_model: str | None = None,
    dashscope_api_key: str | None = None,
) -> ServiceContainer:
    manager = VectorDatabaseManager(
        milvus_host=milvus_host,
        milvus_port=milvus_port,
        embedding_model=embedding_model,
        dashscope_api_key=dashscope_api_key,
    )
    processor = LegacyDocumentProcessor(manager)
    store = MilvusVectorStore(manager)
    retrieval = RetrievalService(store)
    return ServiceContainer(
        ingestion=IngestionService(processor, store),
        retrieval=retrieval,
        generation=GenerationService(retrieval, OpenAICompatibleGenerator()),
        collections=CollectionService(store),
    )

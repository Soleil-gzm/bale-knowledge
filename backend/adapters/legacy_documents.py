"""复用现有文档加载与切分实现的适配器。"""

from backend.domain.models import Chunk
from backend.vector_db_manager import VectorDatabaseManager


class LegacyDocumentProcessor:
    def __init__(self, manager: VectorDatabaseManager):
        self.manager = manager

    def load_and_split(self, file_path: str) -> list[Chunk]:
        documents = self.manager.load_document(file_path)
        split_documents = self.manager.split_documents(documents)
        return [
            Chunk(content=document.page_content, metadata=dict(document.metadata))
            for document in split_documents
        ]

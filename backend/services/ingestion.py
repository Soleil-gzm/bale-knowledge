"""文档入库应用服务。"""

from backend.domain.ports import DocumentProcessor, VectorStore


class IngestionService:
    def __init__(self, processor: DocumentProcessor, store: VectorStore):
        self.processor = processor
        self.store = store

    def ingest_file(self, file_path: str, *, namespace: str) -> int:
        """处理一个内部文件并返回写入的 Chunk 数。"""
        chunks = self.processor.load_and_split(file_path)
        if not chunks:
            return 0

        self.store.add(chunks, namespace=namespace)
        return len(chunks)

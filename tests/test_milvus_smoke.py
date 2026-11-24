import os
from uuid import uuid4

import pytest
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend import vector_db_manager as manager_module
from backend.vector_db_manager import VectorDatabaseManager


pytestmark = pytest.mark.skipif(
    os.getenv("MILVUS_INTEGRATION") != "1",
    reason="Set MILVUS_INTEGRATION=1 with a local Milvus server to run this smoke test",
)


class ConstantEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [self._vector() for _ in texts]

    def embed_query(self, text):
        return self._vector()

    @staticmethod
    def _vector():
        return [1.0] + [0.0] * 15


def test_milvus_txt_lifecycle_smoke(tmp_path):
    manager = VectorDatabaseManager.__new__(VectorDatabaseManager)
    manager.milvus_host = os.getenv("MILVUS_HOST", "127.0.0.1")
    manager.milvus_port = os.getenv("MILVUS_PORT", "19530")
    manager.collection_name = f"bale_k0_{uuid4().hex}"
    manager.embeddings = ConstantEmbeddings()
    manager.text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,
        chunk_overlap=20,
        length_function=len,
    )
    manager.vectorstore = None
    manager._connect_to_milvus()

    path = tmp_path / "smoke.txt"
    path.write_text("Bale Knowledge Milvus lifecycle smoke test", encoding="utf-8")

    try:
        assert manager.process_file(str(path), manager.collection_name) is True
        results = manager.search("Bale Knowledge", collection_name=manager.collection_name)
        assert results
        assert results[0][0].page_content
        assert manager.clear_database(manager.collection_name) is True
        assert not manager_module.utility.has_collection(manager.collection_name)
    finally:
        if manager_module.utility.has_collection(manager.collection_name):
            manager.clear_database(manager.collection_name)

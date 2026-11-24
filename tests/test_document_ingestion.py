from langchain_text_splitters import RecursiveCharacterTextSplitter
from reportlab.pdfgen.canvas import Canvas

from backend.vector_db_manager import VectorDatabaseManager


def make_manager() -> VectorDatabaseManager:
    manager = VectorDatabaseManager.__new__(VectorDatabaseManager)
    manager.chunk_size = 80
    manager.chunk_overlap = 10
    manager.text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=80,
        chunk_overlap=10,
        length_function=len,
    )
    return manager


def test_txt_ingestion_loads_splits_and_stores_document(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("Bale Knowledge 文档入库。\n" * 8, encoding="utf-8")
    manager = make_manager()
    stored = {}

    def add_documents(documents, collection_name=None):
        stored["documents"] = documents
        stored["collection_name"] = collection_name

    manager.add_documents_to_db = add_documents

    assert manager.process_file(str(path), "docs") is True
    assert stored["collection_name"] == "docs"
    assert len(stored["documents"]) > 1
    assert "Bale Knowledge" in stored["documents"][0].page_content


def test_pdf_ingestion_extracts_text(tmp_path):
    path = tmp_path / "report.pdf"
    canvas = Canvas(str(path))
    canvas.drawString(72, 720, "Bale Knowledge PDF smoke test")
    canvas.save()
    manager = make_manager()

    documents = manager.load_document(str(path))

    assert documents
    assert "Bale Knowledge PDF smoke test" in documents[0].page_content

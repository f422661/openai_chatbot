from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import text

from config import DOCUMENTS_DIR
from db import engine, vector_literal
from embeddings import embed_text


CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
SUPPORTED_EXTENSIONS = {".md", ".pdf", ".txt"}


def chunk_text(content: str) -> list[str]:
    normalized = "\n".join(line.strip() for line in content.splitlines())
    normalized = "\n".join(part for part in normalized.splitlines() if part)

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + CHUNK_SIZE, len(normalized))
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(normalized):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)

    return chunks


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8").strip()

    if suffix == ".pdf":
        reader = PdfReader(path)
        pages = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages.append(f"[{path.name} page {page_number}]\n{text}")
        return "\n\n".join(pages).strip()

    return ""


def iter_document_chunks(documents_dir: Path) -> list[str]:
    chunks: list[str] = []
    for path in sorted(documents_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        content = read_document(path)
        if not content:
            continue
        chunks.extend(chunk_text(content))
    return chunks


def ingest_documents() -> int:
    documents_dir = Path(DOCUMENTS_DIR)
    if not documents_dir.exists():
        raise FileNotFoundError(f"Documents directory not found: {documents_dir}")

    chunks = iter_document_chunks(documents_dir)
    insert_statement = text(
        """
        INSERT INTO document_chunks (content, embedding)
        VALUES (:content, CAST(:embedding AS vector))
        """
    )

    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE document_chunks RESTART IDENTITY"))
        for chunk in chunks:
            connection.execute(
                insert_statement,
                {
                    "content": chunk,
                    "embedding": vector_literal(embed_text(chunk)),
                },
            )

    return len(chunks)


if __name__ == "__main__":
    count = ingest_documents()
    print(f"Ingested {count} chunks.")

from sqlalchemy import create_engine, text

from config import DATABASE_URL


engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def fetch_top_chunks(embedding: list[float], limit: int) -> list[str]:
    query = text(
        """
        SELECT content
        FROM document_chunks
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
        """
    )

    with engine.connect() as connection:
        rows = connection.execute(
            query,
            {"embedding": vector_literal(embedding), "limit": limit},
        ).fetchall()

    return [row.content for row in rows]

from sqlalchemy import create_engine, text

from config import DATABASE_URL


engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def fetch_top_matches(embedding: list[float], limit: int) -> list[dict]:
    query = text(
        """
        WITH ranked_chunks AS MATERIALIZED (
            SELECT id, content, embedding <=> CAST(:embedding AS vector) AS distance
            FROM document_chunks
        )
        SELECT id, content, distance
        FROM ranked_chunks
        ORDER BY distance
        LIMIT :limit
        """
    )

    with engine.connect() as connection:
        rows = connection.execute(
            query,
            {"embedding": vector_literal(embedding), "limit": limit},
        ).fetchall()

    return [
        {
            "id": row.id,
            "content": row.content,
            "distance": float(row.distance),
        }
        for row in rows
    ]


def fetch_top_chunks(embedding: list[float], limit: int) -> list[str]:
    return [match["content"] for match in fetch_top_matches(embedding, limit)]

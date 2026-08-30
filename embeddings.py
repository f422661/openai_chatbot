from openai import OpenAI

from config import EMBEDDING_DIM, EMBEDDING_MODEL, OPENAI_API_KEY


def embed_text(text: str) -> list[float]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    response = OpenAI(api_key=OPENAI_API_KEY).embeddings.create(
        model=EMBEDDING_MODEL,
        input=str(text),
        dimensions=EMBEDDING_DIM,
        encoding_format="float",
    )
    embedding = response.data[0].embedding
    if len(embedding) != EMBEDDING_DIM:
        raise ValueError(
            f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, "
            f"got {len(embedding)}"
        )
    return embedding


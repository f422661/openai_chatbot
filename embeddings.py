from functools import lru_cache

from sentence_transformers import SentenceTransformer

from config import EMBEDDING_DIM, EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


def embed_text(text: str) -> list[float]:
    embedding = get_embedding_model().encode(
        [str(text)],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0]
    if embedding.shape != (EMBEDDING_DIM,):
        raise ValueError(
            f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, "
            f"got {embedding.shape[0]}"
        )
    return embedding.tolist()

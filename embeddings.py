from functools import lru_cache

from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


def embed_text(text: str) -> list[float]:
    embedding = get_embedding_model().encode(
        [str(text)],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0]
    return embedding.tolist()

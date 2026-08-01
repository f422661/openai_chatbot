import json
import uuid
import numpy as np
import redis
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query


from config import REDIS_URL, CACHE_TTL, SIMILARITY_THRESHOLD
from embeddings import embed_text

redis_client = redis.Redis.from_url(REDIS_URL)

INDEX_NAME = "idx:semantic_cache"
VECTOR_DIM = 384


def init_semantic_cache_index() -> bool:
    """Ensure the Redis vector index exists."""
    try:
        redis_client.ft(INDEX_NAME).info()
        return True
    except Exception:
        try:
            schema = (
                TextField("question"),
                TextField("answer"),
                TextField("context"),
                VectorField(
                    "embedding",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": VECTOR_DIM,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
            )
            definition = IndexDefinition(
                prefix=["semantic_cache:"],
                index_type=IndexType.HASH,
            )
            redis_client.ft(INDEX_NAME).create_index(fields=schema, definition=definition)
            print("[CACHE] Redis Semantic Cache index created.")
            return True
        except Exception as e:
            print(f"[CACHE WARNING] Could not create Redis index: {e}")
            return False


def get_semantic_cache(question: str) -> dict | None:
    """Query Redis for a semantically similar cached question."""
    try:
        if not init_semantic_cache_index():
            return None

        question_embedding = embed_text(question)
        query_vector = np.array(question_embedding, dtype=np.float32).tobytes()

        q = (
            Query("*=>[KNN 1 @embedding $vec AS distance]")
            .sort_by("distance")
            .paging(0, 1)
            .return_fields("question", "answer", "context", "distance")
            .dialect(2)
        )

        results = redis_client.ft(INDEX_NAME).search(
            q, query_params={"vec": query_vector}
        )

        if results.docs:
            doc = results.docs[0]
            distance = float(doc.distance)
            similarity = 1.0 - distance

            if similarity >= SIMILARITY_THRESHOLD:
                print(
                    f"[CACHE HIT] Similarity: {similarity:.4f} >= {SIMILARITY_THRESHOLD} "
                    f"| Query: '{question}' | Matched: '{doc.question}'"
                )
                return {
                    "answer": doc.answer,
                    "context": json.loads(doc.context),
                    "similarity": similarity,
                    "matched_question": doc.question,
                }
            else:
                print(
                    f"[CACHE MISS] Best Similarity: {similarity:.4f} < {SIMILARITY_THRESHOLD}"
                )
    except Exception as e:
        print(f"[CACHE WARNING] Error retrieving cache: {e}")

    return None


def set_semantic_cache(
    question: str,
    answer: str,
    context: list[str],
    ttl: int = CACHE_TTL,
) -> None:
    """Store question, embedding, answer, and context into Redis."""
    try:
        if not init_semantic_cache_index():
            return

        question_embedding = embed_text(question)
        vector_bytes = np.array(question_embedding, dtype=np.float32).tobytes()

        cache_id = f"semantic_cache:{uuid.uuid4().hex}"

        pipe = redis_client.pipeline()
        pipe.hset(
            cache_id,
            mapping={
                "question": question,
                "answer": answer,
                "context": json.dumps(context, ensure_ascii=False),
                "embedding": vector_bytes,
            },
        )
        pipe.expire(cache_id, ttl)
        pipe.execute()
        print(f"[CACHE STORED] Question: '{question}' cached for {ttl}s.")
    except Exception as e:
        print(f"[CACHE WARNING] Error storing cache: {e}")

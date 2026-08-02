import json
import logging
import uuid

import numpy as np
import redis
from redis.exceptions import ResponseError
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query


from config import (
    CACHE_TTL,
    CACHE_VERSION,
    DEBUG_VECTOR_LOGS,
    EMBEDDING_DIM,
    REDIS_URL,
    SIMILARITY_THRESHOLD,
)

redis_client = redis.Redis.from_url(REDIS_URL)
logger = logging.getLogger("uvicorn.error")

INDEX_NAME = f"idx:semantic_cache:{CACHE_VERSION}"
CACHE_KEY_PREFIX = f"semantic_cache:{CACHE_VERSION}:"


def init_semantic_cache_index() -> bool:
    """Ensure the Redis vector index exists."""
    try:
        redis_client.ft(INDEX_NAME).info()
        return True
    except ResponseError as e:
        if "unknown index name" not in str(e).lower():
            logger.warning("Could not inspect Redis cache index: %s", e)
            return False
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
                        "DIM": EMBEDDING_DIM,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
            )
            definition = IndexDefinition(
                prefix=[CACHE_KEY_PREFIX],
                index_type=IndexType.HASH,
            )
            redis_client.ft(INDEX_NAME).create_index(fields=schema, definition=definition)
            logger.info("Redis semantic cache index created: %s", INDEX_NAME)
            return True
        except ResponseError as create_error:
            if "index already exists" in str(create_error).lower():
                return True
            logger.warning("Could not create Redis cache index: %s", create_error)
            return False
    except redis.RedisError as e:
        logger.warning("Could not connect to Redis cache: %s", e)
        return False


def get_semantic_cache(
    question: str,
    question_embedding: list[float],
) -> dict | None:
    """Query Redis for a semantically similar cached question."""
    try:
        if not init_semantic_cache_index():
            return None

        query_vector_array = np.array(question_embedding, dtype=np.float32)
        query_vector = query_vector_array.tobytes()

        if DEBUG_VECTOR_LOGS:
            logger.info(
                "Query vector | question=%r shape=%s first_10=%s",
                question,
                query_vector_array.shape,
                query_vector_array[:10].tolist(),
            )

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

            if DEBUG_VECTOR_LOGS:
                _log_vector_comparison(doc, query_vector_array, distance, similarity)

            if similarity >= SIMILARITY_THRESHOLD:
                logger.info(
                    "Cache hit | similarity=%.4f threshold=%.4f query=%r matched=%r",
                    similarity,
                    SIMILARITY_THRESHOLD,
                    question,
                    doc.question,
                )
                return {
                    "answer": doc.answer,
                    "context": json.loads(doc.context),
                    "similarity": similarity,
                    "matched_question": doc.question,
                }
            else:
                logger.info(
                    "Cache miss | best_similarity=%.4f threshold=%.4f",
                    similarity,
                    SIMILARITY_THRESHOLD,
                )
    except Exception as e:
        logger.warning("Error retrieving semantic cache: %s", e)

    return None


def set_semantic_cache(
    question: str,
    question_embedding: list[float],
    answer: str,
    context: list[str],
    ttl: int = CACHE_TTL,
) -> None:
    """Store question, embedding, answer, and context into Redis."""
    try:
        if not init_semantic_cache_index():
            return

        vector_bytes = np.array(question_embedding, dtype=np.float32).tobytes()

        cache_id = f"{CACHE_KEY_PREFIX}{uuid.uuid4().hex}"

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
        logger.info("Cache stored | question=%r ttl=%ss", question, ttl)
    except Exception as e:
        logger.warning("Error storing semantic cache: %s", e)


def _log_vector_comparison(
    doc,
    query_vector: np.ndarray,
    redis_distance: float,
    redis_similarity: float,
) -> None:
    stored_vector_bytes = redis_client.hget(doc.id, "embedding")
    if stored_vector_bytes is None:
        logger.warning("Embedding not found for Redis key: %s", doc.id)
        return

    stored_vector = np.frombuffer(stored_vector_bytes, dtype=np.float32)
    query_norm = np.linalg.norm(query_vector)
    stored_norm = np.linalg.norm(stored_vector)

    if query_norm > 0 and stored_norm > 0:
        python_similarity = float(
            np.dot(query_vector, stored_vector) / (query_norm * stored_norm)
        )
        python_distance = 1.0 - python_similarity
    else:
        python_similarity = float("nan")
        python_distance = float("nan")

    logger.info(
        "Vector result | key=%s matched=%r stored_shape=%s stored_first_10=%s "
        "redis_distance=%s redis_similarity=%s python_distance=%s "
        "python_similarity=%s",
        doc.id,
        doc.question,
        stored_vector.shape,
        stored_vector[:10].tolist(),
        redis_distance,
        redis_similarity,
        python_distance,
        python_similarity,
    )

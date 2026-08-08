"""Embedding module using Gemini Embedding 2 + Neo4j Vector Index."""
import logging
from typing import Optional

from app.config import settings
from app.lib.db_operations import run_query

logger = logging.getLogger(__name__)

DEFAULT_DIMENSIONS = 768

VECTOR_INDEXES = {
    "support_log_vector_index": {"label": "SupportLog", "property": "embedding", "dimensions": DEFAULT_DIMENSIONS},
    "care_preference_embedding": {"label": "CarePreference", "property": "embedding", "dimensions": DEFAULT_DIMENSIONS},
    "ng_action_embedding": {"label": "NgAction", "property": "embedding", "dimensions": DEFAULT_DIMENSIONS},
    "client_summary_embedding": {"label": "Client", "property": "summaryEmbedding", "dimensions": DEFAULT_DIMENSIONS},
    "meeting_record_embedding": {"label": "MeetingRecord", "property": "embedding", "dimensions": DEFAULT_DIMENSIONS},
    "meeting_record_text_embedding": {"label": "MeetingRecord", "property": "textEmbedding", "dimensions": DEFAULT_DIMENSIONS},
}

_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            from google import genai
            api_key = settings.gemini_api_key or settings.google_api_key
            _client = genai.Client(api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
    return _client


async def embed_text(
    text: str,
    task_type: str = "RETRIEVAL_DOCUMENT",
    dimensions: int = DEFAULT_DIMENSIONS,
) -> Optional[list[float]]:
    """Generate embedding using Gemini Embedding 2."""
    if not text or not text.strip():
        return None
    client = _get_client()
    if not client:
        return None
    try:
        response = client.models.embed_content(
            model=settings.embedding_model,
            contents=text,
            config={"task_type": task_type, "output_dimensionality": dimensions},
        )
        return response.embeddings[0].values
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return None


async def embed_texts_batch(
    texts: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
    dimensions: int = DEFAULT_DIMENSIONS,
) -> list[Optional[list[float]]]:
    """Batch embedding generation."""
    results = []
    for text in texts:
        emb = await embed_text(text, task_type, dimensions)
        results.append(emb)
    return results


def semantic_search(
    query_embedding: list[float],
    index_name: str = "support_log_embedding",
    top_k: int = 10,
) -> list[dict]:
    """Search Neo4j vector index."""
    idx = VECTOR_INDEXES.get(index_name)
    if not idx:
        return []
    query = """
    CALL db.index.vector.queryNodes($index_name, $top_k, $query_embedding)
    YIELD node, score
    RETURN node, score
    ORDER BY score DESC
    """
    records = run_query(query, {
        "index_name": index_name,
        "top_k": top_k,
        "query_embedding": query_embedding,
    })
    return [{"node": dict(r["node"]), "score": r["score"]} for r in records]


def ensure_vector_indexes() -> None:
    """Create vector indexes if they don't exist (idempotent)."""
    for name, idx in VECTOR_INDEXES.items():
        query = f"""
        CREATE VECTOR INDEX {name} IF NOT EXISTS
        FOR (n:{idx['label']})
        ON (n.{idx['property']})
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {idx['dimensions']},
            `vector.similarity_function`: 'cosine'
        }}}}
        """
        try:
            run_query(query)
        except Exception as e:
            logger.warning("Failed to create index %s: %s", name, e)
    logger.info("Ensured %d vector indexes", len(VECTOR_INDEXES))

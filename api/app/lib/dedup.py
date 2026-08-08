"""Deduplication utilities for Neo4j nodes.

Text normalization functions (normalize_name, normalize_text, normalize_condition)
are defined in app.lib.normalize to avoid circular imports with db_operations.
They are re-exported here for backward compatibility.
"""
import logging
from difflib import SequenceMatcher
from typing import Any

from app.lib.embedding import embed_text
from app.lib.db_operations import run_query

# Re-export normalization functions from normalize module for backward compat.
from app.lib.normalize import (  # noqa: F401
    normalize_name,
    normalize_text,
    normalize_condition,
    name_to_kana,
    CONDITION_ALIASES,
)

logger = logging.getLogger(__name__)

# Map label → text property used in vector index
_LABEL_TEXT_PROPERTY: dict[str, str] = {
    "NgAction": "action",
    "CarePreference": "instruction",
    "SupportLog": "action",
}


def find_similar_by_kana(
    name: str,
    label: str = "Client",
    threshold: float = 0.8,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Find existing nodes with similar kana (phonetic) readings.

    Uses SequenceMatcher to compare hiragana readings converted by name_to_kana().
    Returns list of dicts: {name, kana, similarity, nodeId, matchType}
    sorted by similarity descending.

    Args:
        name: Input name to search for (kanji, kana, or mixed).
        label: Neo4j node label to search. Must be a valid Python identifier
            to prevent Cypher injection. Defaults to "Client".
        threshold: Minimum SequenceMatcher ratio (0–1). Defaults to 0.8.
        limit: Maximum number of results to return. Defaults to 5.

    Returns:
        List of matching node dicts sorted by similarity descending.
        Empty list on empty/invalid input or any error.
    """
    if not name or not name.strip():
        return []

    # Validate label to prevent Cypher injection
    if not label.isidentifier():
        logger.warning("Invalid label for kana search: %r", label)
        return []

    input_kana = name_to_kana(name)
    if not input_kana:
        return []

    try:
        rows = run_query(
            f"MATCH (n:{label}) WHERE n.kana IS NOT NULL "
            f"RETURN n.name AS name, n.kana AS kana, elementId(n) AS nodeId "
            f"LIMIT 500",
            {},
        )
    except Exception as exc:
        logger.warning("find_similar_by_kana query failed: %s", exc)
        return []

    candidates = []
    for row in rows:
        existing_kana = row.get("kana", "")
        if not existing_kana:
            continue
        ratio = SequenceMatcher(None, input_kana, existing_kana).ratio()
        if ratio >= threshold:
            candidates.append({
                "name": row["name"],
                "kana": existing_kana,
                "similarity": round(ratio, 3),
                "nodeId": row["nodeId"],
                "matchType": "kana",
            })

    candidates.sort(key=lambda x: x["similarity"], reverse=True)
    return candidates[:limit]


async def find_semantic_duplicates(
    text: str,
    label: str,
    index_name: str,
    threshold: float = 0.85,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search for semantically similar existing nodes using vector index.

    Returns list of dicts with keys: text, score, nodeId.
    Only results with score >= threshold are returned.

    Args:
        text: The input text to search for duplicates of.
        label: The Neo4j node label (e.g. "NgAction", "CarePreference").
        index_name: The name of the Neo4j vector index to query.
        threshold: Minimum cosine similarity score (0–1). Defaults to 0.85.
        top_k: Maximum candidates to retrieve from the index. Defaults to 5.

    Returns:
        List of matching node dicts, ordered by score descending. Empty list
        on empty input, missing embedding, or any error.
    """
    if not text:
        return []

    try:
        embedding = await embed_text(text, task_type="SEMANTIC_SIMILARITY")
        if embedding is None:
            return []

        text_prop = _LABEL_TEXT_PROPERTY.get(label, "text")
        # Defensive check: text_prop must be a safe identifier (alpha + underscore only)
        # to prevent Cypher injection via f-string. Values come from _LABEL_TEXT_PROPERTY
        # which is hardcoded, but we validate anyway for defence-in-depth.
        if not text_prop.isidentifier():
            logger.warning("Invalid text_prop %r for label %s", text_prop, label)
            return []
        cypher = (
            "CALL db.index.vector.queryNodes($index_name, $top_k, $embedding) "
            "YIELD node, score "
            "WHERE score >= $threshold "
            f"RETURN node.{text_prop} AS text, score, elementId(node) AS nodeId "
            "ORDER BY score DESC"
        )
        rows = run_query(
            cypher,
            {
                "index_name": index_name,
                "top_k": top_k,
                "embedding": embedding,
                "threshold": threshold,
            },
        )
        # Filter by threshold in Python as a safety net (Cypher WHERE also filters,
        # but this guards against driver versions that may not pass parameters to YIELD)
        return [r for r in (rows or []) if r.get("score", 0) >= threshold]

    except Exception as exc:
        logger.warning(
            "find_semantic_duplicates failed for label=%s index=%s: %s",
            label,
            index_name,
            exc,
        )
        return []

"""Deduplication utilities for Neo4j nodes.

Text normalization functions (normalize_name, normalize_text, normalize_condition)
are defined in app.lib.normalize to avoid circular imports with db_operations.
They are re-exported here for backward compatibility.
"""
import logging
from difflib import SequenceMatcher
from typing import Any

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

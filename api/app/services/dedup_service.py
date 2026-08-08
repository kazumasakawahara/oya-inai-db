"""Service layer for pre-registration duplicate detection."""
from __future__ import annotations

import logging
from typing import Any

from app.lib.db_operations import run_query, MERGE_KEYS
from app.lib.dedup import find_similar_by_kana, find_semantic_duplicates
from app.lib.normalize import normalize_name, normalize_text, normalize_condition
from app.schemas.dedup import DedupCandidate, DedupCheckResponse

logger = logging.getLogger(__name__)

# Labels that support kana-based fuzzy matching
_KANA_LABELS = {"Client", "KeyPerson", "Supporter", "Guardian"}

# Labels + config for semantic matching
_SEMANTIC_CONFIG = {
    "NgAction": {"index": "ng_action_embedding", "prop": "action"},
    "CarePreference": {"index": "care_preference_embedding", "prop": "instruction"},
}


async def check_duplicates(
    label: str,
    properties: dict[str, Any],
) -> DedupCheckResponse:
    """Run all applicable duplicate checks for a given node."""
    candidates: list[DedupCandidate] = []
    checks: list[str] = []

    # 1. Exact match check (for MERGE-key labels)
    if label in MERGE_KEYS:
        checks.append("exact")
        exact = _check_exact_match(label, properties)
        candidates.extend(exact)

    # 2. Kana fuzzy match (for name-based labels)
    if label in _KANA_LABELS:
        name = properties.get("name", "")
        if name:
            checks.append("kana")
            kana_matches = find_similar_by_kana(name, label=label, threshold=0.8)
            for m in kana_matches:
                # Skip if already found as exact match
                if not any(c.nodeId == m["nodeId"] for c in candidates):
                    candidates.append(DedupCandidate(
                        name=m["name"],
                        similarity=m["similarity"],
                        matchType="kana",
                        nodeId=m["nodeId"],
                    ))

    # 3. Semantic match (for embeddable labels)
    config = _SEMANTIC_CONFIG.get(label)
    if config:
        text = properties.get(config["prop"], "")
        if text:
            checks.append("semantic")
            try:
                sem_matches = await find_semantic_duplicates(
                    text, label, config["index"], threshold=0.85
                )
                for m in sem_matches:
                    if not any(c.nodeId == m["nodeId"] for c in candidates):
                        candidates.append(DedupCandidate(
                            text=m["text"],
                            similarity=m["score"],
                            matchType="semantic",
                            nodeId=m["nodeId"],
                        ))
            except Exception as exc:
                logger.warning("Semantic dedup check failed: %s", exc)

    # Sort by similarity descending
    candidates.sort(key=lambda c: c.similarity, reverse=True)

    return DedupCheckResponse(
        hasCandidates=len(candidates) > 0,
        candidates=candidates,
        checkedLabel=label,
        checksPerformed=checks,
    )


def _check_exact_match(label: str, properties: dict[str, Any]) -> list[DedupCandidate]:
    """Check for exact MERGE-key match."""
    keys = MERGE_KEYS.get(label, [])
    if not keys:
        return []

    # Build match conditions
    conditions = []
    params = {}
    for k in keys:
        val = properties.get(k)
        if not val:
            return []  # Missing merge key = can't check
        # Normalize the value
        if k == "name":
            if label == "Condition":
                val = normalize_condition(val)
            else:
                val = normalize_name(val)
        else:
            val = normalize_text(str(val))
        param_name = f"p_{k}"
        conditions.append(f"n.{k} = ${param_name}")
        params[param_name] = val

    # Validate label
    if not label.isidentifier():
        return []

    where = " AND ".join(conditions)
    try:
        rows = run_query(
            f"MATCH (n:{label}) WHERE {where} "
            f"RETURN n.name AS name, elementId(n) AS nodeId LIMIT 5",
            params,
        )
    except Exception as exc:
        logger.warning("Exact match check failed: %s", exc)
        return []

    return [
        DedupCandidate(
            name=row.get("name"),
            similarity=1.0,
            matchType="exact",
            nodeId=row["nodeId"],
        )
        for row in rows
    ]

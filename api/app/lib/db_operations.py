"""Neo4j database operations: connection management, query execution, graph registration."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from neo4j import GraphDatabase, Driver
from neo4j.time import Date as Neo4jDate, DateTime as Neo4jDateTime, Time as Neo4jTime, Duration as Neo4jDuration

from app.config import settings
from app.lib.normalize import normalize_name, normalize_text, normalize_condition, name_to_kana

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Labels whose "name" merge key should be normalized with normalize_name()
# (strips whitespace, fullwidth chars, and Japanese honorific suffixes).
_NAME_NORMALIZED_LABELS: set[str] = {
    "Client", "Supporter", "KeyPerson", "Guardian",
    "Hospital", "Organization", "ServiceProvider",
    "Doctor", "Relative", "Identity",
}

MERGE_KEYS: dict[str, list[str]] = {
    "Client": ["name"],
    "Supporter": ["name"],
    "NgAction": ["action"],
    "CarePreference": ["category", "instruction"],
    "Condition": ["name"],
    "KeyPerson": ["name"],
    "Organization": ["name"],
    "ServiceProvider": ["name"],
    "Hospital": ["name"],
    "Doctor": ["name"],
    "Guardian": ["name"],
    "Relative": ["name"],
    "Identity": ["name", "dob"],
    "Certificate": ["type", "grade"],
}

# CareRole: create per client/caregiver scope (ENT-16 — merging onto a shared
# same-name node makes uncovered tasks look "covered" in resilience checks).
# Review: append-only confirmation record (ENT-24 — never update or delete).
ALLOWED_CREATE_LABELS: set[str] = {
    "SupportLog",
    "LifeHistory",
    "Wish",
    "AuditLog",
    "PublicAssistance",
    "MeetingRecord",
    "CareRole",
    "ProviderFeedback",
    "Review",
}

ALLOWED_LABELS: set[str] = set(MERGE_KEYS.keys()) | ALLOWED_CREATE_LABELS

# CREATE-only labels that should get auto-generated sourceHash for dedup.
# AuditLog and PublicAssistance are excluded intentionally (audit integrity / admin-only).
_HASHABLE_CREATE_LABELS: set[str] = {
    "SupportLog", "MeetingRecord", "LifeHistory", "Wish",
}

ALLOWED_REL_TYPES: set[str] = {
    "HAS_CONDITION",
    "MUST_AVOID",
    "IN_CONTEXT",
    "REQUIRES",
    "ADDRESSES",
    "HAS_KEY_PERSON",
    "HAS_LEGAL_REP",
    "HAS_CERTIFICATE",
    "RECEIVES",
    "REGISTERED_AT",
    "TREATED_AT",
    "HAS_DOCTOR",
    "SUPPORTED_BY",
    "LOGGED",
    "ABOUT",
    "FOLLOWS",
    "USES_SERVICE",
    "HAS_HISTORY",
    "HAS_WISH",
    "AUDIT_FOR",
    "HAS_IDENTITY",
    "RECORDED",
    "IS_PARENT_OF",
    "FAMILY_OF",
    "PERFORMS",
    "CAN_BE_PERFORMED_BY",
    "HAS_FEEDBACK",
    "WROTE",
    "REVIEWED",
    # 証拠・鮮度モデル（SSOT v3.4 / 2026-08-08・BRS-13）追記専用
    "CONTRADICTS",
    "CONFIRMS",
}

# ---------------------------------------------------------------------------
# Driver singleton
# ---------------------------------------------------------------------------

_driver: Driver | None = None


def get_driver() -> Driver:
    """Return the singleton Neo4j driver, creating it on first call."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        logger.info("Neo4j driver created: %s", settings.neo4j_uri)
    return _driver


def close_driver() -> None:
    """Close and reset the singleton driver."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed.")


# ---------------------------------------------------------------------------
# Connectivity check
# ---------------------------------------------------------------------------

def is_db_available() -> bool:
    """Return True if the Neo4j database is reachable."""
    try:
        driver = get_driver()
        driver.verify_connectivity()
        return True
    except Exception as exc:
        logger.warning("Neo4j connectivity check failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------

def _sanitize_value(value: Any) -> Any:
    """Neo4j 固有型（Date, DateTime, Duration 等）を JSON 直列化可能な Python 型に変換する。"""
    if isinstance(value, Neo4jDateTime):
        # neo4j.time.DateTime → ISO 8601 文字列
        return value.iso_format()
    if isinstance(value, Neo4jDate):
        # neo4j.time.Date → "YYYY-MM-DD"
        return str(value)
    if isinstance(value, Neo4jTime):
        return value.iso_format()
    if isinstance(value, Neo4jDuration):
        return str(value)
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _sanitize_record(record_dict: dict) -> dict:
    """レコード辞書内の全値を再帰的にサニタイズする。"""
    return {k: _sanitize_value(v) for k, v in record_dict.items()}


def run_query(query: str, params: dict | None = None) -> list[dict]:
    """Execute a Cypher query and return all records as a list of dicts.

    Neo4j 固有の日付・時刻型は自動的に文字列へ変換される。
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, params or {})
        return [_sanitize_record(record.data()) for record in result]


# ---------------------------------------------------------------------------
# Node registration helpers
# ---------------------------------------------------------------------------

def _register_node(
    session: Any,
    label: str,
    properties: dict,
) -> bool:
    """Register a single node; return True on success."""
    if label not in ALLOWED_LABELS:
        logger.warning("Skipping node with disallowed label: %r", label)
        return False

    props = {k: v for k, v in properties.items() if v is not None}

    # Normalize merge key values for consistent MERGE matching
    if label in MERGE_KEYS:
        if label in _NAME_NORMALIZED_LABELS:
            if "name" in props and isinstance(props["name"], str):
                props["name"] = normalize_name(props["name"])
            # ServiceProvider: normalize wamnetId when present
            if label == "ServiceProvider" and props.get("wamnetId"):
                props["wamnetId"] = normalize_text(str(props["wamnetId"]))
            # Auto-set kana for Client if not already present
            if label == "Client" and "kana" not in props:
                name_val = props.get("name", "")
                if name_val:
                    kana = name_to_kana(name_val)
                    if kana:
                        props["kana"] = kana
        elif label == "Condition":
            if "name" in props and isinstance(props["name"], str):
                props["name"] = normalize_condition(props["name"])
        elif label == "Certificate":
            # Ensure grade has a value for composite MERGE key
            for k in MERGE_KEYS[label]:
                if k in props and isinstance(props[k], str):
                    props[k] = normalize_text(props[k])
            if "grade" not in props or not props["grade"]:
                props["grade"] = "不明"
        else:
            # Generic text normalization for all other merge keys
            for k in MERGE_KEYS[label]:
                if k in props and isinstance(props[k], str):
                    props[k] = normalize_text(props[k])

    if label in MERGE_KEYS:
        keys = MERGE_KEYS[label]
        # ServiceProvider: prefer wamnetId over name when available
        if label == "ServiceProvider" and props.get("wamnetId"):
            keys = ["wamnetId"]
        # Ensure all merge keys are present
        missing = [k for k in keys if k not in props]
        if missing:
            logger.warning(
                "Skipping %s node — missing merge key(s): %s", label, missing
            )
            return False
        merge_props = {k: props[k] for k in keys}
        extra_props = {k: v for k, v in props.items() if k not in keys}
        cypher = (
            f"MERGE (n:{label} {{{', '.join(f'{k}: ${k}' for k in keys)}}})\n"
            f"ON CREATE SET n += $extra_props\n"
            f"ON MATCH SET n += $extra_props\n"
            f"RETURN n"
        )
        params = {**merge_props, "extra_props": extra_props}
        session.run(cypher, params)
    else:
        # CREATE-only labels
        # Auto-generate sourceHash for dedup if not already present
        if label in _HASHABLE_CREATE_LABELS and "sourceHash" not in props:
            hash_input = json.dumps(props, sort_keys=True, ensure_ascii=False, default=str)
            props["sourceHash"] = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        cypher = f"CREATE (n:{label} $props) RETURN n"
        session.run(cypher, {"props": props})

    return True


def _register_relationship(
    session: Any,
    rel: dict,
) -> bool:
    """Register a single relationship; return True on success."""
    rel_type = rel.get("type")
    from_label = rel.get("from_label")
    from_key = rel.get("from_key")
    from_value = rel.get("from_value")
    to_label = rel.get("to_label")
    to_key = rel.get("to_key")
    to_value = rel.get("to_value")
    properties = rel.get("properties", {}) or {}

    if not all([rel_type, from_label, from_key, from_value, to_label, to_key, to_value]):
        logger.warning("Skipping incomplete relationship: %r", rel)
        return False

    if rel_type not in ALLOWED_REL_TYPES:
        logger.warning("Skipping relationship with disallowed type: %r", rel_type)
        return False

    if from_label not in ALLOWED_LABELS or to_label not in ALLOWED_LABELS:
        logger.warning(
            "Skipping relationship — disallowed label: from=%r to=%r",
            from_label, to_label,
        )
        return False

    cypher = (
        f"MATCH (a:{from_label} {{{from_key}: $from_value}})\n"
        f"MATCH (b:{to_label} {{{to_key}: $to_value}})\n"
        f"MERGE (a)-[r:{rel_type}]->(b)\n"
        f"ON CREATE SET r += $props\n"
        f"ON MATCH SET r += $props\n"
        f"RETURN r"
    )
    session.run(
        cypher,
        {"from_value": from_value, "to_value": to_value, "props": properties},
    )
    return True


# ---------------------------------------------------------------------------
# Main registration function
# ---------------------------------------------------------------------------

def register_to_database(
    extracted_graph: dict,
    user_name: str = "system",
) -> dict:
    """Register nodes and relationships from an extracted graph dict.

    Args:
        extracted_graph: Dict with optional keys ``nodes`` and ``relationships``.
        user_name: Name of the actor performing registration (used for audit log).

    Returns:
        Dict with keys:
        - ``status``: ``"success"`` or ``"error"``
        - ``client_name``: Name of the primary Client node (or ``None``)
        - ``registered_count``: Number of successfully registered nodes
        - ``registered_types``: List of node labels that were registered
        - ``error``: Error message (only present when status is ``"error"``)
    """
    nodes: list[dict] = extracted_graph.get("nodes", []) or []
    relationships: list[dict] = extracted_graph.get("relationships", []) or []

    client_name: str | None = None
    registered_count = 0
    registered_types: list[str] = []

    try:
        driver = get_driver()
        with driver.session() as session:
            # --- Register nodes ---
            for node in nodes:
                label = node.get("label", "")
                properties = node.get("properties", {}) or {}

                # Extract client name for the response (normalized)
                if label == "Client" and "name" in properties:
                    client_name = normalize_name(properties.get("name", ""))

                if _register_node(session, label, properties):
                    registered_count += 1
                    if label not in registered_types:
                        registered_types.append(label)

            # --- Build temp_id map for source_temp_id/target_temp_id resolution ---
            temp_id_map = {}
            for node in nodes:
                temp_id = node.get("temp_id")
                if not temp_id:
                    continue
                label = node.get("label", "")
                props = node.get("properties", {}) or {}
                if label in MERGE_KEYS:
                    keys = MERGE_KEYS[label]
                    if keys and keys[0] in props:
                        temp_id_map[temp_id] = {
                            "label": label,
                            "key": keys[0],
                            "value": props[keys[0]],
                        }
                elif label in ALLOWED_CREATE_LABELS:
                    # For CREATE-only labels, use a unique property if available
                    for candidate_key in ["date", "id", "title", "filePath"]:
                        if candidate_key in props:
                            temp_id_map[temp_id] = {
                                "label": label,
                                "key": candidate_key,
                                "value": props[candidate_key],
                            }
                            break

            # --- Register relationships ---
            for rel in relationships:
                # Convert source_temp_id/target_temp_id to from_label/from_key/from_value format
                if "source_temp_id" in rel and "from_label" not in rel:
                    src = temp_id_map.get(rel["source_temp_id"])
                    tgt = temp_id_map.get(rel["target_temp_id"])
                    if src and tgt:
                        rel = {
                            "type": rel.get("type"),
                            "from_label": src["label"],
                            "from_key": src["key"],
                            "from_value": src["value"],
                            "to_label": tgt["label"],
                            "to_key": tgt["key"],
                            "to_value": tgt["value"],
                            "properties": rel.get("properties", {}),
                        }
                    else:
                        logger.warning("Cannot resolve temp_ids for relationship: %r", rel)
                        continue
                _register_relationship(session, rel)

            # --- Audit log ---
            if client_name:
                _create_audit_log_in_session(
                    session,
                    user_name=user_name,
                    action="register",
                    target_type="Client",
                    target_name=client_name,
                    details=f"Registered {registered_count} node(s): {registered_types}",
                    client_name=client_name,
                )

        return {
            "status": "success",
            "client_name": client_name,
            "registered_count": registered_count,
            "registered_types": registered_types,
        }

    except Exception as exc:
        logger.error("register_to_database failed: %s", exc, exc_info=True)
        return {
            "status": "error",
            "client_name": client_name,
            "registered_count": registered_count,
            "registered_types": registered_types,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _create_audit_log_in_session(
    session: Any,
    user_name: str,
    action: str,
    target_type: str,
    target_name: str,
    details: str,
    client_name: str,
) -> None:
    """Write an AuditLog node inside an existing session."""
    now = datetime.now(timezone.utc).isoformat()
    cypher = (
        "CREATE (a:AuditLog {"
        "  userName: $user_name,"
        "  action: $action,"
        "  targetType: $target_type,"
        "  targetName: $target_name,"
        "  details: $details,"
        "  createdAt: $created_at"
        "})\n"
        "WITH a\n"
        "MATCH (c:Client {name: $client_name})\n"
        "MERGE (a)-[:AUDIT_FOR]->(c)\n"
        "RETURN a"
    )
    session.run(
        cypher,
        {
            "user_name": user_name,
            "action": action,
            "target_type": target_type,
            "target_name": target_name,
            "details": details,
            "created_at": now,
            "client_name": client_name,
        },
    )


def create_audit_log(
    user_name: str,
    action: str,
    target_type: str,
    target_name: str,
    details: str,
    client_name: str,
) -> None:
    """Public helper to write an AuditLog node linked to a Client."""
    try:
        driver = get_driver()
        with driver.session() as session:
            _create_audit_log_in_session(
                session,
                user_name=user_name,
                action=action,
                target_type=target_type,
                target_name=target_name,
                details=details,
                client_name=client_name,
            )
    except Exception as exc:
        logger.error("create_audit_log failed: %s", exc, exc_info=True)

"""Neo4j database operations: connection management, query execution, graph registration."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
from typing import Any

from neo4j import GraphDatabase, Driver
from neo4j.time import Date as Neo4jDate, DateTime as Neo4jDateTime, Time as Neo4jTime, Duration as Neo4jDuration

from app.config import settings
from app.lib.guardian import guardian
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

# 事実時間軸（SSOT v3.5 §7.10 / BRS-14・2026-09-03）。CREATE 時に自動付与し、
# MERGE の ON MATCH では入力から破棄する（初回登録日は書き換えない）。
# 値の正は SEMANTIC_MODEL §6 machine-check の immutableProperties
# （check_semantic_drift.py が AST で突合する）。判定の本体は Guardian。
IMMUTABLE_PROPERTIES: dict[str, list[str]] = {
    "NgAction": ["registeredAt"],
    "CarePreference": ["registeredAt"],
}

# 管理者裁定で Inactive 化できる事実ラベルと、Client からの辺
_FACT_LABEL_EDGES: dict[str, str] = {
    "NgAction": "MUST_AVOID",
    "CarePreference": "REQUIRES",
}

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

    # 事実時間軸の規則違反（Inactive なのに validTo 無し等）は書き込まない
    fact_errors = guardian.validate_fact_time(label, props)
    if fact_errors:
        logger.warning("Skipping %s node — %s", label, " / ".join(fact_errors))
        return False

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
        # ON CREATE: registeredAt を補い date 型に揃える / ON MATCH: 不変プロパティを破棄
        create_props = guardian.apply_fact_time_defaults(label, extra_props)
        update_props, _ = guardian.strip_immutable_properties(
            label, guardian.coerce_date_properties(label, extra_props)
        )
        cypher = (
            f"MERGE (n:{label} {{{', '.join(f'{k}: ${k}' for k in keys)}}})\n"
            f"ON CREATE SET n += $create_props\n"
            f"ON MATCH SET n += $update_props\n"
            f"RETURN n"
        )
        params = {**merge_props, "create_props": create_props, "update_props": update_props}
        session.run(cypher, params)
    else:
        # CREATE-only labels
        # Auto-generate sourceHash for dedup if not already present
        if label in _HASHABLE_CREATE_LABELS and "sourceHash" not in props:
            hash_input = json.dumps(props, sort_keys=True, ensure_ascii=False, default=str)
            props["sourceHash"] = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        props = guardian.coerce_date_properties(label, props)  # PublicAssistance.endDate
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

    # HAS_KEY_PERSON: status 2値・Inactive には endDate（v3.5 §7.10）。違反は書き込まない
    rel_errors, _ = guardian.validate_relationship_properties(rel_type, properties)
    if rel_errors:
        logger.warning("Skipping %s relationship — %s", rel_type, " / ".join(rel_errors))
        return False
    # ON CREATE: startDate=当日・status=Active を補う / ON MATCH: 入力のみ（交代は endDate+Inactive の SET）
    create_props = guardian.apply_relationship_defaults(rel_type, properties)
    match_props = guardian.coerce_date_properties(
        rel_type, properties, guardian.RELATIONSHIP_DATE_PROPERTIES
    )

    cypher = (
        f"MATCH (a:{from_label} {{{from_key}: $from_value}})\n"
        f"MATCH (b:{to_label} {{{to_key}: $to_value}})\n"
        f"MERGE (a)-[r:{rel_type}]->(b)\n"
        f"ON CREATE SET r += $create_props\n"
        f"ON MATCH SET r += $props\n"
        f"RETURN r"
    )
    session.run(
        cypher,
        {"from_value": from_value, "to_value": to_value,
         "create_props": create_props, "props": match_props},
    )
    return True


# ---------------------------------------------------------------------------
# Main registration function
# ---------------------------------------------------------------------------

def register_to_database(
    extracted_graph: dict,
    user_name: str = "system",
    source_hash: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Register nodes and relationships from an extracted graph dict.

    Args:
        extracted_graph: Dict with optional keys ``nodes`` and ``relationships``.
        user_name: Name of the actor performing registration (used for audit log).
        source_hash: SHA256 of the raw source narrative (BRS-11 v1.7 provenance;
            stored on the AuditLog node).
        correlation_id: The id returned to the API caller as ``auditLogId``;
            stored on the AuditLog node so the returned id resolves to a real node.

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
                    source_hash=source_hash,
                    correlation_id=correlation_id,
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
# 管理者裁定（Inactive 化）とキーパーソン交代 — 事実時間軸（BRS-14）
# ---------------------------------------------------------------------------

def deactivate_fact(
    label: str,
    key_props: dict,
    client_name: str,
    approved_by: str,
    valid_to: str | date | None = None,
    reason: str = "",
) -> dict:
    """管理者裁定で事実（NgAction / CarePreference）を Inactive にする。

    validTo が入る唯一の経路（BRS-14）。status=Inactive・validTo・AuditLog を
    1 トランザクションで書く。validTo 未指定なら裁定日（当日）。
    approvedBy 無しでは実行できない（Phase 1 技術仕様 §4 記録の機械的強制）。
    """
    if not approved_by:
        raise ValueError("approved_by は必須です（裁定者の記録なしに Inactive 化できません）")
    if label not in _FACT_LABEL_EDGES:
        raise ValueError(f"裁定で Inactive 化できるのは {sorted(_FACT_LABEL_EDGES)} のみです: {label}")
    keys = MERGE_KEYS[label]
    missing = [k for k in keys if not key_props.get(k)]
    if missing:
        raise ValueError(f"{label} を特定するキーが不足しています: {missing}")
    valid_to_date = guardian._parse_date(valid_to) if valid_to else date.today()
    edge = _FACT_LABEL_EDGES[label]
    client = normalize_name(client_name)

    def _work(tx):
        cypher = (
            f"MATCH (c:Client {{name: $client_name}})-[:{edge}]->"
            f"(n:{label} {{{', '.join(f'{k}: ${k}' for k in keys)}}})\n"
            "SET n.status = 'Inactive', n.validTo = $valid_to\n"
            "RETURN n"
        )
        record = tx.run(cypher, {"client_name": client, "valid_to": valid_to_date,
                                 **{k: key_props[k] for k in keys}}).single()
        if record is None:
            raise LookupError(f"{label} が見つかりません（client={client}）")
        target_name = " / ".join(str(key_props[k]) for k in keys)
        _create_audit_log_in_session(
            tx, user_name=approved_by, action="deactivate", target_type=label,
            target_name=target_name,
            details=f"管理者裁定により Inactive 化。validTo={valid_to_date.isoformat()}。{reason}".strip(),
            client_name=client,
        )
        return target_name

    try:
        driver = get_driver()
        with driver.session() as session:
            target_name = session.execute_write(_work)
        return {"status": "success", "label": label, "target": target_name,
                "valid_to": valid_to_date.isoformat()}
    except Exception as exc:
        logger.error("deactivate_fact failed: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}


def replace_key_person(
    client_name: str,
    old_name: str,
    new_name: str,
    rank: int,
    changed_on: str | date | None = None,
    user_name: str = "system",
) -> dict:
    """キーパーソンの交代。旧 HAS_KEY_PERSON は削除せず endDate + Inactive を書き、
    新しいリレーションを startDate=交代日・status=Active で CREATE する（ENT-08 / BRS-14）。
    AuditLog まで 1 トランザクション。"""
    changed = guardian._parse_date(changed_on) if changed_on else date.today()
    client = normalize_name(client_name)
    old = normalize_name(old_name)
    new = normalize_name(new_name)

    def _work(tx):
        tx.run(
            "MATCH (c:Client {name: $client_name})-[old:HAS_KEY_PERSON]->(kp:KeyPerson {name: $old_name})\n"
            "WHERE old.status IS NULL OR old.status = 'Active'\n"
            "SET old.endDate = $end_date, old.status = 'Inactive'\n"
            "RETURN count(old) AS closed",
            {"client_name": client, "old_name": old, "end_date": changed},
        )
        tx.run(
            "MATCH (c:Client {name: $client_name})\n"
            "MERGE (kp:KeyPerson {name: $new_name})\n"
            "CREATE (c)-[:HAS_KEY_PERSON {rank: $rank, startDate: $start_date, status: 'Active'}]->(kp)",
            {"client_name": client, "new_name": new, "rank": rank, "start_date": changed},
        )
        _create_audit_log_in_session(
            tx, user_name=user_name, action="replace_key_person", target_type="KeyPerson",
            target_name=f"{old} → {new}",
            details=f"キーパーソン交代（rank={rank}）。旧リレーションは endDate={changed.isoformat()} で Inactive 化し保持",
            client_name=client,
        )

    try:
        driver = get_driver()
        with driver.session() as session:
            session.execute_write(_work)
        return {"status": "success", "old": old, "new": new, "changed_on": changed.isoformat()}
    except Exception as exc:
        logger.error("replace_key_person failed: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}


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
    source_hash: str | None = None,
    correlation_id: str | None = None,
) -> None:
    """Write an AuditLog node inside an existing session.

    sourceHash / correlationId are BRS-11 v1.7 provenance fields (SCHEMA_CONVENTION
    v3.4.1). Passing null leaves the property unset (Neo4j drops null map entries).
    """
    now = datetime.now(timezone.utc).isoformat()
    cypher = (
        "CREATE (a:AuditLog {"
        "  userName: $user_name,"
        "  action: $action,"
        "  targetType: $target_type,"
        "  targetName: $target_name,"
        "  details: $details,"
        "  createdAt: $created_at,"
        "  sourceHash: $source_hash,"
        "  correlationId: $correlation_id"
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
            "source_hash": source_hash,
            "correlation_id": correlation_id,
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

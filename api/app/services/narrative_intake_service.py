"""Business logic for /api/narrative/intake endpoint.

Claude skill 経路と Gemini 経路を統一するための中核サービス。
既存の `db_operations.register_to_database` と `gemini_agent.check_safety_compliance`、
`embedding.embed_text` を再利用し、以下の責務を負う:

1. allowlist 二重検証 (defense in depth)
2. 既存 NgAction との安全性コンプライアンスチェック
3. sourceHash ベースの冪等性チェック
4. register_to_database 呼び出し + 監査ログ生成
5. SupportLog / NgAction / CarePreference への embedding 自動付与
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from app.agents.gemini_agent import check_safety_compliance
from app.lib.dedup import find_semantic_duplicates
from app.lib.db_operations import (
    ALLOWED_CREATE_LABELS,
    ALLOWED_LABELS,
    ALLOWED_REL_TYPES,
    MERGE_KEYS,
    register_to_database,
    run_query,
)
from app.lib.embedding import embed_text
from app.schemas.narrative_intake import (
    DuplicateCheckResult,
    NarrativeIntakeRequest,
    NarrativeIntakeResponse,
    NarrativePreviewContext,
    PreviewClientInfo,
    PreviewExistingNgAction,
    RejectedNode,
    RejectedRelationship,
    SafetyCheckResultDetail,
    SemanticDuplicateWarning,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding target labels
# ---------------------------------------------------------------------------

_EMBEDDING_TARGET_LABELS = {"SupportLog", "NgAction", "CarePreference"}


# ---------------------------------------------------------------------------
# Semantic dedup configuration
# ---------------------------------------------------------------------------

_SEMANTIC_CHECK_CONFIG: dict[str, dict] = {
    "NgAction": {"index": "ng_action_embedding", "threshold": 0.85},
    "CarePreference": {"index": "care_preference_embedding", "threshold": 0.85},
}


# ---------------------------------------------------------------------------
# 1. Allowlist validation (defense in depth)
# ---------------------------------------------------------------------------


def validate_graph(
    req: NarrativeIntakeRequest,
) -> tuple[dict[str, list], dict[str, list]]:
    """Python 側で allowlist を再検証する。

    Claude skill 側で Phase 2 検証が走っているはずだが、LLMの出力を信用しない設計。

    Returns:
        (validated, rejected) のタプル。
        validated = {"nodes": [NarrativeNode...], "relationships": [NarrativeRelationship...]}
        rejected  = {"nodes": [RejectedNode...], "relationships": [RejectedRelationship...]}
    """
    validated_nodes: list = []
    rejected_nodes: list[RejectedNode] = []

    # temp_id の重複チェック用
    seen_temp_ids: set[str] = set()

    for n in req.nodes:
        # 1-a. ラベルチェック
        if n.label not in ALLOWED_LABELS:
            rejected_nodes.append(
                RejectedNode(
                    temp_id=n.temp_id,
                    label=n.label,
                    reason=f"label_not_allowed: {n.label}",
                )
            )
            continue

        # 1-b. mergeKey 必須チェック (MERGE 対象ラベルのみ)
        if n.label in MERGE_KEYS:
            required_keys = MERGE_KEYS[n.label]
            missing = [
                k for k in required_keys if k not in (n.properties or {}) or not n.properties[k]
            ]
            if missing:
                rejected_nodes.append(
                    RejectedNode(
                        temp_id=n.temp_id,
                        label=n.label,
                        reason=f"merge_key_missing: {missing}",
                    )
                )
                continue

        # 1-c. temp_id 重複チェック
        if n.temp_id in seen_temp_ids:
            rejected_nodes.append(
                RejectedNode(
                    temp_id=n.temp_id,
                    label=n.label,
                    reason="duplicate_temp_id",
                )
            )
            continue
        seen_temp_ids.add(n.temp_id)

        validated_nodes.append(n)

    validated_rels: list = []
    rejected_rels: list[RejectedRelationship] = []
    valid_temp_ids = {n.temp_id for n in validated_nodes}

    for r in req.relationships:
        # 2-a. リレーション型チェック
        if r.type not in ALLOWED_REL_TYPES:
            rejected_rels.append(
                RejectedRelationship(
                    source_temp_id=r.source_temp_id,
                    target_temp_id=r.target_temp_id,
                    type=r.type,
                    reason=f"rel_type_not_allowed: {r.type}",
                )
            )
            continue

        # 2-b. source/target の temp_id が有効ノード集合に含まれているか
        if r.source_temp_id not in valid_temp_ids:
            rejected_rels.append(
                RejectedRelationship(
                    source_temp_id=r.source_temp_id,
                    target_temp_id=r.target_temp_id,
                    type=r.type,
                    reason=f"source_temp_id_not_found: {r.source_temp_id}",
                )
            )
            continue
        if r.target_temp_id not in valid_temp_ids:
            rejected_rels.append(
                RejectedRelationship(
                    source_temp_id=r.source_temp_id,
                    target_temp_id=r.target_temp_id,
                    type=r.type,
                    reason=f"target_temp_id_not_found: {r.target_temp_id}",
                )
            )
            continue

        validated_rels.append(r)

    validated = {"nodes": validated_nodes, "relationships": validated_rels}
    rejected = {"nodes": rejected_nodes, "relationships": rejected_rels}
    return validated, rejected


# ---------------------------------------------------------------------------
# 2. Safety compliance check (既存 NgAction との照合)
# ---------------------------------------------------------------------------


async def run_safety_check(
    validated: dict[str, list],
    client_name: str | None,
) -> SafetyCheckResultDetail:
    """クライアントの既存 NgAction と照合し、登録内容が抵触しないか確認する。

    Client が未登録の場合は空結果を返す。
    """
    if not client_name:
        return SafetyCheckResultDetail()

    try:
        existing = run_query(
            """
            MATCH (c:Client)-[:MUST_AVOID]->(ng:NgAction)
            WHERE c.name = $name
            RETURN ng.action AS action,
                   ng.riskLevel AS riskLevel,
                   COALESCE(ng.reason, '') AS reason
            """,
            {"name": client_name},
        )
    except Exception as exc:
        logger.warning("Safety check query failed: %s", exc)
        return SafetyCheckResultDetail()

    if not existing:
        return SafetyCheckResultDetail()

    # ナラティブテキスト相当を SupportLog / CarePreference から組み立てる
    narrative_fragments: list[str] = []
    for n in validated["nodes"]:
        if n.label == "SupportLog":
            parts = [
                str(n.properties.get("action", "")),
                str(n.properties.get("note", "")),
                str(n.properties.get("situation", "")),
            ]
            narrative_fragments.append(" / ".join(p for p in parts if p))
        elif n.label == "CarePreference":
            parts = [
                str(n.properties.get("category", "")),
                str(n.properties.get("instruction", "")),
            ]
            narrative_fragments.append(" / ".join(p for p in parts if p))

    narrative_text = "\n".join(narrative_fragments)
    if not narrative_text.strip():
        return SafetyCheckResultDetail()

    try:
        # gemini_agent.check_safety_compliance は dict を返す
        result = await check_safety_compliance(narrative_text, existing)
    except Exception as exc:
        logger.warning("Safety compliance check failed: %s", exc)
        return SafetyCheckResultDetail()

    is_violation = bool(result.get("is_violation", False))
    warning_text = result.get("warning") or ""
    violations = [warning_text] if warning_text else []
    risk_level = str(result.get("risk_level", "None") or "None")

    return SafetyCheckResultDetail(
        is_violation=is_violation,
        violations=violations,
        risk_level=risk_level,
    )


# ---------------------------------------------------------------------------
# 2-b. Semantic duplicate detection (NgAction / CarePreference)
# ---------------------------------------------------------------------------


async def check_semantic_duplicates(
    validated: dict[str, list],
) -> list[SemanticDuplicateWarning]:
    """NgAction / CarePreference の意味的重複候補を vector index で検索する。

    ベストエフォート: 失敗しても空リストを返し、通常フローをブロックしない。
    """
    warnings: list[SemanticDuplicateWarning] = []
    for n in validated["nodes"]:
        config = _SEMANTIC_CHECK_CONFIG.get(n.label)
        if not config:
            continue

        # Build search text based on label
        if n.label == "NgAction":
            text = str(n.properties.get("action", ""))
        elif n.label == "CarePreference":
            text = str(n.properties.get("instruction", ""))
        else:
            continue

        if not text.strip():
            continue

        try:
            candidates = await find_semantic_duplicates(
                text,
                n.label,
                config["index"],
                threshold=config["threshold"],
            )
        except Exception as exc:
            logger.warning("Semantic dedup check failed for %s: %s", n.label, exc)
            continue

        for c in candidates:
            if c["text"] != text:  # Skip exact matches (handled by MERGE)
                warnings.append(
                    SemanticDuplicateWarning(
                        new_text=text,
                        existing_text=c["text"],
                        similarity_score=c["score"],
                        label=n.label,
                        node_id=c["nodeId"],
                    )
                )

    return warnings


# ---------------------------------------------------------------------------
# 3. Duplicate / idempotency check (sourceHash ベース)
# ---------------------------------------------------------------------------


def check_duplicates(source_hash: str) -> DuplicateCheckResult:
    """sourceHash プロパティを持つ既存ノードを検索し、冪等性を判定する。"""
    if not source_hash:
        return DuplicateCheckResult()

    try:
        existing = run_query(
            """
            MATCH (n)
            WHERE n.sourceHash = $h
            RETURN labels(n)[0] AS label,
                   COALESCE(n.date, '') AS date,
                   COALESCE(n.title, '') AS title,
                   elementId(n) AS nodeId
            LIMIT 20
            """,
            {"h": source_hash},
        )
    except Exception as exc:
        logger.warning("Duplicate check query failed: %s", exc)
        return DuplicateCheckResult()

    return DuplicateCheckResult(
        has_duplicate=len(existing) > 0,
        existing_nodes=[dict(e) for e in existing],
    )


# ---------------------------------------------------------------------------
# 4. Register + audit log (既存パイプライン再利用)
# ---------------------------------------------------------------------------


def _inject_source_hash(
    validated: dict[str, list],
    source_hash: str,
) -> dict[str, Any]:
    """SupportLog / MeetingRecord / LifeHistory に sourceHash を付与し、

    register_to_database が期待する dict 形式に変換する。
    """
    out_nodes: list[dict] = []
    hash_target_labels = {"SupportLog", "MeetingRecord", "LifeHistory", "Wish"}

    for n in validated["nodes"]:
        props = dict(n.properties or {})
        if n.label in hash_target_labels and source_hash and "sourceHash" not in props:
            props["sourceHash"] = source_hash
        out_nodes.append(
            {
                "temp_id": n.temp_id,
                "label": n.label,
                "properties": props,
            }
        )

    out_rels: list[dict] = []
    for r in validated["relationships"]:
        out_rels.append(
            {
                "source_temp_id": r.source_temp_id,
                "target_temp_id": r.target_temp_id,
                "type": r.type,
                "properties": dict(r.properties or {}),
            }
        )

    return {"nodes": out_nodes, "relationships": out_rels}


async def _embed_targets(validated: dict[str, list]) -> int:
    """SupportLog / NgAction / CarePreference に embedding を付与する。

    既に登録済みのノードを mergeKey または特徴プロパティで検索し、
    Gemini Embedding 2 で生成した 768次元ベクトルを UPDATE する。
    """
    embedded = 0

    for n in validated["nodes"]:
        if n.label not in _EMBEDDING_TARGET_LABELS:
            continue

        props = n.properties or {}

        # 埋め込み対象テキストを組み立て
        if n.label == "SupportLog":
            text_parts = [
                str(props.get("action", "")),
                str(props.get("note", "")),
                str(props.get("situation", "")),
                str(props.get("nextAction", "")),
            ]
            match_key = "date"
            match_value = props.get("date", "")
        elif n.label == "NgAction":
            text_parts = [
                str(props.get("action", "")),
                str(props.get("reason", "")),
                str(props.get("riskLevel", "")),
            ]
            match_key = "action"
            match_value = props.get("action", "")
        elif n.label == "CarePreference":
            text_parts = [
                str(props.get("category", "")),
                str(props.get("instruction", "")),
            ]
            match_key = "instruction"
            match_value = props.get("instruction", "")
        else:
            continue

        text = " / ".join(p for p in text_parts if p)
        if not text.strip() or not match_value:
            continue

        try:
            vec = await embed_text(text)
        except Exception as exc:
            logger.warning("embed_text failed for %s: %s", n.label, exc)
            continue

        if not vec:
            continue

        # ベクトルを該当ノードへ付与
        try:
            run_query(
                f"""
                MATCH (n:{n.label} {{{match_key}: $v}})
                SET n.embedding = $emb,
                    n.embeddingUpdatedAt = $ts
                """,
                {
                    "v": match_value,
                    "emb": vec,
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )
            embedded += 1
        except Exception as exc:
            logger.warning("embedding update failed for %s: %s", n.label, exc)

    return embedded


async def register_narrative(
    validated: dict[str, list],
    req: NarrativeIntakeRequest,
    safety: SafetyCheckResultDetail,
    duplicate: DuplicateCheckResult,
    rejected_nodes: list[RejectedNode],
    rejected_rels: list[RejectedRelationship],
) -> NarrativeIntakeResponse:
    """実書き込み + embedding 付与 + レスポンス生成。"""
    audit = req.auditContext

    # Semantic duplicate check (ベストエフォート、DB書き込み前)
    semantic_dups = await check_semantic_duplicates(validated)

    # sourceHash を付与した dict に変換
    graph_dict = _inject_source_hash(validated, audit.sourceHash)

    try:
        result = register_to_database(graph_dict, user_name=audit.user)
    except Exception as exc:
        logger.error("register_to_database failed: %s", exc, exc_info=True)
        return NarrativeIntakeResponse(
            status="validation_error",
            message=f"DB registration failed: {exc}",
            rejectedNodes=rejected_nodes,
            rejectedRelationships=rejected_rels,
            safetyCheck=safety,
            duplicateCheck=duplicate,
            warnings=req.warnings,
            semanticDuplicates=semantic_dups,
        )

    if result.get("status") != "success":
        return NarrativeIntakeResponse(
            status="validation_error",
            message=result.get("error", "unknown_error"),
            rejectedNodes=rejected_nodes,
            rejectedRelationships=rejected_rels,
            safetyCheck=safety,
            duplicateCheck=duplicate,
            warnings=req.warnings,
            semanticDuplicates=semantic_dups,
        )

    # Embedding 付与 (ベストエフォート)
    try:
        embedded_count = await _embed_targets(validated)
    except Exception as exc:
        logger.warning("Embedding phase failed: %s", exc)
        embedded_count = 0

    # 監査ログ ID は register_to_database 内で生成されるが elementId を返さない
    # ため、sessionId ベースで擬似的に埋める
    audit_log_id = f"{audit.sessionId}:{audit.sourceHash[:12]}"

    registered_types = result.get("registered_types", []) or []
    # merged / created の区別は db_operations では追跡していないため、
    # MERGE 対象ラベル数と CREATE 対象ラベル数で近似する
    nodes_merged = sum(1 for n in validated["nodes"] if n.label in MERGE_KEYS)
    nodes_created = sum(1 for n in validated["nodes"] if n.label in ALLOWED_CREATE_LABELS)

    return NarrativeIntakeResponse(
        status="ok",
        nodesCreated=nodes_created,
        nodesMerged=nodes_merged,
        relationshipsCreated=len(validated["relationships"]),
        auditLogId=audit_log_id,
        embeddingsGenerated=embedded_count,
        rejectedNodes=rejected_nodes,
        rejectedRelationships=rejected_rels,
        safetyCheck=safety,
        duplicateCheck=duplicate,
        warnings=req.warnings,
        semanticDuplicates=semantic_dups,
        message=f"registered {result.get('registered_count', 0)} node(s): {registered_types}",
    )


# ---------------------------------------------------------------------------
# 5. Preview context (Phase 3 用の軽量な既存データ参照)
# ---------------------------------------------------------------------------


def build_preview_context(
    client_name: str | None,
    source_hash: str | None,
) -> NarrativePreviewContext:
    """Phase 3 プレビュー時に skill が参照する既存コンテキストを返す。"""
    ctx = NarrativePreviewContext()

    if client_name:
        client_rows = run_query(
            """
            MATCH (c:Client {name: $name})
            RETURN c.name AS name,
                   COALESCE(toString(c.dob), '') AS dob,
                   COALESCE(c.age, 0) AS age
            LIMIT 1
            """,
            {"name": client_name},
        )
        if client_rows:
            row = client_rows[0]
            ctx.client = PreviewClientInfo(
                name=row.get("name"),
                dob=row.get("dob") or None,
                age=int(row.get("age") or 0) or None,
                exists=True,
            )
        else:
            ctx.client = PreviewClientInfo(name=client_name, exists=False)

        ng_rows = run_query(
            """
            MATCH (c:Client {name: $name})-[:MUST_AVOID]->(ng:NgAction)
            RETURN ng.action AS action,
                   COALESCE(ng.riskLevel, 'None') AS riskLevel,
                   COALESCE(ng.reason, '') AS reason
            """,
            {"name": client_name},
        )
        ctx.existingNgActions = [
            PreviewExistingNgAction(
                action=r["action"],
                riskLevel=r["riskLevel"],
                reason=r.get("reason") or None,
            )
            for r in ng_rows
        ]

    if source_hash:
        ctx.duplicateCheck = check_duplicates(source_hash)

    return ctx


# ---------------------------------------------------------------------------
# 6. Utilities
# ---------------------------------------------------------------------------


def compute_source_hash(text: str) -> str:
    """入力テキストの SHA256 を返す (冪等性キー生成用ヘルパー)。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

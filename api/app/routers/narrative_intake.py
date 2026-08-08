"""FastAPI router for /api/narrative/intake endpoint.

Claude skill (narrative-intake) からの書き込みを受け付ける薄いプロキシ。
実際のビジネスロジックは `app.services.narrative_intake_service` に委譲し、
ルーター自身は HTTP 層の責務 (入力バインディング、エラー変換) のみを担う。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.lib.db_operations import (
    ALLOWED_CREATE_LABELS,
    ALLOWED_LABELS,
    ALLOWED_REL_TYPES,
    MERGE_KEYS,
)
from app.schemas.narrative_intake import (
    NarrativeIntakeRequest,
    NarrativeIntakeResponse,
    NarrativePreviewContext,
    NarrativeSchemaResponse,
)
from app.services.narrative_intake_service import (
    build_preview_context,
    check_duplicates,
    check_semantic_duplicates,
    register_narrative,
    run_safety_check,
    validate_graph,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/narrative", tags=["narrative-intake"])


# ---------------------------------------------------------------------------
# POST /api/narrative/intake
# ---------------------------------------------------------------------------


@router.post("/intake", response_model=NarrativeIntakeResponse)
async def intake_narrative(req: NarrativeIntakeRequest) -> NarrativeIntakeResponse:
    """検証済みグラフJSONを受け取り、Neo4j に登録する。

    処理フロー:
    1. allowlist 二重検証 (defense in depth)
    2. 既存 NgAction との安全性チェック
    3. sourceHash ベースの冪等性チェック
    4. dryRun なら検証結果のみ返却
    5. 重大な安全性違反 (LifeThreatening) なら 409 で拒否
    6. 重複があれば duplicate ステータスで返却 (書き込みスキップ)
    7. register_to_database で実書き込み + embedding 自動付与
    """
    logger.info(
        "intake_narrative: user=%s nodes=%d rels=%d dryRun=%s",
        req.auditContext.user,
        len(req.nodes),
        len(req.relationships),
        req.dryRun,
    )

    # 1. 二重検証
    validated, rejected = validate_graph(req)
    rejected_nodes = rejected["nodes"]
    rejected_rels = rejected["relationships"]

    # すべてのノードが拒否された場合は早期リターン
    if not validated["nodes"]:
        return NarrativeIntakeResponse(
            status="validation_error",
            message="all nodes rejected by validation",
            rejectedNodes=rejected_nodes,
            rejectedRelationships=rejected_rels,
            warnings=req.warnings,
        )

    # 2. 安全性チェック
    safety = await run_safety_check(validated, req.auditContext.clientName)

    # 2.5. NgAction セマンティック重複ブロッキング（confirmDuplicates=true なら skip）
    if not req.confirmDuplicates:
        semantic_dups = await check_semantic_duplicates(validated)
        blocking = [d for d in semantic_dups if d.label == "NgAction"]
        if blocking:
            logger.warning(
                "NgAction semantic duplicate blocking: %d candidates found for client=%s",
                len(blocking),
                req.auditContext.clientName,
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "duplicate_confirmation_required",
                    "message": (
                        "意味的に類似するNgActionが既に存在します。"
                        "confirmDuplicates=true で再送してください。"
                    ),
                    "duplicates": [d.model_dump() for d in blocking],
                },
            )

    # 3. 冪等性チェック
    duplicate = check_duplicates(req.auditContext.sourceHash)

    # 4. dryRun モード: 検証結果のみ返却
    if req.dryRun:
        semantic_dups = await check_semantic_duplicates(validated)
        return NarrativeIntakeResponse(
            status="dry_run",
            message="dry run — no data was written",
            rejectedNodes=rejected_nodes,
            rejectedRelationships=rejected_rels,
            safetyCheck=safety,
            duplicateCheck=duplicate,
            warnings=req.warnings,
            semanticDuplicates=semantic_dups,
        )

    # 5. 生命に関わる安全性違反は拒否
    if safety.is_violation and safety.risk_level == "LifeThreatening":
        logger.warning(
            "Safety violation (LifeThreatening) detected for client=%s",
            req.auditContext.clientName,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "status": "safety_violation",
                "message": "登録内容が既存のNgAction(LifeThreatening)に抵触しています",
                "safetyCheck": safety.model_dump(),
                "rejectedNodes": [n.model_dump() for n in rejected_nodes],
            },
        )

    # 6. 重複が検出された場合は書き込みスキップ
    if duplicate.has_duplicate:
        return NarrativeIntakeResponse(
            status="duplicate",
            message=(
                f"sourceHash={req.auditContext.sourceHash[:12]}... "
                f"で既存ノードが {len(duplicate.existing_nodes)} 件見つかりました。"
                "冪等性のため登録をスキップします。"
            ),
            rejectedNodes=rejected_nodes,
            rejectedRelationships=rejected_rels,
            safetyCheck=safety,
            duplicateCheck=duplicate,
            warnings=req.warnings,
        )

    # 7. 実書き込み + embedding 付与
    return await register_narrative(
        validated=validated,
        req=req,
        safety=safety,
        duplicate=duplicate,
        rejected_nodes=rejected_nodes,
        rejected_rels=rejected_rels,
    )


# ---------------------------------------------------------------------------
# GET /api/narrative/preview-context
# ---------------------------------------------------------------------------


@router.get("/preview-context", response_model=NarrativePreviewContext)
async def preview_context(
    clientName: str | None = Query(None, description="対象クライアント名"),
    sourceHash: str | None = Query(None, description="入力原文の SHA256"),
) -> NarrativePreviewContext:
    """Phase 3 プレビュー表示用の既存データサマリーを返す。

    Claude skill がプレビュー作成時に「既に登録されているNgAction」や
    「重複候補」を表示するために使用する。
    """
    return build_preview_context(client_name=clientName, source_hash=sourceHash)


# ---------------------------------------------------------------------------
# GET /api/narrative/schema
# ---------------------------------------------------------------------------


@router.get("/schema", response_model=NarrativeSchemaResponse)
async def get_schema() -> NarrativeSchemaResponse:
    """Python 側の allowlist を返す (skill の schema/*.json 同期用)。"""
    return NarrativeSchemaResponse(
        allowed_labels=sorted(ALLOWED_LABELS),
        allowed_rels=sorted(ALLOWED_REL_TYPES),
        merge_keys={k: list(v) for k, v in MERGE_KEYS.items()},
        allowed_create_labels=sorted(ALLOWED_CREATE_LABELS),
        version=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )

"""Pydantic schemas for /api/narrative/intake endpoint.

Claude skill (narrative-intake) からポストされる検証済みグラフJSONを受け取るための
スキーマ定義。既存の `narrative.py` とは役割が異なり、以下を提供する:

- allowlist 二重検証のための mergeKey 必須フィールド
- 監査コンテキスト (user, sessionId, sourceHash)
- dryRun モード
- 詳細なレスポンス (rejected nodes/rels, safetyCheck, duplicateCheck)
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class NarrativeNode(BaseModel):
    """ナラティブ抽出ノード。

    Claude skill 側で Phase 1〜2 を通過したノードのみをポストする想定。
    """

    temp_id: str = Field(..., description="内部リンク用の仮ID (例: c1, log1)")
    label: str = Field(..., description="ノードラベル (PascalCase)")
    mergeKey: dict[str, Any] | None = Field(
        None,
        description="MERGE対象ラベルのみ必須。例: {'name': '山田太郎'}",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="ノードのプロパティ (camelCase)",
    )


class NarrativeRelationship(BaseModel):
    """ナラティブ抽出リレーション。"""

    source_temp_id: str = Field(..., description="ソースノードの temp_id")
    target_temp_id: str = Field(..., description="ターゲットノードの temp_id")
    type: str = Field(..., description="リレーション型 (UPPER_SNAKE_CASE)")
    properties: dict[str, Any] = Field(default_factory=dict)


class NarrativeAuditContext(BaseModel):
    """監査ログ生成に必要なコンテキスト情報。"""

    user: str = Field(..., description="登録実行者名 (例: 支援員名)")
    sessionId: str = Field(..., description="Claude skill セッションID")
    sourceType: str = Field(
        ...,
        description="入力の種別: narrative | meeting | handover | life_history",
    )
    sourceHash: str = Field(
        ...,
        description="入力ナラティブ原文のSHA256 (冪等性キー)",
    )
    clientName: str | None = Field(
        None,
        description="対象クライアント名 (安全性チェック用)",
    )


class NarrativeIntakeRequest(BaseModel):
    """/api/narrative/intake へのリクエスト本体。"""

    nodes: list[NarrativeNode] = Field(default_factory=list)
    relationships: list[NarrativeRelationship] = Field(default_factory=list)
    auditContext: NarrativeAuditContext
    warnings: list[str] = Field(
        default_factory=list,
        description="Claude skill 側で発生した警告 (相対時間解決失敗など)",
    )
    dryRun: bool = Field(
        False,
        description="True の場合、DBに書き込まず検証結果のみ返す",
    )
    confirmDuplicates: bool = Field(
        False,
        description="True の場合、セマンティック重複の確認済みとして登録を強行する",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class RejectedNode(BaseModel):
    """allowlist違反などで拒否されたノード情報。"""

    temp_id: str
    label: str
    reason: str


class RejectedRelationship(BaseModel):
    """allowlist違反などで拒否されたリレーション情報。"""

    source_temp_id: str
    target_temp_id: str
    type: str
    reason: str


class SafetyCheckResultDetail(BaseModel):
    """安全性チェック結果。"""

    is_violation: bool = False
    violations: list[str] = Field(default_factory=list)
    risk_level: str = Field(
        "None",
        description="None | Discomfort | Panic | LifeThreatening",
    )


class DuplicateCheckResult(BaseModel):
    """sourceHash ベースの冪等性チェック結果。"""

    has_duplicate: bool = False
    existing_nodes: list[dict[str, Any]] = Field(default_factory=list)


class SemanticDuplicateWarning(BaseModel):
    """Warning about a semantically similar existing node."""

    new_text: str
    existing_text: str
    similarity_score: float
    label: str
    node_id: str


class NarrativeIntakeResponse(BaseModel):
    """/api/narrative/intake のレスポンス本体。"""

    status: str = Field(
        ...,
        description="ok | validation_error | safety_violation | duplicate | dry_run",
    )
    nodesCreated: int = 0
    nodesMerged: int = 0
    relationshipsCreated: int = 0
    auditLogId: str | None = None
    embeddingsGenerated: int = 0
    rejectedNodes: list[RejectedNode] = Field(default_factory=list)
    rejectedRelationships: list[RejectedRelationship] = Field(default_factory=list)
    safetyCheck: SafetyCheckResultDetail = Field(
        default_factory=SafetyCheckResultDetail,
    )
    duplicateCheck: DuplicateCheckResult = Field(
        default_factory=DuplicateCheckResult,
    )
    warnings: list[str] = Field(default_factory=list)
    semanticDuplicates: list[SemanticDuplicateWarning] = Field(default_factory=list)
    message: str | None = None


# ---------------------------------------------------------------------------
# Preview context schemas (GET /api/narrative/preview-context)
# ---------------------------------------------------------------------------


class PreviewClientInfo(BaseModel):
    name: str | None = None
    dob: str | None = None
    age: int | None = None
    exists: bool = False


class PreviewExistingNgAction(BaseModel):
    action: str
    riskLevel: str
    reason: str | None = None


class NarrativePreviewContext(BaseModel):
    """Phase 3 プレビュー時に skill が参照する既存情報サマリー。"""

    client: PreviewClientInfo = Field(default_factory=PreviewClientInfo)
    existingNgActions: list[PreviewExistingNgAction] = Field(default_factory=list)
    duplicateCheck: DuplicateCheckResult = Field(default_factory=DuplicateCheckResult)


# ---------------------------------------------------------------------------
# Schema sync endpoint (GET /api/narrative/schema)
# ---------------------------------------------------------------------------


class NarrativeSchemaResponse(BaseModel):
    """Python 側 allowlist の現在値を返す (skill の schema/*.json 生成用)。"""

    allowed_labels: list[str]
    allowed_rels: list[str]
    merge_keys: dict[str, list[str]]
    allowed_create_labels: list[str]
    version: str

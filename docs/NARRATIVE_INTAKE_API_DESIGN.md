# /api/narrative/intake エンドポイント設計書

**バージョン**: v0.1 (Draft)
**作成日**: 2026-04-12
**目的**: Claude skill（`narrative-intake`）から呼び出し、既存 Python パイプライン（`lib/db_new_operations.py::register_to_database` + `lib/embedding.py`）を再利用して一貫性のある登録処理を提供する。

---

## 1. 背景と方針

### 問題意識

現在、narrative → Neo4j の経路は2系統ある:

1. **Gemini 経路**: `lib/ai_extractor.py` → `lib/db_new_operations.py::register_to_database()` → 自動 embedding 付与 + 監査ログ
2. **Claude skill 経路**: skill SKILL.md → neo4j MCP の `write_neo4j_cypher` 直叩き → embedding 未付与、allowlist 検証なし

後者は検証ゲートが弱く、embedding 自動付与も効かないため、**同じロジックを2度実装する** 問題がある。

### 解決方針

**FastAPI に薄いプロキシエンドポイント `/api/narrative/intake` を設ける**ことで、Claude skill が検証済みグラフ JSON をポストすれば、既存 Python パイプライン（`register_to_database`）をそのまま再利用できる構成にする。これにより:

- allowlist 検証 / MERGE キー判定 / Cypher インジェクション対策を Python 側で一元管理
- embedding 自動付与（`lib/embedding.py`）の恩恵を Claude skill からも受けられる
- 監査ログも統一フォーマットで記録される
- skill 側は「抽出 → 検証 → プレビュー → HTTP POST」のみに専念できる

---

## 2. エンドポイント仕様

### 2.1 登録エンドポイント

```
POST /api/narrative/intake
Content-Type: application/json
```

#### Request Body (Pydantic schema)

```python
from pydantic import BaseModel, Field
from typing import Any

class NarrativeNode(BaseModel):
    temp_id: str = Field(..., description="内部リンク用の仮ID (例: c1, log1)")
    label: str = Field(..., description="ノードラベル (PascalCase)")
    mergeKey: dict[str, Any] | None = Field(None, description="MERGE対象ラベルのみ必須")
    properties: dict[str, Any]

class NarrativeRelationship(BaseModel):
    source_temp_id: str
    target_temp_id: str
    type: str = Field(..., description="リレーション型 (UPPER_SNAKE_CASE)")
    properties: dict[str, Any] = Field(default_factory=dict)

class NarrativeAuditContext(BaseModel):
    user: str
    sessionId: str
    sourceType: str = Field(..., description="narrative | meeting | handover")
    sourceHash: str = Field(..., description="入力ナラティブのSHA256")
    clientName: str | None = None

class NarrativeIntakeRequest(BaseModel):
    nodes: list[NarrativeNode]
    relationships: list[NarrativeRelationship]
    auditContext: NarrativeAuditContext
    warnings: list[str] = Field(default_factory=list)
    dryRun: bool = Field(False, description="True の場合、DBに書き込まず検証結果のみ返す")
```

#### Response Body

```python
class NarrativeIntakeResponse(BaseModel):
    status: str                    # "ok" | "validation_error" | "safety_violation" | "duplicate"
    nodesCreated: int
    nodesMerged: int
    relationshipsCreated: int
    auditLogId: str | None
    embeddingsGenerated: int       # 自動付与されたembedding数
    rejectedNodes: list[dict]      # allowlist違反などで落ちたノード
    rejectedRelationships: list[dict]
    safetyCheck: dict              # {is_violation, violations, risk_level}
    duplicateCheck: dict           # {has_duplicate, existing_source_hashes}
    warnings: list[str]            # 入力warnings + サーバー側warnings
```

### 2.2 読み取り補助エンドポイント

Phase 3a（プレビュー時の既存データ参照）で skill から使うための軽量な読み取り API。

```
GET /api/narrative/preview-context?clientName={name}&sourceHash={hash}
```

Response:
```json
{
  "client": {"name": "...", "dob": "...", "age": 31, "exists": true},
  "existingNgActions": [
    {"action": "大きな音", "riskLevel": "Panic", "reason": "..."}
  ],
  "duplicateCheck": {
    "hasDuplicate": false,
    "existingNodes": []
  }
}
```

### 2.3 スキーマ同期エンドポイント

skill の `schema/*.json` 生成用に、Python 側の allowlist をそのまま返すエンドポイント（読み取り専用）。

```
GET /api/narrative/schema
```

Response:
```json
{
  "allowed_labels": [...],
  "allowed_rels": [...],
  "merge_keys": {...},
  "enum_values": {...},
  "version": "2026-04-12"
}
```

---

## 3. サーバー側処理フロー

```
┌──────────────────┐
│ Request 受信      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Pydantic バリデーション │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ allowlist 二重チェック │ ← Python側で再検証（defense in depth）
│ （LLMを信用しない）     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 安全性コンプライアンス │ ← check_safety_compliance() 流用
│ （既存NgAction照合） │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 冪等性チェック        │ ← sourceHash で既存ノード検索
│ （重複SupportLog等）│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ dryRun なら          │
│ 検証結果のみ返却      │ → End
│ そうでなければ次へ    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ register_to_database │ ← 既存関数を再利用
│ （+ 監査ログ自動記録） │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ embedding 自動付与   │ ← lib/embedding.py を流用
│ （SupportLog等）    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Response 返却       │
└──────────────────┘
```

---

## 4. ファイル配置（実装時）

```
api/
├── app/
│   ├── routers/
│   │   └── narrative_intake.py          # 新規: ルーター
│   ├── schemas/
│   │   └── narrative_intake.py          # 新規: Pydanticスキーマ
│   └── services/
│       └── narrative_intake_service.py  # 新規: ビジネスロジック
```

### api/app/routers/narrative_intake.py（骨子）

```python
from fastapi import APIRouter, HTTPException
from app.schemas.narrative_intake import (
    NarrativeIntakeRequest, NarrativeIntakeResponse
)
from app.services.narrative_intake_service import (
    validate_graph, run_safety_check, check_duplicates,
    register_narrative
)

router = APIRouter(prefix="/api/narrative", tags=["narrative-intake"])

@router.post("/intake", response_model=NarrativeIntakeResponse)
async def intake_narrative(req: NarrativeIntakeRequest):
    # 1. allowlist 二重検証
    validated, rejected = validate_graph(req)

    # 2. 安全性チェック
    safety = run_safety_check(validated, req.auditContext.clientName)
    if safety["is_violation"] and safety["risk_level"] == "LifeThreatening":
        raise HTTPException(
            status_code=409,
            detail={"status": "safety_violation", "safetyCheck": safety}
        )

    # 3. 冪等性チェック
    dup = check_duplicates(req.auditContext.sourceHash)

    # 4. dryRun
    if req.dryRun:
        return NarrativeIntakeResponse(
            status="ok",
            nodesCreated=0,
            nodesMerged=0,
            relationshipsCreated=0,
            auditLogId=None,
            embeddingsGenerated=0,
            rejectedNodes=rejected["nodes"],
            rejectedRelationships=rejected["relationships"],
            safetyCheck=safety,
            duplicateCheck=dup,
            warnings=req.warnings,
        )

    # 5. 実登録（既存パイプライン再利用）
    result = register_narrative(validated, req.auditContext)

    return NarrativeIntakeResponse(**result)
```

### api/app/services/narrative_intake_service.py（骨子）

```python
from lib.db_new_operations import (
    register_to_database,
    ALLOWED_LABELS,
    ALLOWED_REL_TYPES,
    MERGE_KEYS,
    run_query,
)
from lib.ai_extractor import check_safety_compliance
from lib.embedding import (
    embed_support_log_if_needed,
    embed_client_summary,
)

def validate_graph(req):
    """allowlist の二重検証（Python側の最終ライン）"""
    validated_nodes = []
    rejected_nodes = []
    for n in req.nodes:
        if n.label not in ALLOWED_LABELS:
            rejected_nodes.append({
                "temp_id": n.temp_id,
                "label": n.label,
                "reason": "label_not_allowed"
            })
            continue
        # mergeKey 必須チェック
        if n.label in MERGE_KEYS and not n.mergeKey:
            rejected_nodes.append({
                "temp_id": n.temp_id,
                "label": n.label,
                "reason": "merge_key_missing"
            })
            continue
        validated_nodes.append(n)

    validated_rels = []
    rejected_rels = []
    for r in req.relationships:
        if r.type not in ALLOWED_REL_TYPES:
            rejected_rels.append({
                "source": r.source_temp_id,
                "target": r.target_temp_id,
                "type": r.type,
                "reason": "rel_type_not_allowed"
            })
            continue
        validated_rels.append(r)

    return (
        {"nodes": validated_nodes, "relationships": validated_rels},
        {"nodes": rejected_nodes, "relationships": rejected_rels},
    )

def run_safety_check(graph, client_name):
    """既存NgActionと照合"""
    if not client_name:
        return {"is_violation": False, "violations": [], "risk_level": "None"}

    existing_ng = run_query(
        "MATCH (c:Client)-[:MUST_AVOID]->(ng:NgAction) "
        "WHERE c.name CONTAINS $name "
        "RETURN ng.action AS action, ng.riskLevel AS riskLevel, ng.reason AS reason",
        {"name": client_name}
    )
    # グラフ内のSupportLog.action等を文字列化して渡す
    narrative_text = "\n".join([
        n.properties.get("action", "")
        for n in graph["nodes"]
        if n.label == "SupportLog"
    ])
    return check_safety_compliance(narrative_text, existing_ng)

def check_duplicates(source_hash):
    """sourceHashで既存ノード検索"""
    existing = run_query(
        "MATCH (n) WHERE n.sourceHash = $h "
        "RETURN labels(n)[0] AS label, n.date AS date",
        {"h": source_hash}
    )
    return {"has_duplicate": len(existing) > 0, "existing_nodes": existing}

def register_narrative(validated, audit_context):
    """既存パイプラインで登録"""
    graph_dict = {
        "nodes": [n.model_dump() for n in validated["nodes"]],
        "relationships": [r.model_dump() for r in validated["relationships"]],
    }
    result = register_to_database(graph_dict, user_name=audit_context.user)
    # embedding 付与
    embedded_count = 0
    for n in validated["nodes"]:
        if n.label in ("SupportLog", "NgAction", "CarePreference"):
            embed_support_log_if_needed(n)  # ベストエフォート
            embedded_count += 1
    if audit_context.clientName:
        embed_client_summary(audit_context.clientName)
    return {
        "status": "ok",
        "nodesCreated": result.get("created", 0),
        "nodesMerged": result.get("merged", 0),
        "relationshipsCreated": result.get("rels_created", 0),
        "auditLogId": result.get("audit_id"),
        "embeddingsGenerated": embedded_count,
        "rejectedNodes": [],
        "rejectedRelationships": [],
        "safetyCheck": {"is_violation": False, "violations": [], "risk_level": "None"},
        "duplicateCheck": {"has_duplicate": False, "existing_nodes": []},
        "warnings": [],
    }
```

※ 上記は骨子であり、実装時には `register_to_database` の戻り値の実際のフィールド名に合わせて調整する必要がある。

---

## 5. Claude skill 側の呼び出し手順

skill の Phase 4 で以下のように呼び出す:

```
1. graph JSON を組み立てる
2. HTTP POST /api/narrative/intake with dryRun=true
3. レスポンスでエラー・警告を確認
4. ユーザー承認後、再度 POST with dryRun=false
5. 結果を表示
```

※ Claude skill から HTTP を叩く方法:
- 本プロジェクトでは Bash/fetch 系ツールで `curl -X POST http://localhost:8001/api/narrative/intake` を実行する想定
- もしくは MCP 経由で `mcp__neo4j__execute_query` に検証済み Cypher を投げる（fallback 経路）

---

## 6. セキュリティとプライバシー

- エンドポイントは **localhost バインド**（`127.0.0.1:8001`）を原則とし、外部公開しない
- 認証は当面プロセス内通信として省略可だが、将来的には FastAPI の `Depends` で API key 検証を追加
- 入力ナラティブの**本文は保存しない**（`sourceHash` のみ）。本文を残したい場合は `SupportLog.note` など明示フィールドを使う
- エラーレスポンスに個人情報（氏名・生年月日・電話番号等）を含めない
- ログは `clientName` のみ記録し、詳細プロパティはマスクする

---

## 7. 実装タスクリスト（見積）

| タスク | 規模 | 依存 |
|---|---|---|
| Pydanticスキーマ定義 (`schemas/narrative_intake.py`) | S | なし |
| Service 層実装 | M | 既存 `db_new_operations.py`, `embedding.py`, `ai_extractor.py` |
| Router 実装 | S | Service層 |
| `main.py` への Router 登録 | XS | Router |
| スキーマ同期スクリプト (`scripts/sync_narrative_intake_schema.py`) | S | Service層 |
| 単体テスト（dryRun, allowlist違反, 冪等性, safety違反） | M | Router |
| skill 側の呼び出しテスト | S | Router + skill |

合計見積: **2-3営業日**（既存パイプラインの再利用により工数を抑制）

---

## 8. 未解決事項（要決定）

1. **embedding 自動付与の粒度**: すべての SupportLog/NgAction/CarePreference に付与するか、明示フラグで選択するか
2. **sourceHash の計算範囲**: ユーザー入力の生テキストか、正規化後のテキストか（正規化後推奨）
3. **MeetingRecord の音声ファイル扱い**: skill 経由でバイナリを送る手段がないため、`filePath` のみ受け取るか、事前アップロードAPIを別途用意するか
4. **トランザクション分離**: `register_to_database` は内部で複数の `run_query` を呼ぶため、現状では単一トランザクション保証がない。将来的に `neo4j.write_transaction` で統一することを検討
5. **dryRun 時の safety check**: dryRun でも safety check は走らせるべき（本設計書ではそうしている）が、実装時に明確化

---

## 9. ロードマップ

| フェーズ | 内容 | 予定 |
|---|---|---|
| Phase 0 | 本設計書レビュー・承認 | 2026-04-12 |
| Phase 1 | 最小実装（validate + register、dryRunなし） | +1日 |
| Phase 2 | dryRun / safety check / 冪等性 追加 | +1日 |
| Phase 3 | embedding 連携・スキーマ同期エンドポイント | +1日 |
| Phase 4 | skill 側の呼び出し統合 + E2Eテスト | +1日 |

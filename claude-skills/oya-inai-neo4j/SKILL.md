---
name: oya-inai-neo4j
description: 仕分け済みの語りから、正本表で Neo4j が正本とされた事実だけを構造化して Neo4j 支援DBへ登録する子スキル。抽出は Claude 自身が行い、登録前に必ず人の確認を挟む。親スキル oya-inai-intake から仕分け YAML を受けて呼ばれるほか、「データベースに登録して」「Neo4j に入れて」「構造化して登録」などの発言時に単独でも必ずこのスキルを使用すること。narrative-extractor（nest-support）からの移植版であり、生育歴（LifeHistory）等は意図して抽出しない。
---

# oya-inai-neo4j — Neo4j への手続き（子・移植＋削る）

> 移植元: `nest-support/claude-skills/narrative-extractor`（2026-08-11 移植）。
> 本スキルは**削る移植**である——正本表で Obsidian が正本の事実を抽出対象から外した。
> 削った対象は下の固定リストが確定記録であり、勝手に増減しない。

## 最上位規則 — No Fabrication

1. **絶対に入力テキストにない情報を創作・推測しない**
2. 「一般的にこうだろう」という推測は禁止。不明な項目は null または空配列 [] とする
3. 抽出は分類であって補完ではない

## 抽出しないもの（固定リスト・削る移植の核心）

以下は**語りに含まれていても抽出しない**。正本は Obsidian Vault 側にある。

| 抽出しない | 落ち先（Vault） | 根拠 |
|---|---|---|
| **生育歴**（`LifeHistory` / `lifeHistories`） | person「ライフストーリー」節 | ADR-D9・正本表19。**本連携では LifeHistory ノードを作らない** |
| 試行錯誤の「学び」（次に同じ場面が来たらどうするか） | `trial` | 正本表8 |
| サービス等利用計画の内容 | `plan` | 正本表9（対応ノードなし） |
| モニタリング・会議の**判断の過程**（なぜそう決めたか） | `monitoring` / `meeting` | 正本表10・12 |

- `SupportLog`（出来事そのもの）は取る（正本表7）。学びの部分だけ Vault へ
- 会議は**開催の事実と逐語のみ**取る（正本表11）。決定の理由は Vault へ
- このリストは移植時（2026-08-11）に削った対象の**確定記録**。改訂は正本表の変更時のみ
- 判断規則の正典は隣のスキルの `oya-inai-intake/reference/dual-intake-routing.md` を参照する（**本スキルは写しを持たない**。写しを増やすと同期点が増える）

## 役割と境界

**本スキルは手続きだけを持つ。**どの事実を Neo4j に落とすかの判断は親（`oya-inai-intake`）が行う。単独起動で判断が必要になったら、親スキルの手順を先に通す。

- 入力: 親スキルの仕分け YAML（`person` / `source` / `to_neo4j`）、または人の直接指示＋テキスト
- **Obsidian 側（仮名のみ）と違い、こちらは実名を扱う。**このため人の確認が必須になる（下記 Step 3）

## 使用方法

### Step 1: 入力の受領

親 YAML の `to_neo4j` の断片、または語りのテキスト。`source.sha256`（raw/ 原本の**バイト列** sha256。oya-inai-vault が算出）を受け取り、`auditContext.sourceHash` に使う——両系突合の橋。

### Step 2: 構造化データの抽出

#### 抽出ルール（厳守）

1. **No Fabrication**（上記・最上位規則）
2. **暗黙知の抽出を優先する**
   - 「〜すると落ち着く」「〜が好き」→ carePreferences
   - 「〜は嫌がる」「〜するとパニック」→ ngActions（最重要）
   - 「今日〜した」「〜の対応で効果があった」→ supportLogs
3. **禁忌事項（NgAction）は最優先**
   - 「絶対に〜しないで」「〜するとパニック」を漏らさない
   - riskLevel を適切に判定：LifeThreatening / Panic / Discomfort
4. **固定リストの適用**: 生育歴・学び・計画・判断の過程が語りに含まれていても**抽出しない**（親の to_vault が拾う）
5. **日付の変換**: 元号（和暦）→ 西暦（YYYY-MM-DD）。明治元年=1868, 大正=1912, 昭和=1926, 平成=1989, 令和=2019
6. **Entity Resolution（同一対象の統合）**
   - 表記揺れは同一エンティティに統合（「健太」「けんた」「山田くん」→ 同一 Client）
   - 既存クライアントへの追記時は、Neo4j を検索して既存ノードと突合する
   - 統合に確信が持てない場合はユーザーに確認する

#### JSONスキーマ（lifeHistories は存在しない——移植時に削除）

```json
{
  "client": { "name": "氏名（必須）", "dob": "YYYY-MM-DD | null", "bloodType": null, "kana": null, "aliases": [] },
  "conditions": [ { "name": "特性・診断名", "status": "Active" } ],
  "ngActions": [ { "action": "してはいけないこと", "reason": "理由", "riskLevel": "LifeThreatening | Panic | Discomfort", "relatedCondition": null } ],
  "carePreferences": [ { "category": "食事/入浴/パニック時/移動/睡眠/服薬/コミュニケーション/その他", "instruction": "具体的な手順", "priority": "High | Medium | Low", "relatedCondition": null } ],
  "supportLogs": [ { "date": "YYYY-MM-DD", "supporter": "記録者", "situation": "状況", "action": "対応", "effectiveness": "Effective | Neutral | Ineffective", "note": "" } ],
  "certificates": [ { "type": "療育手帳/精神障害者保健福祉手帳/身体障害者手帳/障害福祉サービス受給者証/自立支援医療受給者証", "grade": "等級", "nextRenewalDate": "YYYY-MM-DD" } ],
  "keyPersons": [ { "name": "氏名", "relationship": "続柄", "phone": "電話", "role": "役割", "rank": 1 } ],
  "guardians": [ { "name": "氏名/法人名", "type": "成年後見/保佐/補助/任意後見", "phone": "", "organization": "" } ],
  "hospitals": [ { "name": "病院名", "specialty": "診療科", "phone": "", "doctor": "担当医名" } ],
  "wishes": [ { "content": "願いの内容", "date": "YYYY-MM-DD" } ]
}
```

親 YAML 経由の場合、上記スキーマ外のラベル（CareRole / Relative / ServiceProvider / MeetingRecord / Review 等）は API のノード断片（label / mergeKey / properties）として**そのまま**組み立てる。正典の許可リスト（SCHEMA_CONVENTION / SEMANTIC_MODEL）にあるものだけを使い、廃止名は書かない。

### Step 3: 人の確認（必須・省略不可）

抽出結果（JSON または API 断片）と dryRun の検証結果をユーザーに提示し、**明示的な承認を得てから**登録する。

- **確認なしの登録経路を作らない。**「ついでに登録しておきました」は本スキルでは事故である
- 実名が入るため、間違えたときの回復コストが Obsidian 側と違う（承認の非対称）
- 親スキルの仕分け宣言への黙認は**この承認を兼ねない**

### Step 4: 登録（書き込み経路の二段構え）

```
API が応答する？（セッション内で一度だけ確認し、結果を保持する）
  ├ はい → POST /api/narrative/intake（dryRun → Step 3 の確認 → 本実行）
  └ いいえ → neo4j MCP execute_query（★警告を出す）
```

#### 第一経路: API（推奨）

`POST /api/narrative/intake` に nodes / relationships / auditContext を送る。**まず `dryRun: true`**で検証し、rejected が 0 であることと safetyCheck / duplicateCheck の結果を Step 3 で人に見せ、承認後に `dryRun: false` で本実行する。

```json
{
  "nodes": [
    { "temp_id": "c1", "label": "Client", "mergeKey": { "name": "..." }, "properties": {} },
    { "temp_id": "ng1", "label": "NgAction", "mergeKey": { "action": "..." },
      "properties": { "reason": "...", "riskLevel": "Panic", "source": "家族", "status": "Pending" } }
  ],
  "relationships": [
    { "source_temp_id": "c1", "target_temp_id": "ng1", "type": "MUST_AVOID", "properties": {} }
  ],
  "auditContext": {
    "user": "登録実行者名",
    "sessionId": "セッションID",
    "sourceType": "narrative",
    "sourceHash": "raw/ 原本のバイト列 sha256（64桁）",
    "clientName": "対象クライアント名"
  },
  "dryRun": true
}
```

門番（allowlist）・重複検査・意味的重複の警告・安全検査・監査コンテキストは API 側が担う。

#### 代替経路: neo4j MCP 直（API 停止時のみ）

必ず次の警告を出してから進む:

> ⚠️ API が起動していないため、直接データベースへ書き込みます。**重複検査・安全検査・監査コンテキストは適用されません。**API を起動してから実行することを推奨します。

Cypher テンプレート（移植元由来。**LifeHistory のテンプレートは移植時に削除した**）:

**クライアント基本情報:**
```cypher
MERGE (c:Client {name: $name})
SET c.dob = CASE WHEN $dob IS NOT NULL THEN date($dob) ELSE c.dob END,
    c.bloodType = COALESCE($blood, c.bloodType),
    c.kana = COALESCE($kana, c.kana),
    c.aliases = $aliases
```

**特性・診断:**
```cypher
MATCH (c:Client {name: $client})
MERGE (con:Condition {name: $name})
SET con.status = $status
MERGE (c)-[:HAS_CONDITION]->(con)
```

**禁忌事項（NgAction）- 最重要（クライアント配下で MERGE）:**
```cypher
MATCH (c:Client {name: $client})
MERGE (c)-[:MUST_AVOID]->(ng:NgAction {action: $action})
ON CREATE SET ng.reason = $reason, ng.riskLevel = $risk, ng.status = 'Pending'
ON MATCH SET  ng.reason = COALESCE($reason, ng.reason),
              ng.riskLevel = COALESCE($risk, ng.riskLevel)
```

**推奨ケア（CarePreference）:**
```cypher
MATCH (c:Client {name: $client})
MERGE (c)-[:REQUIRES]->(cp:CarePreference {category: $cat, instruction: $inst})
ON CREATE SET cp.priority = $pri, cp.status = 'Pending'
ON MATCH SET  cp.priority = COALESCE($pri, cp.priority)
```

**手帳・受給者証（Certificate。type×grade の複合キー・DRIFT-08 対応済み）:**
```cypher
MATCH (c:Client {name: $client})
MERGE (c)-[r:HAS_CERTIFICATE]->(cert:Certificate {type: $type, grade: COALESCE($grade, '不明')})
SET cert.nextRenewalDate = CASE WHEN $renewal IS NOT NULL THEN date($renewal) ELSE cert.nextRenewalDate END,
    r.status = COALESCE(r.status, 'Active')
```

**キーパーソン（KeyPerson）:**
```cypher
MATCH (c:Client {name: $client})
MERGE (c)-[r:HAS_KEY_PERSON]->(kp:KeyPerson {name: $name})
SET kp.phone = COALESCE($phone, kp.phone),
    kp.relationship = COALESCE($rel, kp.relationship),
    kp.role = COALESCE($role, kp.role),
    r.rank = COALESCE($rank, r.rank)
```

**後見人（Guardian）:**
```cypher
MATCH (c:Client {name: $client})
MERGE (c)-[:HAS_LEGAL_REP]->(g:Guardian {name: $name})
SET g.type = COALESCE($type, g.type),
    g.phone = COALESCE($phone, g.phone),
    g.organization = COALESCE($org, g.organization)
```

**医療機関（Hospital。かかりつけ医は Doctor ノード）:**
```cypher
MATCH (c:Client {name: $client})
MERGE (h:Hospital {name: $name})
SET h.specialty = $spec, h.phone = $phone
MERGE (c)-[:TREATED_AT]->(h)
FOREACH (_ IN CASE WHEN $doc IS NULL OR $doc = '' THEN [] ELSE [1] END |
    MERGE (d:Doctor {name: $doc})
    MERGE (h)-[:HAS_DOCTOR]->(d))
```

**願い（Wish）:**
```cypher
MATCH (c:Client {name: $client})
CREATE (w:Wish {content: $content, status: 'Active', date: date($date)})
CREATE (c)-[:HAS_WISH]->(w)
```

**支援記録（SupportLog）:**
```cypher
MERGE (s:Supporter {name: $supporter})
WITH s
MATCH (c:Client {name: $client})
CREATE (log:SupportLog {
    date: date($date), situation: $situation, action: $action,
    effectiveness: $effectiveness, note: $note
})
CREATE (s)-[:LOGGED]->(log)-[:ABOUT]->(c)
```

### Step 5: 監査ログ（必須）

- **API 経由**: auditContext が監査記録を担う（sourceHash を必ず入れる）
- **MCP 直**: すべての書き込みの後、AuditLog ノードを作成する:

```cypher
CREATE (al:AuditLog {
    timestamp: datetime(), user: $user, action: $action,
    targetType: $targetType, targetName: $targetName,
    details: $details, clientName: $clientName, sourceHash: $sourceHash
})
RETURN al.timestamp AS 記録日時
```

1回の登録で複数ノードを作成した場合、クライアント単位で1件にまとめてよい。

## 継承する規律（write-gate・証拠鮮度モデル）

- **DELETE 禁止**（support-db-write-gate §5）。削除が要る場面は人へ（明示の承認が必須）
- **クライアント単位 MERGE**（同 §2）。NgAction / CarePreference は Client 配下でリレーションごと MERGE し、他クライアントとノードを共有しない
- **更新対象は完全一致で特定**（同 §4）。曖昧照合で更新しない
- **証拠・鮮度モデル**（SCHEMA_CONVENTION v3.4 §7.9 / SEMANTIC_MODEL v1.6 BRS-13）: AI 抽出由来の NgAction / CarePreference は `status: Pending` で作成（人の承認で Active 昇格・AuditLog 必須）。既存事実と食い違う情報は**上書きせず** `CONTRADICTS`（claim / raisedAt / source）で保留し、人が裁定する。鮮度更新は Review＋`CONFIRMS`＋`lastConfirmedAt`（routing §4。DRIFT-13 解消済みのため API 経由で書ける）

## 命名規則（厳守）

- ノード: PascalCase (`Client`, `NgAction`) / リレーション: UPPER_SNAKE_CASE (`MUST_AVOID`) / プロパティ: camelCase (`riskLevel`)
- 廃止名 (`PROHIBITED`, `PREFERS`, `EMERGENCY_CONTACT`, `RELATES_TO`, `HAS_GUARDIAN`, `HOLDS`) は書き込み禁止

## 関連

- 親スキル: `oya-inai-intake`（仕分けの判断・YAML の出所）
- 兄弟スキル: `oya-inai-vault`（Obsidian への手続き・sha256 の算出元）
- 判断規則の正典: `oya-inai-intake/reference/dual-intake-routing.md`（写しは持たない）
- 書き込み規律の正典: `support-db-write-gate`／SCHEMA_CONVENTION v3.4／SEMANTIC_MODEL v1.6

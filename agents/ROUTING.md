# スキル＆Neo4j MCPルーティングガイド

**目的:** 5つのスキルとNeo4j MCPツールの使い分けを定義する。

**アーキテクチャ:**
- **読み取り系スキル（neo4j-support-db / provider-search）** は Cypher テンプレートを提供し、汎用 neo4j MCP の `read_neo4j_cypher` / `write_neo4j_cypher` で実行する。
- **書き込み系スキル（narrative-intake）** は FastAPI `/api/narrative/intake` エンドポイント（port 8001）経由で allowlist 二重検証・安全性チェック・冪等性チェック・embedding 付与を行う。Cypher 直接書き込みではない。
- **DB非依存スキル（emergency-protocol / ecomap-generator）** はプロトコル参照・可視化のみ。

---

## スキル一覧

### 1. neo4j-support-db（計画相談支援）

**SKILL.md:** `~/.claude/skills/neo4j-support-db/SKILL.md`
**Neo4jインスタンス:** `bolt://localhost:7687`
**対象業務:** 障害福祉サービスの利用調整、計画相談支援

**トリガーワード:**
- クライアント名（山田健太、佐々木真理 等）
- パニック、緊急、禁忌、支援記録
- キーパーソン、手帳、更新期限、後見人
- 配慮事項、ケアパターン、生育歴

**Cypherテンプレート（8種）:**

| # | テンプレート | 用途 | 種別 |
|---|------------|------|------|
| 1 | クライアント一覧 | 全クライアントの基本情報と関連データ件数 | read |
| 2 | クライアントプロフィール | 4本柱の包括的情報（NgAction/CarePreference/KeyPerson/Certificate等） | read |
| 3 | 統計情報 | ノードタイプ別件数とリレーション数 | read |
| 4 | 更新期限チェック | N日以内に期限切れの手帳・受給者証 | read |
| 5 | 支援記録取得 | クライアントの支援記録履歴 | read |
| 6 | ケアパターン発見 | 効果的だった対応の自動検出 | read |
| 7 | 監査ログ | 操作履歴の確認 | read |
| 8 | 変更履歴 | クライアント情報の変更追跡 | read |

---

### 2. provider-search（事業所検索・管理）

**SKILL.md:** `~/.claude/skills/provider-search/SKILL.md`
**Neo4jインスタンス:** `bolt://localhost:7687`（support-dbと同じ）
**対象業務:** 福祉サービス事業所の検索・利用管理・口コミ評価

**トリガーワード:**
- 事業所、空き状況、口コミ、評価
- サービス種類（生活介護、就労B型、グループホーム等）
- 代替、別の事業所、紐付け

**Cypherテンプレート（9種）:**

| # | テンプレート | 用途 | 種別 |
|---|------------|------|------|
| 1 | 事業所検索（基本） | サービス種類・地域・空きで絞り込み | read |
| 2 | クライアント利用事業所 | 利用中・調整中・終了のサービス一覧 | read |
| 3 | 代替事業所検索 | 利用中サービスの代替候補 | read |
| 4 | 口コミ取得 | 事業所の口コミ一覧 | read |
| 5 | 評価サマリー | 口コミの集計（◎○△×件数とスコア） | read |
| 6 | 口コミで事業所検索 | カテゴリ別の高評価事業所 | read |
| 7 | クライアント紐付け | クライアント↔事業所のUSES_SERVICE作成 | write |
| 8 | 口コミ登録 | ProviderFeedbackノード作成 | write |
| 9 | 空き状況更新 | availability/currentUsersの更新 | write |

**データ特記:** WAM NETインポートにより新形式(camelCase)と旧形式(snake_case)が混在。テンプレートはCOALESCEで統一処理。

---

### 3. emergency-protocol（緊急時プロトコル）

**SKILL.md:** `~/.claude/skills/emergency-protocol/SKILL.md`
**対象業務:** 緊急時の対応手順ガイド（データベース非依存）

**トリガーワード:**
- 緊急、SOS、倒れた、救急、パニック
- 親亡き後、急変

**内容:**
- 緊急対応フローチャート
- Safety Firstプロトコル
- Parent Downプロトコル（主介護者不在時）
- 関係機関への連絡手順

---

### 4. ecomap-generator（エコマップ生成）

**SKILL.md:** `~/.claude/skills/ecomap-generator/SKILL.md`
**対象業務:** 支援ネットワークの可視化

**トリガーワード:**
- エコマップ、ネットワーク図、支援関係図

**出力形式:** Mermaid / SVG

---

### 5. narrative-intake（長文ナラティブ → 構造化書き込み）

**SKILL.md:** `~/.claude/skills/narrative-intake/SKILL.md`
**書き込み先:** FastAPI `http://localhost:8001/api/narrative/intake`（Neo4j port 7687 は API が仲介）
**対象業務:** 計画相談支援のアセスメント記録、面談録、手書きメモ等の長文をそのまま Neo4j へ構造化保存

**トリガーワード:**
- 「以下のアセスメント記録を登録して」「この面談メモをDBに入れて」
- 「本人の生育歴と現状を記録」「新規ケース登録」
- 長文narrative（200字以上）＋クライアント名

**処理フロー（4フェーズ・プロトコル）:**

| Phase | 内容 | 成果物 |
|-------|------|--------|
| 1. Extraction | 日本語前処理（NFC正規化・元号→西暦・敬称除去・相対時間解決）→ LifeStage 単位チャンキング → Gemini 構造化 | temp_id 付きノード＋リレーション JSON |
| 2. Validation | allowlist（17ラベル／21リレーション）で二重検証 → 拒否候補の列挙 | validated / rejected 分離済みグラフ |
| 3. Preview | `/api/narrative/preview-context` で既存 NgAction / 重複候補を取得 → ユーザーに差分プレビュー提示 | 人間のレビュー |
| 4. Write + Audit | `/api/narrative/intake`（dryRun=false）で書き込み。MERGE ベース冪等化＋sourceHash 重複検出＋LifeThreatening 安全性違反で 409＋AuditLog 自動生成＋embedding 自動付与 | 登録済みノード件数・monkey-patch 可能な safetyCheck / duplicateCheck レスポンス |

**Cypherテンプレート:** なし（すべて FastAPI ルーター `api/app/routers/narrative_intake.py` 経由）

**重要なガードレール:**
- ALLOWED_LABELS / ALLOWED_REL_TYPES / MERGE_KEYS の単一情報源は `api/app/lib/db_operations.py`。
  skill 側 `schema/*.json` は `scripts/sync_narrative_intake_schema.py` で同期する（`--check` でドリフト検出、`--apply` で反映）。
- 既存 NgAction（LifeThreatening）と衝突する narrative は 409 で拒否される。
- sourceHash（入力全文の SHA256）で同じ記録を二重登録しない。

**書き込み後の分析:** 登録完了後は通常通り neo4j-support-db / provider-search / ecomap-generator で可視化・分析可能。

---

### 6. neo4j MCP（汎用データベースアクセス）

**接続先:** `bolt://localhost:7687`（デフォルト）

**ツール:**

| ツール | 用途 |
|--------|------|
| `get_neo4j_schema` | スキーマ取得 |
| `read_neo4j_cypher` | 読み取りクエリ実行 |
| `write_neo4j_cypher` | 書き込みクエリ実行 |

**重要:** スキルのCypherテンプレートはこのMCPツールで実行する。

---

## ルーティング判断フロー

```
ユーザー入力
│
├─ 緊急ワード検出？（パニック、SOS、倒れた、救急）
│  ├─ YES → emergency-protocol スキルで手順確認
│  │       └─ データ取得が必要な場合 → neo4j-support-db テンプレート2
│  └─ NO → 続行
│
├─ 長文narrative（200字以上）＋「登録」「記録」「DBに入れて」？
│  └─ YES → narrative-intake スキル（4フェーズプロトコル）
│          Phase 1: 日本語前処理＋Gemini構造化
│          Phase 2: allowlist二重検証
│          Phase 3: /api/narrative/preview-context で既存データ確認
│          Phase 4: /api/narrative/intake で書き込み＋embedding付与
│
├─ クライアント名が含まれる？
│  ├─ YES → neo4j-support-db スキル
│  └─ NO → 続行
│
├─ 事業所検索・口コミに関する話題？
│  └─ YES → provider-search スキル
│
├─ エコマップ・ネットワーク図？
│  └─ YES → ecomap-generator スキル
│
├─ 一般的なNeo4j操作？（スキーマ確認、カスタムクエリ）
│  └─ YES → neo4j MCP を直接使用
│
└─ 判断不能
   └─ ユーザーに確認する
```

---

## Neo4jインスタンス

Neo4j インスタンスは 1 つ（support-db）。

| インスタンス | Bolt | HTTP | 対象スキル |
|------------|------|------|-----------|
| support-db | localhost:7687 | localhost:7474 | neo4j-support-db, provider-search |

---

## データモデル

### support-db（障害福祉）
- 中心ノード: `:Client`
- 禁忌: `:NgAction`（riskLevel付き）
- ケア指示: `:CarePreference`
- 支援記録: `:SupportLog`
- 事業所: `:ServiceProvider`, `:ProviderFeedback`

---

## 併用パターン

単一のケースで複数のスキルを使うことがある。

**例1：緊急対応から事業所調整まで一連で行う場合**
1. 緊急手順 → emergency-protocol スキル
2. 障害福祉情報 → neo4j-support-db テンプレート2（プロフィール）
3. 事業所検索 → provider-search テンプレート1
4. エコマップ → ecomap-generator スキル

**例2：新規ケースのアセスメント記録 → 書き込み → 即座に分析**
1. 長文narrative受領 → narrative-intake スキルで 4 フェーズ書き込み
2. 書き込み完了後、Client名をキーに neo4j-support-db テンプレート2（4本柱プロフィール）で登録内容を検証
3. 既存類似ケースの確認 → neo4j-support-db テンプレート6（ケアパターン発見）
4. 支援計画に合う事業所候補 → provider-search テンプレート1
5. 支援ネットワーク可視化 → ecomap-generator スキル

# 発展的運用ガイド: Claude Desktop Skills との連携

このシステムは、ダッシュボードUIでの記録・管理に加え、**Claude Desktop + Skills + Neo4j MCP**を活用した高度な分析・提案が可能です。

---

## アーキテクチャ概要

### ワークフロー

| レイヤー | ツール | 役割 |
|:--|:--|:--|
| **Next.js フロントエンド** | ブラウザUI（port 3001） | ダッシュボード・記録・検索・チャット・インテーク |
| **FastAPI バックエンド** | API（port 8001） | REST + WebSocket + エージェント |
| **Layer 3（紫）** | **Claude Desktop + Skills** | **分析・提案・複雑な操作** |

> **Note**: 旧 Streamlit UI（Layer 1・2）は `archive/` に退避済みです。

### Skills + Neo4j MCP 方式（推奨）

```
ユーザー → Claude Desktop → Skills（SKILL.md）→ Neo4j MCP → Neo4j DB
```

Claude が SKILL.md に含まれるCypherテンプレートを参照し、汎用 Neo4j MCP の `read_neo4j_cypher` / `write_neo4j_cypher` ツールでクエリを実行します。

**メリット:**
- Python/uv/Gemini API キー不要
- 軽量（Skills は SKILL.md テキストファイルのみ）
- Cypherテンプレートを直接確認・編集可能
- 新しいSkillの追加が容易

---

## セットアップ

初回セットアップは [QUICK_START.md](./QUICK_START.md) を参照してください。

---

## 5つの Skills

### 1. neo4j-support-db（障害福祉）

**対象**: 知的障害・精神障害のある方の支援情報管理

**4本柱データモデル:**
1. 本人性（Identity & Narrative）
2. ケアの暗黙知（Care Instructions）
3. 法的基盤（Legal Basis）
4. 危機管理ネットワーク（Safety Net）

**主なCypherテンプレート:**
- クライアント一覧・プロフィール取得
- 支援記録の蓄積と効果的ケアパターン発見
- 手帳・受給者証の更新期限チェック
- 監査ログの取得
- 支援記録の全文検索（キーワード横断検索）
- 支援記録の時系列チェーン追跡（FOLLOWS リレーション）
- **セマンティック検索**（意味ベースの類似検索、ダッシュボードUIからも利用可能）

**プロンプト例:**
```
山田健太さんのプロフィールを表示して
```
```
更新期限が近い証明書を全クライアント分チェックして
```
```
佐藤さんの最近の支援記録を分析して、効果的だったケアパターンを教えて
```

---

### 2. provider-search（事業所検索）

**対象**: WAM NET 事業所データの検索・口コミ管理

**機能:**
- サービス種類・地域・空き状況での事業所検索
- クライアントと事業所の紐付け
- 口コミ評価の登録・検索（◎○△× の4段階）
- 代替事業所の提案

**注意**: WAM NETデータは camelCase/snake_case が混在しているため、全クエリで COALESCE パターンを使用

**プロンプト例:**
```
北九州市の生活介護事業所で空きのあるところを探して
```
```
行動障害対応の評価が高い事業所を教えて
```
```
山田さんの就労B型の代替事業所を探して。現在の事業所が閉鎖予定のため。
```

---

### 3. emergency-protocol（緊急時対応）

**対象**: 緊急時の情報取得に特化（読み取り専用）

**Safety First プロトコル:**
1. 🔴 NgAction（禁忌事項）— LifeThreatening → Panic → Discomfort
2. 🟡 CarePreference（推奨ケア）
3. 🟢 KeyPerson（緊急連絡先）— 優先順位順
4. 🏥 Hospital（かかりつけ医）
5. 👤 Guardian（後見人）

**自動トリガーワード**: パニック、緊急、発作、暴れる、倒れた 等

**プロンプト例:**
```
田中さんがパニックを起こしています。緊急対応情報をください。
```
```
山田さんの緊急連絡先を教えて
```

---

### 4. ecomap-generator（エコマップ生成）

**対象**: 支援ネットワークの可視化

**4つのテンプレート:**
| テンプレート | 用途 |
|-------------|------|
| `full_view` | 包括的な全体像（初回面談時） |
| `support_meeting` | サービス担当者会議用 |
| `emergency` | 緊急時体制（Safety First） |
| `handover` | 引き継ぎ用（履歴含む） |

**出力形式:**
- Mermaid 形式（Claude Desktop でそのまま表示可能）
- SVG 形式（印刷・共有用）
- **draw.io 形式**（ダッシュボードの「可視化」→「エコマップ」から生成・ダウンロード可能。draw.ioアプリで自由に編集できます）

**プロンプト例:**
```
田中太郎さんのエコマップを作成して
```
```
佐藤さんの緊急時体制のエコマップをMermaid形式で表示して
```

> **ヒント**: Claude Desktop を使わなくても、Next.js フロントエンドの「可視化」→「エコマップ」ページからGUIで draw.io 形式のエコマップを生成できます。

---

## Skills の選択ガイド

| やりたいこと | 使うSkill |
|-------------|----------|
| クライアントの情報確認 | `neo4j-support-db` |
| 支援記録の追加・分析 | `neo4j-support-db` |
| 訪問前の準備 | `neo4j-support-db` |
| 引き継ぎ資料の作成 | `neo4j-support-db` |
| 事業所の検索・比較 | `provider-search` |
| 緊急時の即時対応 | `emergency-protocol` |
| 支援関係の可視化（Mermaid/SVG） | `ecomap-generator` |
| 支援関係の可視化（draw.io） | Next.js「可視化」→「エコマップ」 |
| 証明書の期限管理 | `neo4j-support-db` |
| 口コミの参照・登録 | `provider-search` |
| 類似ケースの検索 | `neo4j-support-db` |
| 意味的なキーワード検索 | Next.js「活用」→「セマンティック検索」 |

---

## レガシー MCP Server 方式

Skills方式を使わず、従来の MCP Server（`server.py`）を使うことも可能です。

### 必要な環境

- Python 3.12+
- uv（パッケージマネージャー）
- Gemini API キー

### セットアップ

```bash
# 依存関係のインストール
uv sync

# 環境変数の設定
cat > .env << EOF
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
GEMINI_API_KEY=your_api_key_here
EOF
```

### Claude Desktop 設定

`configs/claude_desktop_config.mcp.json` を参照し、パスを実際の環境に合わせて編集してください。

### 提供ツール（40+）

レガシー MCP は以下のカテゴリのツールを提供します:

- **緊急対応**: `search_emergency_info`, `get_visit_briefing`
- **日常支援**: `add_support_log`, `get_support_logs`, `discover_care_patterns`
- **分析・計画**: `get_client_profile`, `get_handover_summary`, `check_renewal_dates`
- **事業所管理**: `search_service_providers`, `find_alternative_providers`
- **監査**: `get_audit_logs`, `get_client_change_history`

> **注意**: Skills方式が推奨です。レガシー方式は将来的に非推奨になる可能性があります。

---

## Skills のカスタマイズ

### SKILL.md の編集

Skills は `~/.claude/skills/` にシンボリックリンクされているため、`claude-skills/` ディレクトリの SKILL.md を直接編集できます。変更はリアルタイムで反映されます。

```bash
# 例: neo4j-support-db の Cypher テンプレートを編集
vim claude-skills/neo4j-support-db/SKILL.md
```

### 新しい Skill の追加

1. `claude-skills/` に新しいディレクトリを作成
2. `SKILL.md` を作成（既存のSkillを参考に）
3. `setup.sh` の `SKILLS` 配列に追加
4. `./setup.sh --skills` を再実行

---

## Ollama（ローカルLLM）サポート

チャット機能で Gemini の代わりに Ollama を使用できます。オフライン環境や API キー不要の運用に適しています。

```bash
# 環境変数で初期プロバイダーを指定
export CHAT_PROVIDER=ollama
export OLLAMA_MODEL=gemma4:26b
```

チャット中に「gemma4を使って」「claudeに切り替えて」と入力すると、`model_switch.py` が動的にLLMを切り替えます。セッション履歴は切り替え後も保持されます。

---

## 音声対話型インテーク

Next.js フロントエンドの `/intake` ページで、音声対話による7本柱インテークが可能です。

- Web Speech API による音声認識
- WebSocket によるリアルタイムストリーミング応答
- `intake_agent.py` が7本柱に沿って対話的に情報を収集

---

## トラブルシューティング

### Skills が認識されない

```bash
# シンボリックリンクの確認
ls -la ~/.claude/skills/

# 再インストール
./setup.sh --skills
```

### Neo4j MCP に接続できない

```bash
# Neo4j の状態確認
docker ps | grep neo4j
curl -s http://localhost:7474

# npx の動作確認
npx -y @anthropic/neo4j-mcp-server --help
```

### Cypher クエリがエラーになる

1. Neo4j Browser (http://localhost:7474) で直接クエリを実行して確認
2. SKILL.md 内のテンプレートとスキーマが一致しているか確認
3. APOC プラグインが有効か確認: `RETURN apoc.version()`

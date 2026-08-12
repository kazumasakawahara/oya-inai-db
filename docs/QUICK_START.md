# クイックスタートガイド

インストーラーを使えば、コマンドに慣れていなくても始められます。UIは Next.js の Web画面（port 3001）+ FastAPI（port 8001）+ Neo4j（Docker, port 7687）です。

---

## いちばん簡単な始め方（推奨）

**Mac:**

```bash
curl -sL https://raw.githubusercontent.com/kazumasakawahara/oya-inai-db/main/installer/install-mac.sh | bash
```

**Windows:** PowerShell で `installer/install-windows.ps1` を実行。

インストーラーが行うこと:

1. 前提条件（Docker Desktop, Node.js）の確認・インストール案内
2. リポジトリのダウンロード
3. Neo4j データベースの起動
4. 接続テスト

完了後、`start.command`（Mac）/ `start.bat`（Windows）を実行し、ブラウザで **http://localhost:3001** を開けば使い始められます。

> Neo4j のブラウザUIは http://localhost:7474（認証: neo4j / password）。通常の操作では使いません。

---

## 手動セットアップ（開発者向け）

| ツール | 必須 | 用途 |
|-------|------|------|
| Docker Desktop | ○ | Neo4j データベース |
| Node.js / pnpm | ○ | Next.js フロントエンド |
| Python 3.12+ / uv | ○ | FastAPI バックエンド |
| Git | ○ | リポジトリの取得 |

```bash
git clone https://github.com/kazumasakawahara/oya-inai-db.git
cd oya-inai-db

# 1. Neo4j の起動
./setup.sh

# 2. 設定ファイル（Neo4j 接続情報のみ。通常はそのままで OK）
cp .env.example .env

# 3. バックエンド（FastAPI）
cd api && uv run uvicorn app.main:app --reload --port 8001

# 4. フロントエンド（Next.js）— 別ターミナルで
cd frontend && pnpm install && pnpm dev --port 3001
```

---

## デモデータで試す

実在の人物とは無関係の**合成データ**（デモ利用者・支援記録・感情シミュレーション）を投入できます。

```bash
./installer/load-demo-data.sh        # Windows: installer\load-demo-data.ps1
```

---

## Claude の準備 — 閲覧・記録だけなら不要です

**Web 画面の機能（利用者台帳・緊急照会・更新期限アラート・出来事の記録・面談記録）は Claude なしですべて動きます。** 一方、**新しい方の登録**と、語り・文書からの**まとめ入力**は Claude（Anthropic 社の AI アシスタント）に頼む設計です。データベースを育てていくには、次の 2 つを用意してください。

1. **Claude の有料プラン**を契約する（https://claude.com）
2. **Claude Desktop** をインストールし、MCP でデータベースにつなぐ（→ [mcp-setup.md](./mcp-setup.md)、使い方は [manuals/ç¦ç¥å°éè·ã®ããã®å®å¨å°å¥ããã¥ã¢ã«.md](./manuals/ç¦ç¥å°éè·ã®ããã®å®å¨å°å¥ããã¥ã¢ã«.md) 第 6 章）

`.env` に AI のキーを書く欄はありません（AI は Claude 一本・2026-08 方針決定）。Claude を設定しなくてもエラーにはならず、Web 画面はそのまま使えます。

---

## 動作確認

1. http://localhost:3001 を開く → ダッシュボードが表示される
2. サイドバーの「クライアント一覧」→ デモデータを入れた場合は利用者が並ぶ
3. 「出来事の記録」→ ①利用者を選ぶ→②本人の様子を選ぶ…と番号順に進めば記録できる

### 調子が悪いとき

```bash
./scripts/doctor.sh          # 接続状態の一括診断

docker ps                    # コンテナの状態確認
docker logs oya-inai-db-neo4j # Neo4j のログ
docker compose restart neo4j # Neo4j の再起動
```

---

## 次のステップ

- [ADVANCED_USAGE.md](./ADVANCED_USAGE.md) — 各画面の詳しい使い方
- [manuals/SETUP_GUIDE.md](./manuals/SETUP_GUIDE.md) — つまずきやすい箇所を含む詳細セットアップ
- [manuals/PRIVACY_GUIDELINES.md](./manuals/PRIVACY_GUIDELINES.md) — 実在の方の情報を扱う前に必読

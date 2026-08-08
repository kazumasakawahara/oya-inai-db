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

# 2. 設定ファイル（AIを使わないなら省略可）
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

## AI（LLM）の設定 — しなくても使えます

**中核機能（利用者台帳・緊急照会・更新期限アラート・訪問前ブリーフィング）は AI なしですべて動きます。** AI機能（ナラティブAI抽出・AIチャット・音声文字起こし・意味検索）を使う場合だけ、次のいずれかを設定してください。

### Ollama（ローカル・¥0・データが外に出ない）

```bash
# macOS
brew install ollama
ollama pull gemma4:26b
```

Web画面の「LLM設定」でチャットの使用モデルを切り替えられます。個人情報を扱う本運用にはこちらを推奨します。

### Gemini API（無料枠あり）

[Google AI Studio](https://aistudio.google.com/) でAPIキーを取得し、`.env` に設定します:

```bash
GEMINI_API_KEY=your_api_key
```

> **注意（2026年8月確認）**: Gemini 無料枠は入力データが Google のプロダクト改善に利用されます。実在の方の個人情報を扱う運用では Ollama か Gemini 有料枠を使ってください。無料枠はデモデータでの試用向けです。

APIキーを設定しない場合もエラーにはなりません。AI機能の画面に「AIの設定が必要です」と案内が出るだけです。

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

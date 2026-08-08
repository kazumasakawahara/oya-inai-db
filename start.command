#!/bin/bash
# 親亡き後支援データベース - 一発起動スクリプト（macOS）
# Windows 版 start.bat と同じ動作: Neo4j + API(8001) + フロントエンド(3001)
cd "$(dirname "$0")"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  親亡き後支援データベース - 一発起動スクリプト"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. 前提条件チェック ──────────────────────────────
if ! docker info >/dev/null 2>&1; then
    echo "[ERROR] Docker Desktop が起動していません。"
    echo "        Docker Desktop を起動してから、もう一度実行してください。"
    read -p "Enter キーで閉じます..."
    exit 1
fi
echo "[OK] Docker Desktop は起動済み"

if ! command -v uv >/dev/null 2>&1; then
    echo "[SETUP] uv パッケージマネージャをインストールしています..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        echo "[重要] uv がインストールされました。このウィンドウを閉じて、start.command をもう一度実行してください。"
        read -p "Enter キーで閉じます..."
        exit 0
    fi
fi
echo "[OK] uv を確認"

if ! command -v pnpm >/dev/null 2>&1; then
    echo "[SETUP] pnpm をインストールしています..."
    npm install -g pnpm || {
        echo "[ERROR] pnpm のインストールに失敗しました。Node.js がインストールされているか確認してください。 https://nodejs.org/"
        read -p "Enter キーで閉じます..."
        exit 1
    }
fi
echo "[OK] pnpm を確認"
echo ""

# ── 2. 初回設定 (.env) ──────────────────────────────
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "[SETUP] .env ファイルを作成しています..."
        cp .env.example .env
        echo "[INFO] AI機能を使う場合のみ、.env にAPIキーを設定してください（使わない場合はこのままでOK）。"
    fi
fi

# ── 3. Python 依存関係 ──────────────────────────────
echo "[SETUP] Python 依存関係を確認中..."
uv sync
echo "[OK] Python 環境を確認しました"

# ── 4. Node.js 依存関係 ─────────────────────────────
echo "[SETUP] Node.js 依存関係を確認中..."
if [ ! -d "frontend/node_modules" ]; then
    (cd frontend && pnpm install)
    echo "[OK] node_modules をインストールしました"
else
    echo "[OK] node_modules は存在済み"
fi
echo ""

# ── 5. Neo4j 起動 ───────────────────────────────────
echo "[START] Neo4j データベースを起動中..."
docker compose up -d neo4j 2>/dev/null || docker-compose up -d neo4j
echo "[INFO] Neo4j の準備を待機中..."
for i in 1 2 3 4 5 6; do
    sleep 5
    if curl -s http://localhost:7474 >/dev/null 2>&1; then
        echo "[OK] Neo4j 準備完了 (bolt://localhost:7687)"
        break
    fi
done

# ── 6. API サーバー起動（バックグラウンド）───────────
echo "[START] API サーバーを起動中 (port 8001)..."
(cd api && nohup uv run uvicorn app.main:app --port 8001 > /tmp/oya-inai-api.log 2>&1 &)
echo $! > /tmp/oya-inai-api.pid 2>/dev/null

# ── 7. フロントエンド起動（バックグラウンド）─────────
echo "[START] フロントエンドを起動中 (port 3001)..."
(cd frontend && nohup pnpm dev --port 3001 > /tmp/oya-inai-frontend.log 2>&1 &)

# ── 8. ブラウザで開く ───────────────────────────────
echo "[INFO] 5秒後にブラウザを開きます..."
sleep 5
open "http://localhost:3001"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  親なき後支援DB が起動しました"
echo ""
echo "  フロントエンド : http://localhost:3001"
echo "  API サーバー   : http://localhost:8001/docs"
echo "  Neo4j Browser  : http://localhost:7474"
echo ""
echo "  停止するには stop.command をダブルクリックしてください"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "Enter キーでこのウィンドウを閉じます（アプリは動き続けます）..."

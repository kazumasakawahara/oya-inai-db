#!/bin/bash
# 親亡き後支援データベース - 停止スクリプト（macOS）
cd "$(dirname "$0")"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  親亡き後支援データベース - 停止スクリプト"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "[STOP] API サーバーを停止中..."
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "[OK] API サーバーを停止しました" || echo "[OK] API サーバーは動いていませんでした"

echo "[STOP] フロントエンドを停止中..."
pkill -f "frontend.*(vite|next|pnpm)" 2>/dev/null
pkill -f "pnpm dev --port 3001" 2>/dev/null
echo "[OK] フロントエンドを停止しました"

echo "[STOP] Neo4j データベースを停止中..."
docker compose down 2>/dev/null || docker-compose down 2>/dev/null
echo "[OK] Neo4j を停止しました"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  全サービスを停止しました"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "Enter キーで閉じます..."

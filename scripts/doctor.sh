#!/usr/bin/env bash
# oya-inai-db 環境整合性チェック
# 使い方: ./scripts/doctor.sh
#
# 確認項目:
#   1. Docker コンテナ (support-db-neo4j / port 7687) が起動中か
#      （別名コンテナが 7687 を提供する構成も許容）
#   2. Neo4j Bolt (7687) に接続できるか
#   3. .env が存在するか（無くても中核機能は動作。LLM 利用時のみ必要）
#   4. API サーバー (port 8001) が応答するか（informational）
#   5. フロントエンド (port 3001) が応答するか（informational）
#
# 結果は OK / FAIL / INFO で表示。最後に総合判定。

set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PASS=0
FAIL=0
ok()   { printf "  \033[32mOK\033[0m   %s\n" "$1"; PASS=$((PASS+1)); }
fail() { printf "  \033[31mFAIL\033[0m %s\n" "$1"; FAIL=$((FAIL+1)); }
info() { printf "  \033[33mINFO\033[0m %s\n" "$1"; PASS=$((PASS+1)); }

echo "=== oya-inai-db doctor ==="
echo "project: $PROJECT_DIR"
echo ""

# 1. Docker containers (障害福祉DB / port 7687)
echo "[1] Docker containers (障害福祉DB / port 7687)"
status=$(docker inspect -f '{{.State.Status}}' support-db-neo4j 2>/dev/null || echo "missing")
if [ "$status" = "running" ]; then
  ok "support-db-neo4j: running"
else
  alt=$(docker ps --filter publish=7687 --format '{{.Names}}' 2>/dev/null | head -1)
  if [ -n "$alt" ]; then
    info "support-db-neo4j は $status だが、port 7687 は '$alt' が提供中（機能上OK）"
  else
    fail "support-db-neo4j: $status（port 7687 を提供するコンテナがありません）"
  fi
fi

# 2. Bolt connectivity
echo ""
echo "[2] Neo4j Bolt connectivity"
if nc -z localhost 7687 2>/dev/null; then ok "localhost:7687 reachable"; else fail "localhost:7687 unreachable"; fi

# 3. .env
echo ""
echo "[3] .env"
if [ -f "$PROJECT_DIR/.env" ]; then
  ok ".env が存在します"
else
  info ".env がありません（LLM 機能を使う場合は cp .env.example .env で作成してください）"
fi

# 4. API server (informational)
echo ""
echo "[4] API server (port 8001, informational)"
if curl -s --max-time 3 http://localhost:8001/docs >/dev/null 2>&1; then
  ok "API サーバー応答あり (http://localhost:8001)"
else
  info "API サーバー未起動（start.command / start.bat で起動できます）"
fi

# 5. Frontend (informational)
echo ""
echo "[5] Frontend (port 3001, informational)"
if curl -s --max-time 3 http://localhost:3001 >/dev/null 2>&1; then
  ok "フロントエンド応答あり (http://localhost:3001)"
else
  info "フロントエンド未起動（start.command / start.bat で起動できます）"
fi

echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1

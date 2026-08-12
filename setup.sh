#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 親亡き後支援データベース - セットアップスクリプト
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# このスクリプトは以下を実行します:
#   1. 前提条件（Docker / Docker Compose）の確認
#   2. Neo4j コンテナの起動
#   3. .env ファイルの作成ガイダンス
#
# 使い方:
#   chmod +x setup.sh
#   ./setup.sh           # 全セットアップ（推奨）
#   ./setup.sh --neo4j   # Neo4j のみ起動
#
# API・フロントエンドを含めた一発起動は start.command (Mac) /
# start.bat (Windows) を使用してください。
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# プロジェクトルート（このスクリプトのあるディレクトリ）
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ヘルパー関数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_header() {
    echo ""
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${PURPLE}  親亡き後支援データベース - セットアップ${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 前提条件チェック
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

check_prerequisites() {
    info "前提条件を確認中..."
    local missing=0

    # Docker チェック
    if command -v docker &>/dev/null; then
        success "Docker: $(docker --version | head -1)"
    else
        error "Docker がインストールされていません"
        echo "  インストール: https://docs.docker.com/get-docker/"
        missing=1
    fi

    # Docker Compose チェック
    if docker compose version &>/dev/null 2>&1; then
        success "Docker Compose: $(docker compose version --short 2>/dev/null || echo 'available')"
    elif command -v docker-compose &>/dev/null; then
        success "Docker Compose (legacy): $(docker-compose --version | head -1)"
    else
        error "Docker Compose がインストールされていません"
        missing=1
    fi

    if [ $missing -eq 1 ]; then
        echo ""
        error "前提条件が満たされていません。上記を解決してから再実行してください。"
        exit 1
    fi

    echo ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Neo4j セットアップ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

setup_neo4j() {
    info "Neo4j コンテナを起動中..."

    cd "${PROJECT_DIR}"

    # docker compose を使用（v2優先）
    if docker compose version &>/dev/null 2>&1; then
        docker compose up -d
    else
        docker-compose up -d
    fi

    # 起動待ち
    info "Neo4j の起動を待機中（最大60秒）..."
    local retries=0
    local max_retries=12
    while [ $retries -lt $max_retries ]; do
        if curl -s http://localhost:7474 &>/dev/null; then
            success "Neo4j が起動しました"
            echo "  ブラウザUI: http://localhost:7474"
            echo "  Bolt接続: bolt://localhost:7687"
            echo "  認証: neo4j / password"
            return 0
        fi
        retries=$((retries + 1))
        sleep 5
    done

    warn "Neo4j の起動確認がタイムアウトしました"
    echo "  docker logs oya-inai-db-neo4j で状態を確認してください"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 設定ガイダンス
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

show_config_guidance() {
    echo ""
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${PURPLE}  次のステップ${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    if [ ! -f "${PROJECT_DIR}/.env" ]; then
        echo "1. 設定ファイルを作成してください:"
        echo -e "   ${BLUE}cp .env.example .env${NC}"
        echo "   （Neo4j の接続情報のみ。API キーは不要です）"
        echo ""
    fi
    echo "アプリ全体（API + フロントエンド）の起動:"
    echo -e "  Mac:     ${GREEN}./start.command${NC}"
    echo -e "  Windows: ${GREEN}start.bat${NC}"
    echo ""
    echo "詳細は docs/QUICK_START.md を参照してください。"
    echo ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メイン処理
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

main() {
    print_header

    case "${1:-all}" in
        --neo4j|-n)
            check_prerequisites
            setup_neo4j
            ;;
        --help|-h)
            echo "使い方: ./setup.sh [オプション]"
            echo ""
            echo "オプション:"
            echo "  (なし)        全セットアップ（Neo4j起動 + ガイダンス表示）"
            echo "  --neo4j, -n   Neo4j のみ起動"
            echo "  --help, -h    このヘルプを表示"
            ;;
        all|"")
            check_prerequisites
            setup_neo4j
            show_config_guidance
            success "セットアップが完了しました！"
            ;;
        *)
            error "不明なオプション: $1"
            echo "  ./setup.sh --help でヘルプを表示"
            exit 1
            ;;
    esac
}

main "$@"

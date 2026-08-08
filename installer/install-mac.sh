#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# oya-inai-db ワンクリックインストーラー（macOS版）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# 使い方:
#   curl -sL https://raw.githubusercontent.com/kazumasakawahara/oya-inai-db/main/installer/install-mac.sh | bash
#   または:
#   chmod +x install-mac.sh && ./install-mac.sh
#
# このスクリプトが行うこと:
#   1. 前提条件（Docker Desktop, Node.js）の確認・インストール案内
#   2. oya-inai-db リポジトリのダウンロード
#   3. Neo4j データベースの起動
#   4. 接続テストの実行
#
# アプリ全体（API + Web画面）の起動は、セットアップ完了後に
# start.command を実行してください。
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 定数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VERSION="1.0.0"
REPO_URL="https://github.com/kazumasakawahara/oya-inai-db.git"
DEFAULT_INSTALL_DIR="${HOME}/Documents/oya-inai-db"

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ヘルパー関数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

info()    { echo -e "${BLUE}[情報]${NC} $1"; }
success() { echo -e "${GREEN}[完了]${NC} $1"; }
warn()    { echo -e "${YELLOW}[注意]${NC} $1"; }
error()   { echo -e "${RED}[エラー]${NC} $1"; }
step()    { echo -e "\n${PURPLE}${BOLD}━━━ $1 ━━━${NC}\n"; }

# ユーザーに Y/N で質問する
# 使い方: ask "質問?" && echo "Yes" || echo "No"
ask() {
    local prompt="$1"
    local response
    echo -ne "${CYAN}[確認]${NC} ${prompt} [Y/n] "
    read -r response
    [[ "$response" =~ ^[Yy]?$ ]]
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ウェルカムメッセージ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

show_welcome() {
    echo ""
    echo -e "${PURPLE}${BOLD}"
    echo "  ╔══════════════════════════════════════════════╗"
    echo "  ║                                              ║"
    echo "  ║   oya-inai-db インストーラー v${VERSION}         ║"
    echo "  ║   〜 親なき後支援データベース 〜              ║"
    echo "  ║                                              ║"
    echo "  ╚══════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "  このスクリプトは、oya-inai-db のセットアップを"
    echo "  対話形式で案内します。"
    echo ""
    echo "  所要時間の目安: 10〜20分"
    echo "  （Docker Desktop が未インストールの場合はもう少しかかります）"
    echo ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 1: 前提条件チェック
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

check_macos() {
    if [[ "$(uname)" != "Darwin" ]]; then
        error "このインストーラーは macOS 専用です。"
        error "Windows をお使いの場合は installer/install-windows.ps1 を使用してください。"
        exit 1
    fi
    success "macOS を確認しました: $(sw_vers -productVersion)"
}

check_docker() {
    step "Step 1/4: Docker Desktop の確認"

    if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
        success "Docker Desktop が動作中です: $(docker --version | head -1)"
        return 0
    fi

    if command -v docker &>/dev/null; then
        warn "Docker はインストールされていますが、起動していません。"
        echo ""
        echo "  Docker Desktop を起動してください:"
        echo "  1. Launchpad または アプリケーションフォルダから「Docker」を開く"
        echo "  2. メニューバーにクジラのアイコンが表示されるまで待つ"
        echo ""
        echo -ne "${CYAN}[確認]${NC} Docker Desktop を起動しましたか？ [Enter で続行] "
        read -r
        if docker info &>/dev/null 2>&1; then
            success "Docker Desktop が起動しました"
            return 0
        else
            error "Docker Desktop がまだ起動していないようです。起動後に再実行してください。"
            exit 1
        fi
    fi

    # Docker未インストール
    warn "Docker Desktop がインストールされていません。"
    echo ""
    echo "  Docker Desktop は、データベースを動かすために必要です。"
    echo ""

    if ask "Homebrew で Docker Desktop をインストールしますか？"; then
        if command -v brew &>/dev/null; then
            info "Docker Desktop をインストール中..."
            brew install --cask docker
            echo ""
            echo "  Docker Desktop がインストールされました。"
            echo "  アプリケーションフォルダから「Docker」を起動してください。"
            echo ""
            echo -ne "${CYAN}[確認]${NC} Docker Desktop を起動しましたか？ [Enter で続行] "
            read -r
        else
            warn "Homebrew がインストールされていません。"
            echo ""
            echo "  以下のURLから Docker Desktop をダウンロードしてください:"
            echo "  ${BOLD}https://www.docker.com/products/docker-desktop/${NC}"
            echo ""
            echo "  インストール・起動後にこのスクリプトを再実行してください。"
            exit 1
        fi
    else
        echo ""
        echo "  以下のURLから Docker Desktop をダウンロードしてください:"
        echo "  ${BOLD}https://www.docker.com/products/docker-desktop/${NC}"
        echo ""
        echo "  インストール・起動後にこのスクリプトを再実行してください。"
        exit 1
    fi

    if docker info &>/dev/null 2>&1; then
        success "Docker Desktop が動作中です"
    else
        error "Docker Desktop がまだ起動していないようです。起動後に再実行してください。"
        exit 1
    fi
}

check_node() {
    step "Step 2/4: Node.js の確認"

    if command -v npx &>/dev/null; then
        success "Node.js がインストール済みです: $(node --version 2>/dev/null || echo 'available')"
        return 0
    fi

    warn "Node.js がインストールされていません。"
    echo ""
    echo "  Node.js は、Web画面（フロントエンド）を動かすために必要です。"
    echo ""

    if ask "Homebrew で Node.js をインストールしますか？"; then
        if command -v brew &>/dev/null; then
            info "Node.js をインストール中..."
            brew install node
            success "Node.js がインストールされました: $(node --version)"
        else
            echo ""
            echo "  以下のURLから Node.js をダウンロードしてください:"
            echo "  ${BOLD}https://nodejs.org/${NC}"
            echo "  （LTS版を推奨）"
            echo ""
            echo "  インストール後にこのスクリプトを再実行してください。"
            exit 1
        fi
    else
        echo ""
        echo "  以下のURLから Node.js をダウンロードしてください:"
        echo "  ${BOLD}https://nodejs.org/${NC}"
        echo ""
        exit 1
    fi
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 3: プロジェクトのダウンロード
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

download_project() {
    step "Step 3/4: プロジェクトファイルのダウンロード"

    # 既にプロジェクトディレクトリ内から実行されている場合
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local parent_dir
    parent_dir="$(dirname "$script_dir")"

    if [ -f "${parent_dir}/setup.sh" ] && [ -f "${parent_dir}/docker-compose.yml" ]; then
        INSTALL_DIR="${parent_dir}"
        success "プロジェクトディレクトリを検出: ${INSTALL_DIR}"
        return 0
    fi

    # ダウンロードが必要
    echo "  プロジェクトファイルをダウンロードします。"
    echo ""
    echo "  インストール先: ${DEFAULT_INSTALL_DIR}"
    echo ""

    if [ -d "${DEFAULT_INSTALL_DIR}" ]; then
        warn "既にディレクトリが存在します: ${DEFAULT_INSTALL_DIR}"
        if ask "上書き（更新）しますか？"; then
            INSTALL_DIR="${DEFAULT_INSTALL_DIR}"
        else
            echo -ne "  別のインストール先を入力してください: "
            read -r INSTALL_DIR
            INSTALL_DIR="${INSTALL_DIR:-${DEFAULT_INSTALL_DIR}}"
        fi
    else
        INSTALL_DIR="${DEFAULT_INSTALL_DIR}"
    fi

    if command -v git &>/dev/null; then
        info "Git でダウンロード中..."
        if [ -d "${INSTALL_DIR}/.git" ]; then
            cd "${INSTALL_DIR}" && git pull
        else
            git clone "${REPO_URL}" "${INSTALL_DIR}"
        fi
    else
        info "ZIP でダウンロード中..."
        local zip_url="https://github.com/kazumasakawahara/oya-inai-db/archive/refs/heads/main.zip"
        local tmp_zip="/tmp/oya-inai-db.zip"
        curl -sL "${zip_url}" -o "${tmp_zip}"
        mkdir -p "$(dirname "${INSTALL_DIR}")"
        unzip -qo "${tmp_zip}" -d /tmp/
        if [ -d "${INSTALL_DIR}" ]; then
            cp -R /tmp/oya-inai-db-main/* "${INSTALL_DIR}/"
        else
            mv /tmp/oya-inai-db-main "${INSTALL_DIR}"
        fi
        rm -f "${tmp_zip}"
        rm -rf /tmp/oya-inai-db-main
    fi

    success "ダウンロード完了: ${INSTALL_DIR}"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 4: Neo4j の起動
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

setup_database() {
    step "Step 4/4: データベースの起動"

    cd "${INSTALL_DIR}"

    info "Neo4j データベースを起動しています..."
    info "（初回は Docker イメージのダウンロードに数分かかります）"
    echo ""

    if docker compose version &>/dev/null 2>&1; then
        docker compose up -d 2>&1 | while read -r line; do
            echo "  ${line}"
        done
    else
        docker-compose up -d 2>&1 | while read -r line; do
            echo "  ${line}"
        done
    fi

    # 起動待機
    local retries=0
    local max_retries=24  # 最大2分

    info "データベースの起動を待っています..."
    while [ $retries -lt $max_retries ]; do
        if curl -s http://localhost:7474 &>/dev/null; then
            success "障害福祉データベース（port 7687）が起動しました"
            break
        fi
        retries=$((retries + 1))
        echo -ne "  待機中... (${retries}/${max_retries})\r"
        sleep 5
    done
    if [ $retries -eq $max_retries ]; then
        warn "障害福祉データベースの起動確認がタイムアウトしました。docker logs で確認してください。"
    fi

    echo ""
    echo "  データベースの管理画面:"
    echo "    障害福祉:     ${BOLD}http://localhost:7474${NC}"
    echo "    認証情報:     neo4j / password"
    echo ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接続テスト
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

run_connection_test() {
    echo ""
    info "接続テストを実行中..."

    local all_ok=true

    # Neo4j support-db テスト
    if curl -s http://localhost:7474 &>/dev/null; then
        success "障害福祉データベース (port 7687): 接続OK"
    else
        error "障害福祉データベース (port 7687): 接続失敗"
        all_ok=false
    fi

    echo ""
    if $all_ok; then
        success "すべてのテストに合格しました！"
    else
        warn "一部のテストが不合格です。上記のメッセージを確認してください。"
    fi
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 完了メッセージ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

show_completion() {
    echo ""
    echo -e "${GREEN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════╗"
    echo "  ║                                              ║"
    echo "  ║   セットアップが完了しました！                ║"
    echo "  ║                                              ║"
    echo "  ╚══════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo "  ${BOLD}次のステップ:${NC}"
    echo ""
    echo "  1. アプリを起動:"
    echo "     ${CYAN}cd ${INSTALL_DIR} && ./start.command${NC}"
    echo "  2. ブラウザで Web画面 (http://localhost:3001) が開きます"
    echo "  3. デモデータを試す場合:"
    echo "     ${CYAN}bash installer/load-demo-data.sh${NC}"
    echo ""
    echo "  ${BOLD}ドキュメント:${NC}"
    echo "    クイックスタート:  ${INSTALL_DIR}/docs/QUICK_START.md"
    echo "    使い方ガイド:     ${INSTALL_DIR}/docs/ADVANCED_USAGE.md"
    echo ""
    echo "  ${BOLD}データベース管理画面:${NC}"
    echo "    http://localhost:7474 （認証: neo4j / password）"
    echo ""
    echo "  ${BOLD}困ったときは:${NC}"
    echo "    ${INSTALL_DIR}/docs/manuals/FAQ.md を参照してください。"
    echo ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メイン処理
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

main() {
    show_welcome
    check_macos
    check_docker
    check_node
    download_project
    setup_database
    run_connection_test
    show_completion
}

main "$@"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# oya-inai-db ワンクリックインストーラー（Windows版）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# 使い方:
#   PowerShell を「管理者として実行」で開き:
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   .\installer\install-windows.ps1
#
#   または（リモート実行）:
#   irm https://raw.githubusercontent.com/kazumasakawahara/oya-inai-db/main/installer/install-windows.ps1 | iex
#
# このスクリプトが行うこと:
#   1. 前提条件（Docker Desktop, Node.js）の確認・インストール案内
#   2. oya-inai-db リポジトリのダウンロード
#   3. Neo4j データベースの起動
#   4. 接続テストの実行
#
# アプリ全体（API + Web画面）の起動は、セットアップ完了後に
# start.bat を実行してください。
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 文字コード設定（日本語対応）
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 定数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

$VERSION = "1.0.0"
$REPO_URL = "https://github.com/kazumasakawahara/oya-inai-db.git"
$DEFAULT_INSTALL_DIR = Join-Path $env:USERPROFILE "Documents\oya-inai-db"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ヘルパー関数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function Write-Info    { param($msg) Write-Host "[情報] " -ForegroundColor Blue -NoNewline; Write-Host $msg }
function Write-Success { param($msg) Write-Host "[完了] " -ForegroundColor Green -NoNewline; Write-Host $msg }
function Write-Warn    { param($msg) Write-Host "[注意] " -ForegroundColor Yellow -NoNewline; Write-Host $msg }
function Write-Err     { param($msg) Write-Host "[エラー] " -ForegroundColor Red -NoNewline; Write-Host $msg }
function Write-Step    { param($msg) Write-Host "`n━━━ $msg ━━━`n" -ForegroundColor Magenta }

function Ask-YesNo {
    param($prompt)
    $response = Read-Host "$prompt [Y/n]"
    return ($response -eq "" -or $response -match "^[Yy]")
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ウェルカムメッセージ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function Show-Welcome {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor Magenta
    Write-Host "  ║                                              ║" -ForegroundColor Magenta
    Write-Host "  ║   oya-inai-db インストーラー v$VERSION         ║" -ForegroundColor Magenta
    Write-Host "  ║   〜 親なき後支援データベース 〜              ║" -ForegroundColor Magenta
    Write-Host "  ║            （Windows版）                     ║" -ForegroundColor Magenta
    Write-Host "  ║                                              ║" -ForegroundColor Magenta
    Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "  このスクリプトは、oya-inai-db のセットアップを"
    Write-Host "  対話形式で案内します。"
    Write-Host ""
    Write-Host "  所要時間の目安: 10〜20分"
    Write-Host "  （Docker Desktop が未インストールの場合はもう少しかかります）"
    Write-Host ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 1: 前提条件チェック
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function Check-Windows {
    if ($env:OS -ne "Windows_NT") {
        Write-Err "このインストーラーは Windows 専用です。"
        Write-Err "macOS をお使いの場合は installer/install-mac.sh を使用してください。"
        exit 1
    }

    # Windows バージョン確認
    $osVersion = [System.Environment]::OSVersion.Version
    Write-Success "Windows を確認しました: Windows $($osVersion.Major).$($osVersion.Minor) (Build $($osVersion.Build))"

    # WSL2 の確認（推奨）
    if (Get-Command wsl -ErrorAction SilentlyContinue) {
        Write-Success "WSL が利用可能です"
    } else {
        Write-Warn "WSL がインストールされていません。Docker Desktop は WSL2 バックエンドを推奨しています。"
    }
}

function Check-Docker {
    Write-Step "Step 1/4: Docker Desktop の確認"

    # Docker コマンドの存在確認
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        try {
            $null = docker info 2>$null
            if ($LASTEXITCODE -eq 0) {
                $dockerVersion = docker --version
                Write-Success "Docker Desktop が動作中です: $dockerVersion"
                return
            }
        } catch {}

        # Docker はあるが起動していない
        Write-Warn "Docker はインストールされていますが、起動していません。"
        Write-Host ""
        Write-Host "  Docker Desktop を起動してください:"
        Write-Host "  1. スタートメニューから「Docker Desktop」を検索して開く"
        Write-Host "  2. タスクバーにクジラのアイコンが表示されるまで待つ"
        Write-Host "     （初回起動は1〜2分かかります）"
        Write-Host ""
        Read-Host "  Docker Desktop を起動しましたか？ [Enter で続行]"

        try {
            $null = docker info 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Docker Desktop が起動しました"
                return
            }
        } catch {}

        Write-Err "Docker Desktop がまだ起動していないようです。起動後に再実行してください。"
        exit 1
    }

    # Docker 未インストール
    Write-Warn "Docker Desktop がインストールされていません。"
    Write-Host ""
    Write-Host "  Docker Desktop は、データベースを動かすために必要です。"
    Write-Host ""

    if (Ask-YesNo "winget で Docker Desktop をインストールしますか？") {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Info "Docker Desktop をインストール中..."
            winget install Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
            Write-Host ""
            Write-Host "  Docker Desktop がインストールされました。"
            Write-Host "  パソコンの再起動が必要な場合があります。"
            Write-Host "  再起動後、Docker Desktop を起動してからこのスクリプトを再実行してください。"
            exit 0
        } else {
            Write-Warn "winget が利用できません。"
        }
    }

    Write-Host ""
    Write-Host "  以下の URL から Docker Desktop をダウンロードしてください:"
    Write-Host "  https://www.docker.com/products/docker-desktop/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  インストール・起動後にこのスクリプトを再実行してください。"
    exit 1
}

function Check-Node {
    Write-Step "Step 2/4: Node.js の確認"

    if (Get-Command npx -ErrorAction SilentlyContinue) {
        $nodeVersion = node --version 2>$null
        Write-Success "Node.js がインストール済みです: $nodeVersion"
        return
    }

    Write-Warn "Node.js がインストールされていません。"
    Write-Host ""
    Write-Host "  Node.js は、Web画面（フロントエンド）を動かすために必要です。"
    Write-Host ""

    if (Ask-YesNo "winget で Node.js をインストールしますか？") {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Info "Node.js をインストール中..."
            winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
            # PATH の更新
            $env:PATH = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
            if (Get-Command npx -ErrorAction SilentlyContinue) {
                Write-Success "Node.js がインストールされました"
                return
            } else {
                Write-Warn "Node.js のインストールは完了しましたが、PATH の反映にはターミナルの再起動が必要です。"
                Write-Host "  PowerShell を閉じて開き直し、再実行してください。"
                exit 0
            }
        }
    }

    Write-Host ""
    Write-Host "  以下の URL から Node.js をダウンロードしてください:"
    Write-Host "  https://nodejs.org/ （LTS版を推奨）" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 3: プロジェクトのダウンロード
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function Download-Project {
    Write-Step "Step 3/4: プロジェクトファイルのダウンロード"

    # 既にプロジェクトディレクトリ内から実行されている場合
    $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
    $parentDir = Split-Path -Parent $scriptDir

    if ((Test-Path (Join-Path $parentDir "setup.sh")) -and (Test-Path (Join-Path $parentDir "docker-compose.yml"))) {
        $script:INSTALL_DIR = $parentDir
        Write-Success "プロジェクトディレクトリを検出: $($script:INSTALL_DIR)"
        return
    }

    # ダウンロードが必要
    Write-Host "  プロジェクトファイルをダウンロードします。"
    Write-Host ""
    Write-Host "  インストール先: $DEFAULT_INSTALL_DIR"
    Write-Host ""

    if (Test-Path $DEFAULT_INSTALL_DIR) {
        Write-Warn "既にディレクトリが存在します: $DEFAULT_INSTALL_DIR"
        if (Ask-YesNo "上書き（更新）しますか？") {
            $script:INSTALL_DIR = $DEFAULT_INSTALL_DIR
        } else {
            $customPath = Read-Host "  別のインストール先を入力してください"
            $script:INSTALL_DIR = if ($customPath) { $customPath } else { $DEFAULT_INSTALL_DIR }
        }
    } else {
        $script:INSTALL_DIR = $DEFAULT_INSTALL_DIR
    }

    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Info "Git でダウンロード中..."
        if (Test-Path (Join-Path $script:INSTALL_DIR ".git")) {
            Push-Location $script:INSTALL_DIR
            git pull
            Pop-Location
        } else {
            git clone $REPO_URL $script:INSTALL_DIR
        }
    } else {
        Write-Info "ZIP でダウンロード中..."
        $zipUrl = "https://github.com/kazumasakawahara/oya-inai-db/archive/refs/heads/main.zip"
        $tmpZip = Join-Path $env:TEMP "oya-inai-db.zip"
        $tmpDir = Join-Path $env:TEMP "oya-inai-db-main"

        Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -UseBasicParsing
        Expand-Archive -Path $tmpZip -DestinationPath $env:TEMP -Force

        if (Test-Path $script:INSTALL_DIR) {
            Copy-Item -Path "$tmpDir\*" -Destination $script:INSTALL_DIR -Recurse -Force
        } else {
            New-Item -ItemType Directory -Path (Split-Path $script:INSTALL_DIR -Parent) -Force | Out-Null
            Move-Item -Path $tmpDir -Destination $script:INSTALL_DIR
        }

        Remove-Item -Path $tmpZip -Force -ErrorAction SilentlyContinue
        Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Success "ダウンロード完了: $($script:INSTALL_DIR)"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 4: Neo4j の起動
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function Setup-Database {
    Write-Step "Step 4/4: データベースの起動"

    Push-Location $script:INSTALL_DIR

    Write-Info "Neo4j データベースを起動しています..."
    Write-Info "（初回は Docker イメージのダウンロードに数分かかります）"
    Write-Host ""

    docker compose up -d

    # 起動待機: support-db
    $maxRetries = 24
    $retries = 0
    Write-Info "データベースの起動を待っています..."

    while ($retries -lt $maxRetries) {
        try {
            $null = Invoke-WebRequest -Uri "http://localhost:7474" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            Write-Success "障害福祉データベース（port 7687）が起動しました"
            break
        } catch {
            $retries++
            Write-Host "  待機中... ($retries/$maxRetries)" -NoNewline
            Write-Host "`r" -NoNewline
            Start-Sleep -Seconds 5
        }
    }
    if ($retries -eq $maxRetries) {
        Write-Warn "障害福祉データベースの起動確認がタイムアウトしました。docker logs で確認してください。"
    }

    Pop-Location

    Write-Host ""
    Write-Host "  データベースの管理画面:"
    Write-Host "    障害福祉:       http://localhost:7474" -ForegroundColor Cyan
    Write-Host "    認証情報:       neo4j / password"
    Write-Host ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 接続テスト
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function Test-Connection {
    Write-Host ""
    Write-Info "接続テストを実行中..."

    $allOk = $true

    # Neo4j support-db テスト
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:7474" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-Success "障害福祉データベース (port 7687): 接続OK"
    } catch {
        Write-Err "障害福祉データベース (port 7687): 接続失敗"
        $allOk = $false
    }

    Write-Host ""
    if ($allOk) {
        Write-Success "すべてのテストに合格しました！"
    } else {
        Write-Warn "一部のテストが不合格です。上記のメッセージを確認してください。"
    }
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 完了メッセージ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function Show-Completion {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "  ║                                              ║" -ForegroundColor Green
    Write-Host "  ║   セットアップが完了しました！                ║" -ForegroundColor Green
    Write-Host "  ║                                              ║" -ForegroundColor Green
    Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "  次のステップ:" -ForegroundColor White
    Write-Host ""
    Write-Host "  1. アプリを起動:"
    Write-Host "     cd $($script:INSTALL_DIR) して start.bat をダブルクリック" -ForegroundColor Cyan
    Write-Host "  2. ブラウザで Web画面 (http://localhost:3001) が開きます"
    Write-Host "  3. デモデータを試す場合:"
    Write-Host "     .\installer\load-demo-data.ps1" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  ドキュメント:"
    Write-Host "    クイックスタート:  $($script:INSTALL_DIR)\docs\QUICK_START.md"
    Write-Host "    使い方ガイド:     $($script:INSTALL_DIR)\docs\ADVANCED_USAGE.md"
    Write-Host ""
    Write-Host "  データベース管理画面:"
    Write-Host "    http://localhost:7474 （認証: neo4j / password）" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  困ったときは:"
    Write-Host "    $($script:INSTALL_DIR)\docs\manuals\FAQ.md を参照してください。"
    Write-Host ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メイン処理
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Show-Welcome
Check-Windows
Check-Docker
Check-Node
Download-Project
Setup-Database
Test-Connection
Show-Completion

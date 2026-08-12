@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   親亡き後支援データベース - 一発起動スクリプト
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

REM ──────────────────────────────────────────────────
REM 1. 前提条件チェック
REM ──────────────────────────────────────────────────
set "MISSING="

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Desktop が起動していません。
    echo         Docker Desktop を起動してから、もう一度実行してください。
    echo         https://docs.docker.com/get-docker/
    echo.
    pause
    exit /b 1
)
echo [OK] Docker Desktop は起動済み

uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [SETUP] uv パッケージマネージャをインストールしています...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
    echo [重要] uv がインストールされました。
    echo        このウィンドウを閉じて、start.bat をもう一度実行してください。
    pause
    exit /b 0
)
echo [OK] uv を確認

where pnpm >nul 2>&1
if %errorlevel% neq 0 (
    echo [SETUP] pnpm をインストールしています...
    npm install -g pnpm
    if %errorlevel% neq 0 (
        echo [ERROR] pnpm のインストールに失敗しました。
        echo         Node.js がインストールされているか確認してください。
        echo         https://nodejs.org/
        pause
        exit /b 1
    )
)
echo [OK] pnpm を確認
echo.

REM ──────────────────────────────────────────────────
REM 2. 初回設定 (.env チェック)
REM ──────────────────────────────────────────────────
if not exist .env (
    if exist .env.example (
        echo [SETUP] .env ファイルを作成しています...
        copy .env.example .env >nul
        echo [WARN] .env ファイルを作成しました。Neo4j の接続情報を確認してください。
        echo.
        notepad .env
        echo.
        echo [INFO] .env を保存したら、何かキーを押して続行してください...
        pause >nul
    ) else (
        echo [WARN] .env.example が見つかりません。SETUP_GUIDE.md を参照して .env を作成してください。
    )
)

REM ──────────────────────────────────────────────────
REM 3. Python 依存関係のインストール
REM ──────────────────────────────────────────────────
echo [SETUP] Python 依存関係を確認中...
if not exist ".venv" (
    uv sync
    echo [OK] Python 仮想環境を作成しました
) else (
    echo [OK] Python 仮想環境は存在済み
)

REM ──────────────────────────────────────────────────
REM 4. Node.js 依存関係のインストール
REM ──────────────────────────────────────────────────
echo [SETUP] Node.js 依存関係を確認中...
if not exist "frontend\node_modules" (
    cd frontend
    pnpm install
    cd ..
    echo [OK] node_modules をインストールしました
) else (
    echo [OK] node_modules は存在済み
)
echo.

REM ──────────────────────────────────────────────────
REM 5. Neo4j データベースの起動
REM ──────────────────────────────────────────────────
echo [START] Neo4j データベースを起動中...
docker compose up -d neo4j 2>nul || docker-compose up -d neo4j 2>nul
echo [OK] Neo4j コンテナを起動しました

REM Neo4j 準備待ち（最大30秒）
echo [INFO] Neo4j の準備を待機中...
set RETRIES=0
:wait_neo4j
if %RETRIES% geq 6 (
    echo [WARN] Neo4j の応答が遅いですが、バックグラウンドで起動を続けます
    goto :neo4j_done
)
timeout /t 5 /nobreak >nul
curl -s http://localhost:7474 >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Neo4j 準備完了 (bolt://localhost:7687)
    goto :neo4j_done
)
set /a RETRIES+=1
goto :wait_neo4j

:neo4j_done
echo.

REM ──────────────────────────────────────────────────
REM 6. API サーバーの起動（バックグラウンド）
REM ──────────────────────────────────────────────────
echo [START] API サーバーを起動中 (port 8001)...
start "OyagamiDB-API" /min cmd /c "cd /d "%~dp0api" && uv run uvicorn app.main:app --reload --port 8001"
echo [OK] API サーバーをバックグラウンドで起動しました

REM ──────────────────────────────────────────────────
REM 7. フロントエンドの起動（バックグラウンド）
REM ──────────────────────────────────────────────────
echo [START] フロントエンドを起動中 (port 3001)...
start "OyagamiDB-Frontend" /min cmd /c "cd /d "%~dp0frontend" && pnpm dev --port 3001"
echo [OK] フロントエンドをバックグラウンドで起動しました
echo.

REM ──────────────────────────────────────────────────
REM 8. ブラウザで開く（5秒後）
REM ──────────────────────────────────────────────────
echo [INFO] 5秒後にブラウザを開きます...
timeout /t 5 /nobreak >nul
start "" "http://localhost:3001"

REM ──────────────────────────────────────────────────
REM 完了メッセージ
REM ──────────────────────────────────────────────────
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   親なき後支援DB が起動しました
echo.
echo   フロントエンド : http://localhost:3001
echo   API サーバー   : http://localhost:8001/docs
echo   Neo4j Browser  : http://localhost:7474
echo.
echo   停止するには stop.bat を実行してください
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
pause

@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   親亡き後支援データベース - 停止スクリプト
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

REM API サーバー停止
echo [STOP] API サーバーを停止中...
taskkill /FI "WINDOWTITLE eq OyagamiDB-API*" /T /F >nul 2>&1
echo [OK] API サーバーを停止しました

REM フロントエンド停止
echo [STOP] フロントエンドを停止中...
taskkill /FI "WINDOWTITLE eq OyagamiDB-Frontend*" /T /F >nul 2>&1
echo [OK] フロントエンドを停止しました

REM Neo4j 停止
echo [STOP] Neo4j データベースを停止中...
docker compose down 2>nul || docker-compose down 2>nul
echo [OK] Neo4j を停止しました

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   全サービスを停止しました
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
pause

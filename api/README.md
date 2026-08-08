# API Server

FastAPI バックエンド（ポート 8001）

## 起動

```bash
cd api
uv run uvicorn app.main:app --reload --port 8001
```

## ルーター一覧

| エンドポイント | メソッド | 機能 |
|----------------|----------|------|
| `/api/health` | GET | ヘルスチェック |
| `/api/dashboard/stats` | GET | 統計情報 |
| `/api/dashboard/alerts` | GET | 更新期限アラート |
| `/api/dashboard/activity` | GET | 最近の活動 |
| `/api/clients` | GET/POST | クライアント一覧・作成 |
| `/api/clients/{name}` | GET/PUT/DELETE | クライアント詳細・更新・削除 |
| `/api/clients/{name}/emergency` | GET | 緊急情報 |
| `/api/clients/{name}/logs` | GET | 支援記録 |
| `/api/narratives/extract` | POST | テキスト→構造化抽出 |
| `/api/narratives/upload` | POST | ファイルアップロード |
| `/api/narratives/register` | POST | Neo4j登録 |
| `/api/narratives/validate` | POST | スキーマ検証 |
| `/api/narratives/safety-check` | POST | 安全性チェック |
| `/api/quicklog` | POST | クイックログ作成 |
| `/api/search/fulltext` | GET | 全文検索 |
| `/api/search/semantic` | POST | セマンティック検索 |
| `/api/ecomap/{name}` | GET | エコマップデータ |
| `/api/meetings/upload` | POST | 音声アップロード・文字起こし |
| `/api/meetings/{name}` | GET | 面談記録一覧 |
| `/api/system/status` | GET | システム状態 |
| `/api/chat/ws` | WebSocket | AIチャット（ストリーミング） |

## エージェント

| ファイル | 役割 |
|----------|------|
| `gemini_agent.py` | マルチLLMチャット（12ツール付き） |
| `safety_first.py` | 緊急キーワード検知→DB直接検索 |
| `intake_agent.py` | 7本柱対話型インテーク |
| `model_switch.py` | チャット中のLLM動的切替 |
| `validator.py` | 抽出グラフのスキーマ検証 |

## テスト

```bash
uv run pytest tests/ -q  # 319テスト、0.9秒、DB不要
```

## 環境変数

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `NEO4J_URI` | `neo4j://localhost:7687` | Neo4j接続先 |
| `GEMINI_API_KEY` | (必須) | Google Gemini APIキー |
| `CHAT_PROVIDER` | `gemini` | gemini/claude/ollama |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollamaホスト |
| `OLLAMA_MODEL` | `gemma4:26b` | Ollamaモデル |
| `BACKEND_PORT` | `8001` | APIサーバーポート |
| `FRONTEND_PORT` | `3001` | フロントエンドポート |

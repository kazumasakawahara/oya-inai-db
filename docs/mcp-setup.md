# MCP の設定 — スキル層を使うための下準備

> **【草稿】この章は河原さんのレビュー待ちです。**書き手が「分かっている人」なので、福祉職の方が実際に詰まる箇所を拾えていない可能性があります（S-8）。レビュー前に QUICK_START からはリンクしません。

## MCP とは何か（1分で）

Claude はそのままでは、あなたのパソコンの中のファイルやデータベースに触れません。**MCP（Model Context Protocol）は、Claude と手元の道具をつなぐ「差込口」**です。スキル層には差込口が2つ要ります。

| 差込口 | つなぐ相手 | 何に使うか |
|---|---|---|
| filesystem MCP | Obsidian Vault のフォルダ | 語りの原本を保存し、ページを書く |
| neo4j MCP | 支援データベース（Neo4j） | 禁忌・ケア・期限を構造化して登録する |

## 手順（Claude Desktop の場合）

1. Claude Desktop の設定ファイルを開きます
   - Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
2. `mcpServers` に2つ追加します（**パスはご自分の環境に置き換えてください**）:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem",
               "/Users/あなたの名前/Obsidian/あなたのVault名"]
    },
    "neo4j": {
      "command": "uvx",
      "args": ["mcp-neo4j-cypher"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "（設定したパスワード）"
      }
    }
  }
}
```

3. Claude Desktop を**完全に終了して**起動し直します（ウィンドウを閉じるだけでは設定が読み込まれません）
4. 動作確認: チャットで「Vault の schema.md を読んでください」と頼み、内容が返れば filesystem は OK。「データベースに RETURN 1 を実行して」で 1 が返れば neo4j も OK です

## よくある詰まりどころ（草稿・要実地確認）

- **パスの綴り**: フォルダ名にスペースや日本語が入る場合も、そのまま正確に書きます
- **再起動忘れ**: 設定を変えたら必ず Claude を完全終了→起動
- **Neo4j が起動していない**: 先にデータベースを起動してから Claude を使います（`docker compose up -d neo4j`）
- **npx / uvx が無い**: Node.js（npx）と uv（uvx）のインストールが先に必要です——ここが最初の壁になりやすい箇所です

> パッケージ名（`@modelcontextprotocol/server-filesystem` / `mcp-neo4j-cypher`）は 2026-08-11 時点のものです。導入時に各公式リポジトリで最新名をご確認ください。

## 9. レビュー状態（実機確認待ち）

- **河原さんのレビューは一巡済み**（2026-08-11）。Windows 主体への全面改稿（完全終了の0章格上げ・設定ファイル二重問題・原因順の詰まりどころ）と視覚版 `mcp-setup.html` の作成が確定した。**ただし改稿版ファイルは本リポジトリに未着で、本ファイルは改稿前の草稿のまま**——改稿版を受領し次第、差し替える
- **Windows の記述は公開報告に基づく二次情報で、実機未確認**（河原さんは Mac へ移行済みのため確認不可）。実機確認は、**Windows を使う実務者に手順を踏んでもらう機会を待つ**
- それまで冒頭の草稿バナーと QUICK_START 未リンクを維持する

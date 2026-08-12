# クイックスタートガイド

親亡き後支援データベース（oya-inai-db）を最短で立ち上げる手順です。
じっくり読みながら進めたい方は [SETUP_GUIDE.md](./SETUP_GUIDE.md) をどうぞ。

---

## 前提条件

| ツール | 必須 | 用途 |
|-------|------|------|
| Docker Desktop | ○ | Neo4j データベースを動かす |
| Node.js (LTS) | ○ | Web画面を動かす |
| Claude 有料プラン + Claude Desktop | — | 新しい方の登録・まとめ入力に使う。**無くても Web 画面はエラーになりません** |

> **Web 画面は Claude ゼロで動きます。** 利用者台帳・緊急照会・更新期限アラート・出来事の記録・面談記録は
> そのまま使えます（「ソフトは無償・AI は Claude」）。新しい方の登録は Claude に頼む設計です（→ 下の「Claude の準備」）。

---

## ステップ 1: インストーラーを実行する

インストーラーが行うのは次の4つです。

1. 前提条件（Docker Desktop / Node.js）の確認
2. リポジトリのダウンロード
3. Neo4j の起動
4. 接続テスト

**macOS:**
```bash
curl -sL https://raw.githubusercontent.com/kazumasakawahara/oya-inai-db/main/installer/install-mac.sh | bash
```

**Windows（PowerShell を管理者として実行）:**
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
irm https://raw.githubusercontent.com/kazumasakawahara/oya-inai-db/main/installer/install-windows.ps1 | iex
```

> すでにリポジトリを取得済みで、**Neo4j だけを起動したい**場合は `./setup.sh` を使います。
> `setup.sh` が行うのは Neo4j の起動だけで、アプリ全体は起動しません。

---

## ステップ 2: .env を用意する

```bash
cp .env.example .env
```

```powershell
copy .env.example .env
```

| 変数 | 初期値 | 備考 |
|------|--------|------|
| `NEO4J_URI` | `bolt://localhost:7687` | そのままで OK |
| `NEO4J_USERNAME` | `neo4j` | そのままで OK |
| `NEO4J_PASSWORD` | `password` | そのままで OK |

> Windows は `start.bat` が `.env` の不在を検知して自動でコピーし、メモ帳で開きます。

---

## ステップ 3: アプリを起動する

| OS | 起動 | 停止 |
|----|------|------|
| macOS | `start.command` をダブルクリック | ターミナルで `Control + C`、またはウィンドウを閉じる |
| Windows | `start.bat` をダブルクリック | `stop.bat` をダブルクリック |

起動すると次の3つが立ち上がります。

| 構成要素 | ポート | URL |
|---------|-------|-----|
| Web画面（Next.js） | 3001 | http://localhost:3001 |
| API（FastAPI） | 8001 | — |
| Neo4j 5.15（Docker: `oya-inai-db-neo4j`） | 7687 (bolt) / 7474 (ブラウザUI) | http://localhost:7474 （認証: `neo4j` / `password`）|

**http://localhost:3001** が開けば起動成功です。

---

## ステップ 4: デモデータの投入（オプション）

動作確認やデモ用に、合成データを投入できます。**実在の人物とは一切関係ありません。**

**macOS:**
```bash
chmod +x installer/load-demo-data.sh
./installer/load-demo-data.sh
```

**Windows:**
```powershell
.\installer\load-demo-data.ps1
```

削除する場合:

```bash
./installer/load-demo-data.sh --remove
```

```powershell
.\installer\load-demo-data.ps1 -Remove
```

---

## 画面の構成

サイドバーから各ページへ移動します。

| ページ | 用途 |
|--------|------|
| ホーム | ダッシュボード（利用者数・今月の記録・更新期限アラート） |
| 出来事の記録 | 日々の出来事を記録 |
| 面談記録 | その場で文字入力 / 文書ファイル添付 |
| クライアント一覧 | 利用者の一覧・詳細・緊急照会 |
| エコマップ | 支援ネットワークの関係図 |
| 知識グラフ | データのつながりの可視化 |

> 入力画面は番号ステップ式（①利用者を選ぶ → ②…）です。
> ボタンが押せないときは「あと『◯◯』を済ませると押せます」とヒントが出ます。

**新しい方の登録**と、語り・文書からの**まとめ入力**は、画面ではなく **Claude が担当**します（次の節）。

---

## Claude の準備（登録・まとめ入力に必要）

AI は **Claude 一本**です（2026-08 方針決定。旧 Ollama / Gemini の 3 択・LLM設定画面は廃止）。

1. **Claude の有料プラン**を契約する（https://claude.com）
2. **Claude Desktop** をインストールし、MCP でデータベースにつなぐ

つなぎ方は [../mcp-setup.md](../mcp-setup.md)、使い方の練習は [ç¦ç¥å°éè·ã®ããã®å®å¨å°å¥ããã¥ã¢ã«.md](./ç¦ç¥å°éè·ã®ããã®å®å¨å°å¥ããã¥ã¢ã«.md) 第 6 章を参照してください。

---

## トラブルシューティング

### まず診断スクリプト

```bash
./scripts/doctor.sh
```

### Neo4j に接続できない

```bash
docker ps | grep oya-inai-db-neo4j
docker compose restart
```

ブラウザで http://localhost:7474 にアクセスして確認してください（`neo4j` / `password`）。

### http://localhost:3001 が開かない

- Docker Desktop が起動しているか（クジラのアイコン）
- `start.command` / `start.bat` を実行したか
- 初回は準備に1〜2分かかります。少し待ってから再読み込み

### Claude がデータベースにつながらない

Docker と Neo4j が動いているか確認し、MCP の設定を変えた直後なら Claude Desktop を**完全終了**してから開き直してください。
詳しくは [../mcp-setup.md](../mcp-setup.md) のトラブルシューティングへ。
**Web 画面の機能（台帳・緊急照会・更新期限アラート・記録）には影響しません。**

---

## 次のステップ

- [SETUP_GUIDE.md](./SETUP_GUIDE.md) — 初めての方向けの詳細セットアップガイド
- [FIRST_5_OPERATIONS.md](./FIRST_5_OPERATIONS.md) — まず試してほしい5つの操作
- [../mcp-setup.md](../mcp-setup.md) — Claude Desktop とデータベースのつなぎ方
- [PRIVACY_GUIDELINES.md](./PRIVACY_GUIDELINES.md) — 個人情報の取り扱い
- [FAQ.md](./FAQ.md) — よくある質問とトラブルシューティング

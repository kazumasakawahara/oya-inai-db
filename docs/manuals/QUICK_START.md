# クイックスタートガイド

親亡き後支援データベース（oya-inai-db）を最短で立ち上げる手順です。
じっくり読みながら進めたい方は [SETUP_GUIDE.md](./SETUP_GUIDE.md) をどうぞ。

---

## 前提条件

| ツール | 必須 | 用途 |
|-------|------|------|
| Docker Desktop | ○ | Neo4j データベースを動かす |
| Node.js (LTS) | ○ | Web画面を動かす |
| Gemini / Claude API キー | — | AI 機能を使う場合のみ。**無くてもエラーになりません** |

> **中核機能は LLM ゼロで動きます。** 利用者台帳・緊急照会・更新期限アラート・訪問前ブリーフィングは
> AI をひとつも設定しなくてもそのまま使えます（「ソフト無償・知能は持ち込み」）。

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
| `GEMINI_API_KEY` | （空） | AI 機能を使うときだけ設定 |

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

| ページ | 用途 | LLM |
|--------|------|-----|
| ホーム | ダッシュボード | 不要 |
| インテーク | 新規受け入れ情報の登録 | 不要 |
| ナラティブ入力 | 語りをそのまま入力 | 不要（AI抽出を使う場合のみ必要）|
| 出来事の記録 | 日々の出来事を記録 | 不要 |
| 面談記録 | その場で文字入力 / 文書ファイル添付 / 音声ファイル添付 | 音声の文字起こしのみ必要 |
| クライアント一覧 | 利用者の一覧・検索 | 不要 |
| 記録を探す | 意味検索 | **要 Gemini 設定** |
| エコマップ | 支援ネットワークの関係図 | 不要 |
| 知識グラフ | データのつながりの可視化 | 不要 |
| AIチャット | AI に相談 | **要 LLM 設定** |
| LLM設定 | 使う AI の選択と設定 | — |

> 入力画面は番号ステップ式（①利用者を選ぶ → ②…）です。
> ボタンが押せないときは「あと『◯◯』を済ませると押せます」とヒントが出ます。

---

## LLM の設定（任意）

設定は `.env` か、画面の「**LLM設定**」ページから行います。

| 選択肢 | 費用 | データの扱い |
|--------|------|------------|
| **Ollama** | ¥0（完全ローカル） | データが外に出ない。個人情報を扱う運用に推奨 |
| **Gemini API** | Flash 系と Embedding は無料枠あり | 下の注意を参照 |
| **Claude API** | 有料 | 外部 API に送信される |

> **Gemini 無料枠の注意（2026-08 確認）**
> 無料枠では入力データが Google のプロダクト改善に利用されます。
> **個人情報を扱う運用では Ollama か有料枠を推奨します。**
> Pro モデルは 2026-04 以降、無料枠の対象外です。

設定を変えたらアプリを起動し直してください。

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

### 「記録を探す」「AIチャット」が使えない

LLM が未設定です。「LLM設定」ページか `.env` で設定してください。
**中核機能（台帳・緊急照会・更新期限アラート・訪問前ブリーフィング）には影響しません。**

---

## 次のステップ

- [SETUP_GUIDE.md](./SETUP_GUIDE.md) — 初めての方向けの詳細セットアップガイド
- [FIRST_5_OPERATIONS.md](./FIRST_5_OPERATIONS.md) — まず試してほしい5つの操作
- [VOICE_RECORDING_GUIDE.md](./VOICE_RECORDING_GUIDE.md) — 音声記録の録り方
- [PRIVACY_GUIDELINES.md](./PRIVACY_GUIDELINES.md) — 個人情報の取り扱い
- [FAQ.md](./FAQ.md) — よくある質問とトラブルシューティング

# 親亡き後支援データベース（oya-inai-db）

知的障害・精神障害のある方の「その人らしく生きるための情報」——してはいけないこと（禁忌）、効果のあったケア、頼れる人、手帳や受給者証の期限——を、親が元気なうちから記録し、**親亡き後の支援者に確実に手渡す**ためのデータベースです。小規模な福祉事業所や家族会でも運用できるよう、無償のソフトウェアとして公開しています。

- **記録は資産**: 日々の出来事・面談・生育歴をグラフデータベース（Neo4j）に構造化して蓄積
- **緊急時に強い**: 禁忌事項・キーパーソン・かかりつけ医を1画面で即座に照会
- **期限を逃さない**: 手帳・受給者証の更新期限を自動アラート
- **PCが苦手でも使える**: 番号ステップ式のやさしい入力画面（①→②→…と進むだけ）

## 「無償」の定義 — ソフトは無償・AI は Claude

このソフトウェア自体は無償です。閲覧と日々の記録（利用者台帳・緊急照会・更新期限アラート・出来事の記録・面談記録）は AI なしで動きます。一方、**新しい方の登録**と、語り・文書からの**まとめ入力**は **Claude**（Anthropic 社の AI アシスタント）に頼む設計のため、**Claude の有料プランの契約が実質的な導入要件**です。

| 使い方 | 費用 | できること | データの扱い |
|---|---|---|---|
| **Web 画面だけで使う** | ¥0 | 閲覧と日々の記録（利用者台帳・緊急照会・更新期限アラート・出来事の記録・面談記録・エコマップ・知識グラフ） | データはお使いの PC から外に出ません |
| **Claude と組み合わせる** | Claude 有料プラン | 上記＋新しい方の登録・語りや文書からのまとめ入力・自由な言葉での照会・書類の下書き | 依頼した内容が Anthropic 社のサーバーに送信されます → [PRIVACY_GUIDELINES.md](docs/manuals/PRIVACY_GUIDELINES.md) |

※ 以前あった AI の 3 択（Ollama / Gemini / Claude API）と、アプリ内の AI 機能（ナラティブ抽出・AI チャット・意味検索・音声文字起こし）は 2026-08 に廃止し、AI は Claude 一本にまとめました。Claude は Claude Desktop から MCP という仕組みでデータベースに直接つながります（→ [docs/mcp-setup.md](docs/mcp-setup.md)）。

## 二層の提供 — 中核の Web 画面／仕分けは Claude Skills（任意）

本リポジトリは2層で提供しています。

1. **中核（この下のクイックスタートで入るもの）** — 利用者台帳・緊急照会・期限アラート・記録の保存。**Web 画面は AI なしですべて動きます**（新しい方の登録・まとめ入力は Claude に頼む設計 → [COMPLETE_MANUAL.md 第6章](docs/manuals/COMPLETE_MANUAL.md)）
2. **スキル層（`claude-skills/`・任意・後付け）** — 語り（面談メモ・支援記録・会議録）を渡すと、AI が Obsidian Vault と本データベースへ**仕分けて投入**する Claude Skills 3本。Claude の**有料枠**と MCP の設定が必要です。導入・撤去とも中核に影響しません → [claude-skills/README.md](claude-skills/README.md)

## クイックスタート

**Mac:**

```bash
curl -sL https://raw.githubusercontent.com/kazumasakawahara/oya-inai-db/main/installer/install-mac.sh | bash
```

**Windows:** PowerShell で `installer/install-windows.ps1` を実行します。

インストーラーが前提条件（Docker Desktop・Node.js）の確認、リポジトリの取得、データベースの起動、接続テストまで行います。完了後、`start.command`（Mac）/ `start.bat`（Windows）でアプリを起動し、ブラウザで **http://localhost:3001** を開いてください。

- 試しに触ってみるには: `installer/load-demo-data.sh`（Windows は `.ps1`）で**合成デモデータ**（実在の人物とは無関係）を投入できます
- 詳しい手順: [docs/QUICK_START.md](docs/QUICK_START.md) / [docs/manuals/SETUP_GUIDE.md](docs/manuals/SETUP_GUIDE.md)
- 調子が悪いとき: `scripts/doctor.sh` が接続状態を診断します

## 主な画面

| 画面 | できること |
|---|---|
| ホーム | 利用者数・今月の記録・更新期限アラートの一覧 |
| 出来事の記録 | 本人が喜んだ・嫌がった・パニックになった等の出来事を、ボタン選択中心で記録 |
| 面談記録 | その場で文字入力・文書ファイル添付の2方式 |
| クライアント一覧 | 利用者台帳・詳細・緊急照会 |
| エコマップ / 知識グラフ | 支援関係の可視化 |

新しい方の登録・語りや文書からのまとめ入力・自由な言葉での照会は、画面ではなく **Claude が担当**します（→ [docs/mcp-setup.md](docs/mcp-setup.md) / [COMPLETE_MANUAL.md 第6章](docs/manuals/COMPLETE_MANUAL.md)）。

## 技術構成

Neo4j 5.15 Community（Docker）+ FastAPI + Next.js。詳細な語彙・スキーマは [docs/SCHEMA_CONVENTION.md](docs/SCHEMA_CONVENTION.md)（正典 shared-schema からの同期コピー）を参照してください。

## 個人情報の取り扱い

実在の方の情報を扱う前に、必ず [docs/manuals/PRIVACY_GUIDELINES.md](docs/manuals/PRIVACY_GUIDELINES.md) をお読みください。同梱のデモデータはすべて合成データです。

## ライセンス

[MIT License](LICENSE)

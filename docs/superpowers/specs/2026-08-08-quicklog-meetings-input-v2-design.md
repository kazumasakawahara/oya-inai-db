# クイックログの反応記録化・面談記録の入力方式選択 — 設計書

日付: 2026-08-08
ブランチ: feat/friendly-input-ui（第1弾「やさしい入力UI」の続き）
状態: 河原さん承認済み（「落ち着いていた」等の平常状態はカット、支援に役立つ特記の記録に主眼）

## 目的

1. **クイックログ**: 利用者本人が喜んだ・嫌がった・パニックになった等の「特記すべき反応」と、
   それが起きた場面・環境を、選択操作中心で確実に記録できるようにする。
   平常状態（落ち着いていた等）は記録対象にしない。
2. **面談記録**: 音声専用に見える UI をやめ、「その場で文字入力 / 文書ファイル / 音声ファイル」の
   3方式から選べるようにする。

## 前提（スキーマ正典との整合）

- SupportLog の正典プロパティに `emotion` / `triggerTag` / `context` / `action` / `effectiveness` は
  **既に定義済み**。スキーマ変更は行わない（伝搬チェックリスト対象外）。
- 語彙は既存シードデータ（installer/*.cypher）・insight 分析と互換にする:
  - emotion: `Joy` / `Anxiety` / `Fear` / `Anger` / `Sadness`（`Calm` は API では受理するが UI に出さない）
  - effectiveness: `Effective` / `Neutral` / `Ineffective`
  - situation / triggerTag / context: 日本語値可（正典 §55）

## クイックログ

### UI（frontend/src/app/quicklog/page.tsx）

ステップ構成（①②③④必須、⑤任意）:

1. **利用者を選ぶ** — ClientPicker（現行どおり）
2. **本人の様子はどうでしたか** — 絵文字つき大ボタン5択（1タップ、単一選択）
   - 😊 喜んでいた・楽しそうだった → Joy
   - 😟 嫌がっていた・不安そうだった → Anxiety
   - 😨 パニックになった・強くおびえていた → Fear
   - 😠 怒っていた・イライラしていた → Anger
   - 😢 悲しそうだった・元気がなかった → Sadness
3. **どんな場面でしたか** — ドロップダウン（食事のとき/入浴のとき/作業・活動中/外出・散歩中/
   ほかの人との交流/移動・送迎中/休憩中・自由時間/予定が変わったとき/その他）
   ＋「そのときの環境・きっかけ」自由入力（任意。例: 大きな音がした、人が多くて騒がしかった）
4. **くわしく書く** — 自由文（note）
5. **職員の対応（任意・折りたたみ相当のoptionalステップ）** — 対応内容（action）＋
   「うまくいった/どちらともいえない/うまくいかなかった」3択（effectiveness）

場面の選択肢は `{label, situation, triggerTag}` の対応表で保存値に変換する
（例: 作業・活動中 → situation=作業, triggerTag=作業中。シード語彙と一致させる）。

### API（api/app/schemas/narrative.py, api/app/routers/quicklog.py）

- `QuickLogRequest` に optional フィールド追加: `emotion`（Literal 検証）/ `trigger_tag` / `context` /
  `action` / `effectiveness`（Literal 検証）
- ルーターは値があるプロパティだけ SupportLog に書く。既存の呼び出し（フィールド省略）は
  そのまま動く（後方互換）。

## 面談記録

### UI（frontend/src/components/domain/MeetingRecordForm.tsx — AudioUploader を改名・拡張）

1. **利用者を選ぶ**
2. **記録のかたちを選ぶ** — 大ボタン3択: ✍️ その場で文字で入力 / 📄 文書ファイルを添付 / 🎵 音声ファイルを添付
3. 方式ごとの入力:
   - 文字: 大きな Textarea
   - 文書: FileDropZone（.docx/.xlsx/.pdf/.txt）→ サーバー側でテキスト抽出
   - 音声: FileDropZone（現行）＋ LLM 未設定時は LlmNotice（保存は可能・文字起こしのみ不可）
4. **タイトルとメモ（任意）**
- 送信ボタンは「記録を保存する」に統一。GuidedSubmitButton のヒントは方式に応じて変化。

### API（api/app/routers/meetings.py）

`POST /api/meetings/upload` を拡張（エンドポイント追加はしない）:

- `file` を optional 化し、`text` Form フィールドを追加
- 分岐: `text` あり → 本文を `{id}_memo.txt` として uploads/meetings に保存し transcript=本文
  / 音声ファイル → 現行どおり保存＋Gemini 文字起こし
  / 文書ファイル（.docx/.xlsx/.pdf/.txt）→ 保存＋ `app.lib.file_readers.read_file` でテキスト抽出し transcript に格納
  / どちらも無し・非対応形式 → 日本語エラーメッセージ
- テキスト・文書モードでも必ず filePath を持たせる（textEmbedding 付与の MATCH キーが filePath のため）。
  MeetingRecord のプロパティは正典の範囲内（date/title/filePath/transcript/note/textEmbedding）で変更なし。

## テスト

- e2e 更新: meetings.spec.ts（方式選択→音声モードの誘導ヒント）、quicklog.spec.ts 新規
  （様子ボタン・場面選択・ヒント文言・送信可否）
- 既存 e2e（dashboard/navigation/narrative）は変更なしで通ること。

## やらないこと（YAGNI）

- スキーマ正典・machine-check・Guardian への変更（既存プロパティのみ使用のため不要）
- 面談記録への emotion 等の付与、録音のブラウザ内収録、mimeType プロパティの新規書き込み
- 平常状態（Calm）の UI 提供

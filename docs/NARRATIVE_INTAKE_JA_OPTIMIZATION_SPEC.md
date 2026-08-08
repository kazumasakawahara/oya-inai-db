# narrative-intake スキル 日本語最適化 実装指示書

**対象**: Claude Code
**作成日**: 2026-04-12
**作成者**: 河原（法務・設計）／Claude（設計補助）
**対象スキル**: `claude-skills/narrative-intake/`
**前提ブランチ**: 現在の作業ブランチ（main 直接ではなく、`feature/narrative-intake-ja-opt` を新規作成すること）
**見積り工数**: 半日〜1日（約4〜6時間）

---

## 0. 本指示書の位置づけ

本書は、既存の `claude-skills/narrative-intake/` スキルに対し、**日本語ナラティブ処理の精度と安全性を向上させるための追加実装** を Claude Code に指示するものである。現状のスキルは「日本語の福祉実務語彙」にはある程度沿っているが、元号正規化・文境界検出・相対時間解決が未実装であるため、これらを3つのタスクとして実装する。

本書の指示を逸脱する変更（既存ファイルの構造変更、他スキルへの影響、プロダクションコードの変更）は行わず、**純粋に narrative-intake スキル内部への追加**に留めること。

---

## 1. 背景と目的

### 1.1 背景

`claude-skills/narrative-intake/` は、ナラティブ（自然文）から Neo4j への構造化登録を4フェーズプロトコル（抽出→検証→プレビュー→書込+監査）で行うスキル。現状は LifeStage 単位のチャンキング戦略を採用しているが、以下の日本語固有の処理が不足している。

1. **元号表記**（昭和/平成/令和）→西暦変換が Claude の文脈理解任せで、誤変換リスクがある
2. **全角/半角・異体字**の表記ゆれが `mergeKey` の完全一致マッチで別ノード化してしまう
3. **日本語文境界**（`。` `！` `？` `」` 等）を考慮した分割ロジックが未整備で、引用途中や連体修飾句内でチャンク境界が切れる可能性がある
4. **相対時間表現**（「翌年」「同月」「中3の夏」）がチャンク境界を跨いだ際に解決できない

### 1.2 目的

上記4点を、3つの追加ファイルと既存1ファイルへの追記で解決し、「日本語最適化済み narrative-intake」と呼べる水準に引き上げる。

### 1.3 非目的（やらないこと）

- Python 側の `lib/ai_extractor.py` / `lib/db_new_operations.py` の変更（スキルだけで完結させる）
- FastAPI 統合（別タスク、`docs/NARRATIVE_INTAKE_API_DESIGN.md` に基づく）
- 既存スキーマ JSON（`allowed_labels.json` 等）の変更
- 他スキル（`neo4j-support-db`, `provider-search` 等）への波及

---

## 2. 作業環境と前提条件

### 2.1 作業フォルダ

```
/Users/kazumasa/Projects/neo4j-agno-agent/
```

（Cowork セッション内では `/sessions/happy-blissful-archimedes/mnt/neo4j-agno-agent/`）

### 2.2 前提ツール

- uv（Python パッケージマネージャー）
- Python 3.12+
- Node.js（JSON Schema 検証用、任意）
- Claude Code の `Read` / `Write` / `Edit` / `Bash` ツール

### 2.3 事前確認コマンド

実装開始前に以下を実行し、環境が正しいことを確認する。

```bash
# 現在のスキル構成を確認
ls -la claude-skills/narrative-intake/
ls -la claude-skills/narrative-intake/prompts/
ls -la claude-skills/narrative-intake/schema/

# ブランチを作成
git checkout -b feature/narrative-intake-ja-opt
git status
```

### 2.4 バックアップ

グローバルルールに従い、既存ファイルを編集する前に必ずバックアップを作成すること。

```bash
cp claude-skills/narrative-intake/prompts/extraction_core.md \
   claude-skills/narrative-intake/prompts/extraction_core.md.bak-20260412
cp claude-skills/narrative-intake/SKILL.md \
   claude-skills/narrative-intake/SKILL.md.bak-20260412
```

---

## 3. タスク一覧

| # | タスク | 種別 | 対象ファイル | 優先度 |
|---|-------|-----|------------|-------|
| T1 | 日本語テキストルール定義 | 新規作成 | `schema/ja_text_rules.json` | 高 |
| T2 | 元号変換表の追加 | 新規作成 | `schema/era_conversion.json` | 高 |
| T3 | 敬称・呼称辞書の追加 | 新規作成 | `schema/honorific_dict.json` | 中 |
| T4 | 日本語前処理プロンプト追記 | 既存編集 | `prompts/extraction_core.md` | 高 |
| T5 | 相対時間解決プロンプト新設 | 新規作成 | `prompts/relative_time_resolver.md` | 中 |
| T6 | SKILL.md への参照追記 | 既存編集 | `SKILL.md` | 高 |
| T7 | テスト用サンプルの追加 | 新規作成 | `examples/ja_optimization_test.md` | 低 |
| T8 | 検証スクリプト作成 | 新規作成 | `scripts/validate_ja_rules.py` | 中 |

各タスクの詳細は第4節以降に記載する。

---

## 4. タスク詳細

### T1. `schema/ja_text_rules.json` の新設

#### 4.1.1 目的

日本語テキストの文境界・引用・分割禁止位置を機械可読な形で定義し、Phase 2 検証時とチャンキング時に参照できるようにする。

#### 4.1.2 ファイルパス

```
claude-skills/narrative-intake/schema/ja_text_rules.json
```

#### 4.1.3 内容仕様

以下の JSON スキーマに従うこと。コメントは JSON 標準では許可されないため、`_comment` フィールドを使う。

```json
{
  "version": "1.0.0",
  "updatedAt": "2026-04-12",
  "_comment": "日本語ナラティブのチャンキング・正規化・検証に使用するルール集",

  "sentenceEndMarkers": {
    "_comment": "文末を示す記号。これらの直後は文境界候補",
    "primary": ["。", "！", "？", "．"],
    "secondary": ["」", "』", "）", "〕", "】"],
    "note": "secondary は primary に連接する場合のみ境界として扱う（例: 『〜と言った。』）"
  },

  "quotationPairs": {
    "_comment": "開き記号と閉じ記号のペア。ペア内ではチャンク分割禁止",
    "pairs": [
      {"open": "「", "close": "」"},
      {"open": "『", "close": "』"},
      {"open": "（", "close": "）"},
      {"open": "〔", "close": "〕"},
      {"open": "【", "close": "】"},
      {"open": "\"", "close": "\""},
      {"open": "'", "close": "'"}
    ]
  },

  "forbiddenSplitContexts": {
    "_comment": "以下の文脈ではチャンク分割禁止",
    "patterns": [
      {
        "name": "insideQuotation",
        "description": "引用括弧の内部",
        "detection": "quotationPairs のいずれかのペア内にカーソルがある"
      },
      {
        "name": "renyokeiModifier",
        "description": "連体修飾句の途中（例: 『〜した母親が〜』の『〜した』と『母親』の間）",
        "detection": "動詞連体形（タ形/ル形）の直後かつ名詞の直前"
      },
      {
        "name": "rentaishushokuInstrument",
        "description": "助詞『の』『が』『を』『に』『で』『と』の直後",
        "detection": "1文字助詞の直後で語境界になっていない位置"
      },
      {
        "name": "compoundNoun",
        "description": "複合名詞の途中（例: 『障害福祉サービス受給者証』）",
        "detection": "漢字が連続している位置"
      },
      {
        "name": "dateExpression",
        "description": "日付・元号表記の途中（例: 『昭和58年3月15日』）",
        "detection": "元号名・年月日数字列の途中"
      }
    ]
  },

  "normalization": {
    "_comment": "Phase 1 抽出前の正規化ルール",
    "unicode": "NFC",
    "fullWidthToHalfWidth": {
      "digits": true,
      "alphabets": true,
      "symbols": false,
      "_comment": "記号は全角を維持（日本語文章の慣習）"
    },
    "halfWidthToFullWidth": {
      "kana": true,
      "_comment": "半角カタカナは全角に統一"
    },
    "whitespace": {
      "normalizeMultipleSpaces": true,
      "preserveLineBreaks": true
    }
  },

  "chunkingHints": {
    "_comment": "チャンク分割時のサイズ・境界の目安",
    "preferredCharCount": 2500,
    "minCharCount": 800,
    "maxCharCount": 4000,
    "boundaryPriority": [
      "LifeStageHeading",
      "ChapterHeading",
      "BlankLine",
      "SentenceEnd",
      "ClauseEnd"
    ],
    "avoidBoundaryWithin": [
      "quotationPair",
      "dateExpression",
      "parentheticalNote"
    ]
  },

  "lifeStageHeadings": {
    "_comment": "LifeStage チャンク境界として検出すべき日本語見出しパターン",
    "regexPatterns": [
      "^(胎児期|乳児期|幼児期|学齢期前半|学齢期後半|学童期|青年期|成人期|壮年期|高齢期)",
      "^第[一二三四五六七八九十0-9０-９]+章",
      "^(幼少期|小学[生校]時代|中学[生校]時代|高校時代|大学時代|社会人[になってから]?)",
      "^[0-9０-９]+[歳才]の?[頃ころ]"
    ]
  }
}
```

#### 4.1.4 受け入れ基準

- `python -c "import json; json.load(open('claude-skills/narrative-intake/schema/ja_text_rules.json'))"` がエラーなく完走する
- `version`・`updatedAt`・`sentenceEndMarkers`・`quotationPairs`・`forbiddenSplitContexts`・`normalization`・`chunkingHints`・`lifeStageHeadings` の8キーすべてが存在する
- すべての正規表現が Python `re` モジュールでコンパイル可能であること（T8 の検証スクリプトでチェック）

---

### T2. `schema/era_conversion.json` の新設

#### 4.2.1 目的

日本の元号を西暦に変換するための辞書を機械可読な形で提供し、Phase 1 抽出時とプレビュー表示時に参照可能にする。

#### 4.2.2 ファイルパス

```
claude-skills/narrative-intake/schema/era_conversion.json
```

#### 4.2.3 内容仕様

```json
{
  "version": "1.0.0",
  "updatedAt": "2026-04-12",
  "_comment": "日本の元号 → 西暦変換表。元号N年 = baseYear + N",

  "eras": [
    {
      "name": "明治",
      "nameAlt": ["明", "M", "Meiji"],
      "startDate": "1868-01-25",
      "endDate": "1912-07-30",
      "baseYear": 1867,
      "_formula": "西暦 = 1867 + 明治N年"
    },
    {
      "name": "大正",
      "nameAlt": ["大", "T", "Taisho", "Taishō"],
      "startDate": "1912-07-30",
      "endDate": "1926-12-25",
      "baseYear": 1911,
      "_formula": "西暦 = 1911 + 大正N年"
    },
    {
      "name": "昭和",
      "nameAlt": ["昭", "S", "Showa", "Shōwa"],
      "startDate": "1926-12-25",
      "endDate": "1989-01-07",
      "baseYear": 1925,
      "_formula": "西暦 = 1925 + 昭和N年"
    },
    {
      "name": "平成",
      "nameAlt": ["平", "H", "Heisei"],
      "startDate": "1989-01-08",
      "endDate": "2019-04-30",
      "baseYear": 1988,
      "_formula": "西暦 = 1988 + 平成N年"
    },
    {
      "name": "令和",
      "nameAlt": ["令", "R", "Reiwa"],
      "startDate": "2019-05-01",
      "endDate": null,
      "baseYear": 2018,
      "_formula": "西暦 = 2018 + 令和N年"
    }
  ],

  "parsingRules": {
    "regex": "(明治|大正|昭和|平成|令和|M|T|S|H|R)\\s*([元0-9０-９]+)\\s*年",
    "ganOrdinal": "元 は 1 として扱う（例: 平成元年 = 平成1年 = 1989年）",
    "ambiguityHandling": "M/T/S/H/R の1文字略記は、文脈に日本語の元号文字がない場合のみ適用する",
    "boundaryDates": "元号切替年（例: 昭和64年/平成元年は同年）は startDate/endDate で判定する"
  },

  "examples": [
    {"input": "昭和58年3月15日", "output": "1983-03-15"},
    {"input": "平成元年", "output": "1989"},
    {"input": "令和2年4月1日", "output": "2020-04-01"},
    {"input": "S58.3.15", "output": "1983-03-15"},
    {"input": "H7年生まれ", "output": "1995年生まれ"}
  ]
}
```

#### 4.2.4 受け入れ基準

- JSON として valid であること
- 5元号（明治・大正・昭和・平成・令和）すべてが含まれること
- `baseYear + 元号年 = 西暦年` の計算が `examples` の全項目で一致すること（T8 で検証）

---

### T3. `schema/honorific_dict.json` の新設

#### 4.3.1 目的

敬称・呼称・親族呼称を辞書化し、Phase 2 の `mergeKey` 正規化で「お母さん」「母親」「実母」を同一の Person として扱えるようにする。

#### 4.3.2 ファイルパス

```
claude-skills/narrative-intake/schema/honorific_dict.json
```

#### 4.3.3 内容仕様

```json
{
  "version": "1.0.0",
  "updatedAt": "2026-04-12",
  "_comment": "敬称・呼称・親族呼称の正規化辞書",

  "suffixHonorifics": {
    "_comment": "人名の後ろに付く敬称。mergeKey 生成時は除去する",
    "list": ["さん", "様", "さま", "先生", "氏", "ちゃん", "くん", "君", "殿", "殿下", "先輩", "後輩"]
  },

  "kinshipTerms": {
    "_comment": "親族呼称の統一名への正規化",
    "mother": {
      "canonical": "母",
      "variants": ["母", "母親", "お母さん", "お母様", "おかあさん", "ママ", "実母", "生母", "母上"]
    },
    "father": {
      "canonical": "父",
      "variants": ["父", "父親", "お父さん", "お父様", "おとうさん", "パパ", "実父", "生父", "父上"]
    },
    "elderBrother": {
      "canonical": "兄",
      "variants": ["兄", "兄さん", "お兄さん", "お兄ちゃん", "にいさん", "アニキ"]
    },
    "youngerBrother": {
      "canonical": "弟",
      "variants": ["弟", "弟さん", "弟くん"]
    },
    "elderSister": {
      "canonical": "姉",
      "variants": ["姉", "姉さん", "お姉さん", "お姉ちゃん", "ねえさん"]
    },
    "youngerSister": {
      "canonical": "妹",
      "variants": ["妹", "妹さん", "妹ちゃん"]
    },
    "grandmother": {
      "canonical": "祖母",
      "variants": ["祖母", "おばあさん", "おばあちゃん", "祖母さん", "大お母さん"]
    },
    "grandfather": {
      "canonical": "祖父",
      "variants": ["祖父", "おじいさん", "おじいちゃん", "祖父さん", "大お父さん"]
    },
    "spouseWife": {
      "canonical": "妻",
      "variants": ["妻", "家内", "奥さん", "奥様", "嫁", "連れ合い"]
    },
    "spouseHusband": {
      "canonical": "夫",
      "variants": ["夫", "主人", "旦那さん", "旦那様", "連れ合い"]
    }
  },

  "professionalTitles": {
    "_comment": "職業的呼称。人名にかかる場合は suffixHonorifics として扱う",
    "list": ["医師", "看護師", "介護福祉士", "社会福祉士", "精神保健福祉士", "保育士", "栄養士", "薬剤師", "保健師", "相談支援専門員", "サービス管理責任者", "児童発達支援管理責任者"]
  },

  "normalizationRule": {
    "kinshipResolution": "親族呼称が Client の家族文脈で現れた場合、canonical 名に統一し、KeyPerson.name として使用する",
    "suffixStripping": "mergeKey 生成前に suffixHonorifics を末尾から除去する（例: '田中先生' → '田中'）",
    "contextWarning": "複数の親族が同じ canonical（例: 複数の兄）を持つ場合は Phase 2 で warning を出し、名前等で区別するよう促す"
  }
}
```

#### 4.3.4 受け入れ基準

- JSON として valid
- 10種以上の親族関係を網羅
- `canonical` はすべて `variants` リストにも含まれていること

---

### T4. `prompts/extraction_core.md` への日本語前処理セクション追記

#### 4.4.1 目的

既存の抽出プロンプトの冒頭に「日本語前処理」セクションを追加し、Gemini/Claude が Phase 1 実行時に必ず正規化・元号変換・敬称処理を行うようにする。

#### 4.4.2 対象ファイル

```
claude-skills/narrative-intake/prompts/extraction_core.md
```

#### 4.4.3 編集方法

**既存の「## 抽出ルール」セクションの直前**に、以下の新セクションを挿入すること。既存セクションの削除・変更は禁止。

```markdown
## 日本語前処理（Phase 1 の最初に必ず実行）

ナラティブから graph JSON を生成する前に、以下の前処理を内部的に完了させること。
これらのルールは `schema/ja_text_rules.json`・`schema/era_conversion.json`・`schema/honorific_dict.json` に定義されており、本プロンプトで明示しなくとも参照すること。

### 1. Unicode 正規化

- 入力テキストを **NFC（Normalization Form C）** に正規化する
- 半角カタカナ（ｶﾀｶﾅ）は全角カタカナ（カタカナ）に変換
- 全角数字（０１２）は半角数字（012）に変換
- 全角英字（ａｂｃ）は半角英字（abc）に変換
- 記号（句読点・括弧類）は全角を維持

### 2. 元号 → 西暦変換

`schema/era_conversion.json` の `eras[].baseYear` を用いて変換する。

- **必ず西暦として ISO 8601 形式**（`YYYY-MM-DD` または `YYYY`）で出力する
- `元年` は `1年` として扱う（例: `平成元年` → `1989`）
- 変換規則:
  - 明治 + N年 = 1867 + N
  - 大正 + N年 = 1911 + N
  - 昭和 + N年 = 1925 + N
  - 平成 + N年 = 1988 + N
  - 令和 + N年 = 2018 + N
- 元号切替年（例: 昭和64年/平成元年は同年 = 1989年）は `startDate`/`endDate` 境界で判定
- 略記（S/H/R 等）は他に元号文字列がない場合のみ解釈

**例**:
- 「昭和58年3月15日生まれ」→ `{"dob": "1983-03-15"}`
- 「平成7年頃に診断」→ `{"diagnosedDate": "1995"}` ＋ `warnings: ["曖昧表現『頃』"]`
- 「令和2年4月から」→ `{"startDate": "2020-04"}`

### 3. 親族呼称・敬称の正規化

`schema/honorific_dict.json` に従い、以下を実施する。

- **親族呼称の統一**: 「お母さん」「母親」「実母」→ すべて `"母"` を `KeyPerson.name` に使用。ただし固有名（「田中花子さん（母）」のような記載）があれば固有名を優先し、`role: "母"` をプロパティとして併記する。
- **敬称の除去**: `mergeKey` 生成時に末尾の「さん」「先生」「ちゃん」等を除去する。例: `田中先生` → mergeKey は `田中`、ただし `displayName: "田中先生"` を保持。
- **曖昧ケースの警告**: 同一の canonical（例: 「兄」）が文脈上2人以上存在する場合、`warnings` に「複数の兄が言及されているため区別が必要」と記録する。

### 4. 文境界の尊重（チャンク処理時）

長文を複数チャンクに分割する場合は、`schema/ja_text_rules.json` の `sentenceEndMarkers` と `quotationPairs` に従い、以下を遵守する。

- 分割位置は文末記号（`。` `！` `？`）の直後のみ
- `「」` `『』` `（）` の**内部では分割禁止**
- 連体修飾句の途中（動詞タ形／ル形と直後の名詞の間）では分割禁止
- 日付表記（`昭和58年3月15日`）の途中では分割禁止
- 複合名詞（連続する漢字列）の途中では分割禁止

### 5. 相対時間表現の扱い

「翌年」「同月」「中3の夏」等の相対表現は、直前のチャンクに絶対日付アンカーがある場合のみ解決を試みる。解決できない場合は：

- 可能な限り近い絶対日付（直近の文脈日付）を `dateHint` に格納
- `warnings` 配列に `"相対時間表現『翌年』を解決できませんでした。元の文脈: 〜"` を記録
- graph JSON の日付プロパティには入れず、`notes` フィールドに文字列のまま残す

詳細は `prompts/relative_time_resolver.md` を参照。

---
```

#### 4.4.4 受け入れ基準

- 既存セクション（抽出ルール、few-shot 例、出力フォーマット）が無傷
- 新セクションが既存の `## 抽出ルール` の直前に挿入されている
- セクション内の5サブセクション（Unicode 正規化 / 元号変換 / 敬称 / 文境界 / 相対時間）がすべて存在する
- `schema/` 配下の3つの JSON ファイルへの参照リンクが含まれている

---

### T5. `prompts/relative_time_resolver.md` の新設

#### 4.5.1 目的

相対時間表現の解決ロジックを独立したプロンプトとして切り出し、T4 のメインプロンプトから参照可能にする。

#### 4.5.2 ファイルパス

```
claude-skills/narrative-intake/prompts/relative_time_resolver.md
```

#### 4.5.3 内容仕様

以下の構造で Markdown を作成すること。

```markdown
# 相対時間表現の解決ルール

本プロンプトは `prompts/extraction_core.md` の Phase 1 日本語前処理ステップから参照される補助プロンプトである。
日本語ナラティブによく現れる相対的な時間表現を、文脈中の絶対日付に基づいて可能な限り絶対化する。

## 適用対象の表現カテゴリ

### A. 直接相対（前後関係が明確）
- 「翌年」「翌月」「翌日」「翌週」
- 「前年」「前月」「前日」「前週」
- 「2年後」「3ヶ月後」「半年前」「10日前」

### B. 同一基準（直前の文と同じ時点）
- 「同年」「同月」「同日」「同時期」「その頃」
- 「その時」「当時」

### C. 年齢ベース（Client の dob が必要）
- 「3歳の時」「5才の頃」「10歳前後」
- 「小学校入学時」（通常6歳、`schema/era_conversion.json` に学齢規則なし → 近似）
- 「中学生の頃」（12〜15歳、範囲として扱う）

### D. ライフイベント参照（他のノードに依存）
- 「結婚した年」「診断を受けた翌年」「入所した後」
- 「母が亡くなった年」

### E. 曖昧表現（解決不可の可能性高）
- 「最近」「最近のこと」「先日」「昨日」（執筆日基準が不明）
- 「若い頃」「年配になってから」

## 解決アルゴリズム

1. **アンカー検索**: 直前のチャンク末尾から逆方向に絶対日付を探す（最大 20 文以内）
2. **カテゴリ判定**: 表現がA〜Eのどれに該当するか判定
3. **計算**:
   - A: `anchorDate ± offset` を算出
   - B: `anchorDate` をそのまま採用
   - C: `dob + ageN` を算出（`dob` が未確定なら中断）
   - D: 参照先ノードを temp_id で辿り、その日付 ± offset
   - E: **解決を試みず、warnings に記録**
4. **精度表示**: 解決結果には `precision` を付記
   - `"exact"` (YYYY-MM-DD)
   - `"month"` (YYYY-MM)
   - `"year"` (YYYY)
   - `"approximate"` (± 1年以上の誤差)
   - `"unresolved"` (解決失敗)

## 出力フォーマット

graph JSON の日付プロパティには解決済み絶対日付のみを入れる。未解決の表現は `notes` に残す。

```json
{
  "label": "LifeHistory",
  "properties": {
    "lifeStage": "青年期",
    "period": "1998",
    "periodPrecision": "year",
    "description": "20歳の時に A型作業所に通所開始",
    "notes": "原文: 『大学中退の翌年、20歳で通所を始めた』"
  }
}
```

## 解決できない場合のフォールバック

以下のいずれかの warnings エントリを必ず追加すること。

- `"相対時間『{表現}』の解決に失敗: アンカー日付が見つかりません"`
- `"相対時間『{表現}』の解決に失敗: Client.dob が未確定です"`
- `"曖昧表現『{表現}』: 絶対日付への変換を保留しました"`

## 検証例

### 例1: 翌年の解決（成功）

**入力**:
> 平成10年（1998年）4月、A型作業所に通所開始。**翌年**、体調不良で一時中断した。

**出力**:
- アンカー: `1998-04`
- 翌年 = `1999`
- `period: "1999"`, `periodPrecision: "year"`

### 例2: 年齢ベース（dob 必要）

**入力**:
> 3歳の時、発達検査で広汎性発達障害と診断された。

**前提**: Client.dob = `1980-05-20`

**出力**:
- `diagnosedDate: "1983"`, `precision: "approximate"`
- `notes: "原文: 『3歳の時』"`

### 例3: 解決不可（warning）

**入力**:
> 最近、作業所の人間関係で悩んでいる様子。

**出力**:
- 日付プロパティは設定しない
- `warnings: ["曖昧表現『最近』: 絶対日付への変換を保留しました"]`
- `notes: "原文の記載時期不明"`
```

#### 4.5.4 受け入れ基準

- 5カテゴリ（A〜E）すべてが記載されている
- 解決アルゴリズムが1〜4のステップで明示されている
- 3つ以上の検証例が含まれている
- 解決失敗時の warnings フォーマットが規定されている

---

### T6. `SKILL.md` への参照追記

#### 4.6.1 目的

SKILL.md の「長文ナラティブのチャンキング戦略」セクションに、日本語最適化ファイル群への参照を追加し、利用者（Claude Desktop のユーザー）が存在を認識できるようにする。

#### 4.6.2 対象ファイル

```
claude-skills/narrative-intake/SKILL.md
```

#### 4.6.3 編集方法

既存の「長文ナラティブのチャンキング戦略」セクション（現状191〜196行目付近）の直後に、以下の新サブセクションを挿入すること。

```markdown
### 日本語最適化ルール（バージョン 1.0）

チャンキング・正規化・相対時間解決のルールは以下のファイルに分離されている。Phase 1 実行時に必ず参照すること。

| ファイル | 役割 |
|---------|-----|
| `schema/ja_text_rules.json` | 文境界・引用括弧・分割禁止位置・NFC正規化ルール |
| `schema/era_conversion.json` | 明治〜令和の元号→西暦変換表 |
| `schema/honorific_dict.json` | 敬称・親族呼称・職業的呼称の正規化辞書 |
| `prompts/relative_time_resolver.md` | 相対時間表現の解決アルゴリズム |

これらのファイルは相互に参照可能で、`prompts/extraction_core.md` の「日本語前処理」セクションからも呼び出される。
ルール更新時は `version` と `updatedAt` を必ずインクリメントすること。

**実装上の注意**:
- 元号変換は **抽出段階で必ず実施**し、graph JSON 出力時には ISO 8601 形式に統一する
- 敬称は `mergeKey` 生成時に除去するが、`displayName` プロパティとして原表記を保持する
- 相対時間表現は解決できない場合、日付プロパティに入れず `warnings` と `notes` に残す
```

#### 4.6.4 受け入れ基準

- 既存のチャンキング戦略セクション（5項目のリスト）が無傷
- 新サブセクションが正しい位置に挿入されている
- 4ファイルすべてへの参照が表形式で記載されている

---

### T7. `examples/ja_optimization_test.md` の新設

#### 4.7.1 目的

日本語最適化ルールが正しく機能するかを確認するためのエンドツーエンドテストケースを提供する。

#### 4.7.2 ファイルパス

```
claude-skills/narrative-intake/examples/ja_optimization_test.md
```

#### 4.7.3 内容仕様

以下の構造で、**入力ナラティブ → 期待される graph JSON** のペアを最低5件記載すること。

- **テストケース1**: 元号変換を含む短い生育歴（昭和・平成・令和すべて含む）
- **テストケース2**: 親族呼称の統合が必要な家族聴き取り
- **テストケース3**: 半角カタカナ・全角数字混在の支援記録
- **テストケース4**: 相対時間表現「翌年」「同月」「3歳の時」を含む長文
- **テストケース5**: 解決不可な曖昧表現（「最近」「若い頃」）を含む記録

各ケースの形式:
```markdown
## テストケース N: タイトル

### 入力
（原文のナラティブ）

### 期待される前処理結果
- 正規化: 〜
- 元号変換: 〜
- 敬称処理: 〜

### 期待される graph JSON（抜粋）
（JSON コードブロック）

### 期待される warnings
- ...

### 検証ポイント
- [ ] 〜
- [ ] 〜
```

#### 4.7.4 受け入れ基準

- 5件以上のテストケースが存在する
- 各ケースに入力・期待結果・検証ポイントが含まれる
- JSON 部分がすべて valid JSON である

---

### T8. `scripts/validate_ja_rules.py` の新設

#### 4.8.1 目的

T1〜T3 で作成した JSON ファイルが仕様通りであることを検証する Python スクリプトを用意し、CI / 手動検証で使えるようにする。

#### 4.8.2 ファイルパス

```
claude-skills/narrative-intake/scripts/validate_ja_rules.py
```

（`scripts/` サブディレクトリが存在しなければ作成する）

#### 4.8.3 内容仕様

uv で管理されている Python 3.12 環境で動作すること。標準ライブラリのみ使用（`json`, `re`, `sys`, `pathlib`, `unicodedata`）。

実装すべき検証項目:

1. **JSON 構文検証**: 3ファイルすべてが `json.load()` で読み込めること
2. **スキーマキー検証**: 必須トップレベルキーがすべて存在すること
3. **正規表現検証**: `ja_text_rules.json` の `lifeStageHeadings.regexPatterns` と `era_conversion.json` の `parsingRules.regex` が `re.compile()` でコンパイル可能であること
4. **元号計算検証**: `era_conversion.json` の `examples` 配列を全走査し、`baseYear + N年 = 西暦` が一致するか確認
5. **辞書整合性検証**: `honorific_dict.json` の `kinshipTerms.*.canonical` が `variants` 配列に含まれていること
6. **Unicode 正規化確認**: 3ファイル内のすべての日本語文字列が NFC 正規化済みであること

出力形式:
- 成功時: `✓ All validations passed (N checks)` を stdout に出力し、exit code 0
- 失敗時: 失敗した項目を `✗ FAIL: <check名> - <詳細>` で列挙し、exit code 1

実行方法:
```bash
cd /Users/kazumasa/Projects/neo4j-agno-agent
uv run python claude-skills/narrative-intake/scripts/validate_ja_rules.py
```

#### 4.8.4 スクリプト骨子

以下は参考実装の骨子。完成版はコメントを日本語で記載すること。

```python
#!/usr/bin/env python3
"""narrative-intake スキルの日本語最適化ルールを検証するスクリプト"""

import json
import re
import sys
import unicodedata
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCHEMA_DIR = SKILL_DIR / "schema"

errors = []
checks_passed = 0

def check(condition: bool, name: str, detail: str = "") -> None:
    global checks_passed
    if condition:
        checks_passed += 1
    else:
        errors.append(f"{name} - {detail}")

def validate_ja_text_rules() -> None:
    path = SCHEMA_DIR / "ja_text_rules.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    required_keys = [
        "version", "updatedAt", "sentenceEndMarkers",
        "quotationPairs", "forbiddenSplitContexts",
        "normalization", "chunkingHints", "lifeStageHeadings",
    ]
    for key in required_keys:
        check(key in data, f"ja_text_rules.{key}", "必須キーが存在しません")
    # 正規表現コンパイル確認
    for pattern in data.get("lifeStageHeadings", {}).get("regexPatterns", []):
        try:
            re.compile(pattern)
            check(True, f"regex compile: {pattern[:30]}")
        except re.error as e:
            check(False, f"regex compile: {pattern[:30]}", str(e))

def validate_era_conversion() -> None:
    path = SCHEMA_DIR / "era_conversion.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    check("eras" in data, "era_conversion.eras", "必須キーが存在しません")
    era_names = {e["name"] for e in data.get("eras", [])}
    for required in ["明治", "大正", "昭和", "平成", "令和"]:
        check(required in era_names, f"era_conversion.{required}", "元号が欠けています")
    # examples の計算検証
    base_years = {e["name"]: e["baseYear"] for e in data["eras"]}
    era_regex = re.compile(r"(明治|大正|昭和|平成|令和)\s*([元0-9]+)")
    for ex in data.get("examples", []):
        inp = ex["input"]
        out = ex["output"]
        m = era_regex.search(inp)
        if m:
            era_name = m.group(1)
            year_str = m.group(2).replace("元", "1")
            n = int(year_str)
            expected_year = base_years[era_name] + n
            check(
                str(expected_year) in out,
                f"era_example: {inp}",
                f"期待: {expected_year}, 実際: {out}",
            )

def validate_honorific_dict() -> None:
    path = SCHEMA_DIR / "honorific_dict.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    kinship = data.get("kinshipTerms", {})
    for key, term in kinship.items():
        canonical = term.get("canonical", "")
        variants = term.get("variants", [])
        check(
            canonical in variants,
            f"honorific.{key}.canonical",
            f"canonical '{canonical}' が variants に含まれていません",
        )

def validate_nfc() -> None:
    for json_file in SCHEMA_DIR.glob("*.json"):
        with open(json_file, encoding="utf-8") as f:
            raw = f.read()
        normalized = unicodedata.normalize("NFC", raw)
        check(
            raw == normalized,
            f"nfc: {json_file.name}",
            "NFC 正規化されていない文字が含まれます",
        )

def main() -> int:
    validate_ja_text_rules()
    validate_era_conversion()
    validate_honorific_dict()
    validate_nfc()

    if errors:
        print(f"✗ FAIL: {len(errors)} errors")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"✓ All validations passed ({checks_passed} checks)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

#### 4.8.4 受け入れ基準

- `uv run python claude-skills/narrative-intake/scripts/validate_ja_rules.py` が exit code 0 で完走する
- 5種類のチェック（JSON構文／必須キー／正規表現／元号計算／辞書整合性／NFC）がすべて実装されている
- エラー発生時は失敗した項目を具体的に表示する

---

## 5. 実装順序

以下の順序で実装すること。各ステップ完了後にファイル存在・構文チェックを行い、前ステップが成功してから次へ進む。

1. T1: `schema/ja_text_rules.json` 作成 → JSON valid 確認
2. T2: `schema/era_conversion.json` 作成 → JSON valid 確認
3. T3: `schema/honorific_dict.json` 作成 → JSON valid 確認
4. T8: `scripts/validate_ja_rules.py` 作成 → 実行して T1〜T3 を検証
5. T5: `prompts/relative_time_resolver.md` 作成
6. T4: `prompts/extraction_core.md` 編集（バックアップ先行）
7. T6: `SKILL.md` 編集（バックアップ先行）
8. T7: `examples/ja_optimization_test.md` 作成
9. 全体検証: 第6節参照

---

## 6. 検証とテスト

### 6.1 構文検証

```bash
# JSON 3ファイルの valid 確認
for f in claude-skills/narrative-intake/schema/ja_text_rules.json \
         claude-skills/narrative-intake/schema/era_conversion.json \
         claude-skills/narrative-intake/schema/honorific_dict.json; do
  python -c "import json; json.load(open('$f')); print('✓ $f')"
done

# 検証スクリプト実行
uv run python claude-skills/narrative-intake/scripts/validate_ja_rules.py
```

### 6.2 差分確認

```bash
# 既存ファイル編集の差分確認
git diff claude-skills/narrative-intake/prompts/extraction_core.md
git diff claude-skills/narrative-intake/SKILL.md
```

既存の `## 抽出ルール`・Few-shot セクション・出力フォーマットが**削除・改変されていない**ことを必ず目視確認すること。

### 6.3 ファイルツリー確認

```bash
tree claude-skills/narrative-intake/ -I '*.bak-*'
```

期待される構成:
```
claude-skills/narrative-intake/
├── SKILL.md
├── examples/
│   ├── daily_log_sample.md
│   ├── ja_optimization_test.md        # 新規
│   └── life_history_sample.md
├── prompts/
│   ├── extraction_core.md             # 編集
│   ├── few_shots.md
│   ├── relative_time_resolver.md      # 新規
│   └── safety_check.md
├── schema/
│   ├── allowed_labels.json
│   ├── allowed_rels.json
│   ├── enum_values.json
│   ├── era_conversion.json            # 新規
│   ├── honorific_dict.json            # 新規
│   ├── ja_text_rules.json             # 新規
│   └── merge_keys.json
├── scripts/
│   └── validate_ja_rules.py           # 新規
└── templates/
    ├── audit_log.cypher
    ├── preview_report.md
    └── upsert_graph.cypher
```

### 6.4 手動動作確認（Claude Desktop での確認手順）

実装完了後、次を手動で確認すること。

1. `setup.sh --skills` を再実行してシンボリックリンクを更新
2. Claude Desktop を再起動
3. `examples/ja_optimization_test.md` のテストケース1の入力ナラティブをそのまま Claude Desktop に貼り付け
4. Phase 1 出力に以下が含まれているか確認：
   - 元号がすべて西暦に変換されている
   - 親族呼称が統一されている
   - 半角カタカナ・全角数字が正規化されている
   - 相対時間表現が解決または warnings に記録されている

---

## 7. 完了基準（Definition of Done）

すべての項目が ✓ になったら完了とみなす。

- [ ] T1〜T8 のすべてのファイルが作成・編集されている
- [ ] `validate_ja_rules.py` が exit code 0 で完走する
- [ ] 既存ファイル（`extraction_core.md`, `SKILL.md`）のバックアップが作成されている
- [ ] 既存セクションに破壊的変更がない（git diff で確認）
- [ ] `examples/ja_optimization_test.md` に5件以上のテストケース
- [ ] `tree` コマンドの出力が第6.3節の期待構成と一致する
- [ ] 全ファイルが UTF-8 / NFC 正規化済み
- [ ] グローバルルール（日本語・バックアップ・承認）を遵守している
- [ ] 変更内容のサマリーを日本語で報告している

---

## 8. コミットメッセージ雛形

実装完了後、以下の雛形でコミットすること。**ユーザーから明示的な指示があるまで push しない**。

```
feat(narrative-intake): 日本語最適化ルールの追加

- schema/ja_text_rules.json: 文境界・引用括弧・分割禁止位置・NFC正規化ルール
- schema/era_conversion.json: 明治〜令和の元号変換表
- schema/honorific_dict.json: 敬称・親族呼称の正規化辞書
- prompts/relative_time_resolver.md: 相対時間表現の解決アルゴリズム
- prompts/extraction_core.md: 日本語前処理セクションの追記
- SKILL.md: 日本語最適化ルールへの参照追記
- examples/ja_optimization_test.md: エンドツーエンドテストケース5件
- scripts/validate_ja_rules.py: 構文・整合性検証スクリプト

元号（昭和/平成/令和）→ 西暦変換、半角カタカナ/全角数字の NFC 正規化、
親族呼称の統合（お母さん/母親/実母 → 母）、相対時間表現の解決を
Phase 1 抽出段階で実施するようにした。Python 側の ai_extractor.py や
db_new_operations.py には変更なし。

検証: uv run python claude-skills/narrative-intake/scripts/validate_ja_rules.py
```

---

## 9. 未解決の論点（実装者の判断で保留してよい）

以下は本指示書の範囲外だが、実装中に気づいたら `docs/NARRATIVE_INTAKE_JA_OPTIMIZATION_SPEC.md` にコメントで追記してよい。

1. **形態素解析ライブラリ**（MeCab, Sudachi）との連携は将来課題とする。本タスクでは Claude/Gemini の文脈理解に依存するルールベースで十分。
2. **LifeStage の年齢範囲**（例: 幼児期 = 1〜6歳）の厳密定義は `docs/LIFE_HISTORY_TO_NEO4J_LULES.md` にすでに存在するため、本タスクでは重複定義を避ける。必要なら将来 `schema/life_stage_ages.json` として切り出す。
3. **方言・カジュアル表現**（「〜やん」「〜やで」）の正規化は今回対象外。必要なら `schema/dialect_rules.json` を将来追加。
4. **OCR 由来の誤字**（例: "l0" と "10" の混同）の自動補正も対象外。`lib/embedding.py::ocr_with_gemini` の責務範囲。

---

## 10. 質問・確認事項

実装中に不明点があった場合は、以下の判断基準で進めること。

- **スキーマ定義に関する疑問** → `docs/NEO4J_SCHEMA_CONVENTION.md` を最優先で参照
- **元号変換の境界ケース** → `schema/era_conversion.json` の `parsingRules.boundaryDates` に従う
- **プロンプトの文言** → 既存の `prompts/extraction_core.md` のトーンと一貫性を保つ
- **判断がつかない場合** → 実装を止めてユーザー（河原）に確認する

---

**本指示書の最終確認**: 作業開始前に、この指示書全体を一度通読し、タスクの依存関係を把握してから T1 に着手すること。

# 生育歴ナラティブ → Neo4j 構造化ルール

## 1. 概要

物語調で記載された知的障害者の生育歴を、既存の4本柱データモデル（特に第1の柱「本人性」）と整合する形でNeo4jグラフに変換するためのルール。

**設計思想**: 生育歴は「出来事の羅列」ではなく、**その人がなぜ今こうなのか**を説明する因果の物語。グラフはその因果関係を明示的にたどれるようにする。

---

## 2. ノード設計

### 2.1 中核ノード

| ラベル | 説明 | 必須プロパティ | 任意プロパティ |
|---|---|---|---|
| `:Client` | 本人（既存） | `name`, `birthDate` | `gender`, `bloodType` |
| `:LifeEvent` | 生育歴上の出来事 | `id`(UUID), `title`, `period`, `ageRange` | `description`, `source`, `reliability` |
| `:LifeStage` | 発達段階 | `name`, `order` | `startAge`, `endAge` |
| `:Person` | 登場人物 | `name`, `role` | `relationship`, `isAlive` |
| `:Place` | 場所・環境 | `name`, `type` | `address`, `period` |
| `:Condition` | 障害・疾患（既存） | `name`, `type` | `diagnosedAge`, `severity` |
| `:Emotion` | 本人の感情・心理状態 | `name` | `valence`(+1/-1), `intensity`(1-5) |
| `:Skill` | 獲得したスキル・能力 | `name`, `domain` | `level` |
| `:Service` | 利用した福祉サービス・学校 | `name`, `type` | `period`, `evaluation` |

### 2.2 LifeStage（発達段階）の標準値

```cypher
// 初期セットアップ
UNWIND [
  {name:"胎児期・出生", order:0, startAge:null, endAge:0},
  {name:"乳児期",       order:1, startAge:0,    endAge:1},
  {name:"幼児期",       order:2, startAge:1,    endAge:6},
  {name:"学齢期前半",   order:3, startAge:6,    endAge:12},
  {name:"学齢期後半",   order:4, startAge:12,   endAge:15},
  {name:"青年期",       order:5, startAge:15,   endAge:20},
  {name:"成人期",       order:6, startAge:20,   endAge:40},
  {name:"壮年期",       order:7, startAge:40,   endAge:65},
  {name:"高齢期",       order:8, startAge:65,   endAge:null}
] AS s
MERGE (ls:LifeStage {name: s.name})
SET ls.order = s.order, ls.startAge = s.startAge, ls.endAge = s.endAge
```

---

## 3. リレーション設計と重み付け

### 3.1 リレーション一覧

| リレーション | 始点 → 終点 | 重み付けプロパティ | 説明 |
|---|---|---|---|
| `EXPERIENCED` | Client → LifeEvent | `impact`(-5〜+5) | 本人が経験した出来事 |
| `BELONGS_TO` | LifeEvent → LifeStage | ― | 出来事が属する発達段階 |
| `CAUSED` | LifeEvent → LifeEvent | `strength`(1-5), `certainty`(推定/確実) | 出来事間の因果関係 |
| `INVOLVED` | LifeEvent → Person | `role`(加害/保護/傍観/支援) | 出来事への関与者 |
| `OCCURRED_AT` | LifeEvent → Place | ― | 出来事の場所 |
| `LED_TO_CONDITION` | LifeEvent → Condition | `strength`(1-5) | 出来事が障害・症状に与えた影響 |
| `TRIGGERED` | LifeEvent → Emotion | `duration`(一時的/持続的/現在も) | 出来事が引き起こした感情 |
| `ENABLED` | LifeEvent → Skill | `strength`(1-5) | 出来事を通じて獲得した能力 |
| `SUPPORTED_BY` | LifeEvent → Service | `effectiveness`(1-5) | 福祉サービスとの関連 |
| `RELATES_TO` | LifeEvent → CarePreference | `derivation`(直接/間接) | 現在のケア方針の根拠 |
| `EXPLAINS` | LifeEvent → NgAction | `derivation`(直接/間接) | 禁忌事項の背景となる体験 |

### 3.2 重み付けルール

#### `impact`（影響度: -5 〜 +5）

出来事が本人の発達・人生に与えた影響の方向と大きさ。

| 値 | 意味 | 例 |
|---|---|---|
| +5 | 人生の転機となるプラス | 理解ある教師との出会いで自信を回復 |
| +3 | 明確なプラス | 作業所で仲間ができた |
| +1 | 軽いプラス | 好きな活動を見つけた |
| 0 | 中立/判定困難 | 転居（影響不明） |
| -1 | 軽いマイナス | 環境変化で一時不安定に |
| -3 | 明確なマイナス | いじめにより不登校 |
| -5 | 深刻なトラウマ | 虐待、重大事故 |

#### `strength`（因果の強さ: 1〜5）

| 値 | 意味 |
|---|---|
| 5 | 直接の原因（医学的診断、明確な因果） |
| 4 | 強い関連（専門家の所見あり） |
| 3 | 蓋然性の高い推測 |
| 2 | 関連の可能性あり |
| 1 | 弱い示唆 |

#### `certainty`（確実性）

| 値 | 基準 |
|---|---|
| `confirmed` | 診断書・公的記録に基づく |
| `reported` | 家族・本人の証言 |
| `inferred` | 支援者の専門的推測 |
| `uncertain` | 記述から読み取れるが不明瞭 |

---

## 4. ナラティブ→Cypher変換の手順

### Step 1: 登場人物の抽出

```cypher
// 例: 母・父・担任教師
MERGE (p1:Person {name: "母（仮名A）", role: "母親"})
SET p1.relationship = "実母", p1.isAlive = true

MERGE (p2:Person {name: "担任B先生", role: "教師"})
SET p2.relationship = "小学校担任"
```

### Step 2: LifeEventの作成

```cypher
MERGE (e:LifeEvent {id: "evt-001"})
SET e.title = "出生時の仮死状態",
    e.period = "出生時",
    e.ageRange = "0歳",
    e.description = "難産で出生時に一時的な仮死状態。蘇生後NICUに2週間入院。",
    e.source = "母親からの聞き取り",
    e.reliability = "reported"
```

### Step 3: リレーションの構築と重み付け

```cypher
// Client → LifeEvent（影響度付き）
MATCH (c:Client {name: "山田健太"})
MATCH (e:LifeEvent {id: "evt-001"})
MERGE (c)-[:EXPERIENCED {impact: -4, note: "発達への影響が示唆される"}]->(e)

// LifeEvent → LifeStage
MATCH (e:LifeEvent {id: "evt-001"})
MATCH (ls:LifeStage {name: "胎児期・出生"})
MERGE (e)-[:BELONGS_TO]->(ls)

// LifeEvent → Condition（因果関係）
MATCH (e:LifeEvent {id: "evt-001"})
MERGE (cond:Condition {name: "知的障害", type: "障害"})
MERGE (e)-[:LED_TO_CONDITION {
  strength: 3,
  certainty: "inferred",
  note: "出生時低酸素と発達遅延の関連が推測される"
}]->(cond)

// LifeEvent → LifeEvent（因果連鎖）
MATCH (e1:LifeEvent {id: "evt-001"})
MATCH (e2:LifeEvent {id: "evt-003"})
MERGE (e1)-[:CAUSED {
  strength: 3,
  certainty: "inferred",
  note: "出生時の問題→3歳時点での発達遅延の発見"
}]->(e2)
```

### Step 4: 現在のケアとの紐づけ

```cypher
// 生育歴上の出来事 → 現在の禁忌事項の根拠
MATCH (e:LifeEvent {id: "evt-012"})  // 大声で叱られパニック発作
MATCH (ng:NgAction {action: "大声で叱る"})
MERGE (e)-[:EXPLAINS {derivation: "直接"}]->(ng)

// 生育歴上の出来事 → 現在のケア方針の根拠
MATCH (e:LifeEvent {id: "evt-015"})  // 音楽で落ち着いた経験
MATCH (cp:CarePreference {category: "パニック時"})
MERGE (e)-[:RELATES_TO {derivation: "直接"}]->(cp)
```

---

## 5. 抽出時のAIプロンプトルール

LLMで物語調テキストから構造化する際、以下を遵守する。

### 5.1 抽出対象の分類

| カテゴリ | 抽出すべき情報 | LifeEventのタグ |
|---|---|---|
| 医療 | 出生状況、診断、入院、服薬開始 | `medical` |
| 教育 | 就学、転校、不登校、卒業 | `education` |
| 家族 | 離婚、死別、虐待、養育環境の変化 | `family` |
| 福祉 | サービス利用開始、施設入所、手帳取得 | `welfare` |
| 対人 | いじめ、友人関係、支援者との出会い | `social` |
| 行動 | パニック、自傷、他害の初発・変化 | `behavior` |
| 成功体験 | 就労、作品制作、表彰、人間関係の構築 | `achievement` |
| 転機 | 大きな環境変化、気づき、方針転換 | `turning_point` |

### 5.2 判定基準

- **LifeEventとして切り出すか？** → 「今の支援に影響するか」が基準。日常のエピソードは原則除外。
- **impact値をどう決めるか？** → ナラティブ上の記述量・語調・繰り返し回数で判断。「今でも〜」「それ以来〜」等の表現は高影響度の手がかり。
- **因果関係を付けるか？** → 文脈上「〜がきっかけで」「〜の結果」「〜から」と読み取れる場合のみ。安易な因果推定は避け、`certainty: "inferred"` を明示する。

### 5.3 倫理規範

- **ラベリングの禁止**: 「問題児だった」等の評価的表現をそのままプロパティにしない。事実ベースに書き直す。
- **本人の声の優先**: 家族の視点と本人の視点が異なる場合、`source`プロパティで区別して両方記録する。
- **強みの可視化**: マイナス要因だけでなく、プラスの出来事・スキル獲得を必ず抽出する。

---

## 6. クエリテンプレート

### 6.1 時系列トレース（人生を追う）

```cypher
MATCH (c:Client {name: $name})-[r:EXPERIENCED]->(e:LifeEvent)-[:BELONGS_TO]->(ls:LifeStage)
OPTIONAL MATCH (e)-[:TRIGGERED]->(em:Emotion)
RETURN ls.name AS 段階, ls.order AS 順序,
       e.title AS 出来事, e.ageRange AS 年齢,
       r.impact AS 影響度,
       collect(em.name) AS 感情
ORDER BY ls.order, e.ageRange
```

### 6.2 因果チェーン探索（なぜ今こうなのか）

```cypher
MATCH path = (e1:LifeEvent)-[:CAUSED*1..5]->(e2:LifeEvent)
WHERE e1.id = $startEventId
RETURN [n IN nodes(path) | n.title] AS 因果連鎖,
       [r IN relationships(path) | r.strength] AS 強度,
       length(path) AS 深さ
ORDER BY reduce(s=0, r IN relationships(path) | s + r.strength) DESC
```

### 6.3 プラス・マイナス要因サマリー

```cypher
MATCH (c:Client {name: $name})-[r:EXPERIENCED]->(e:LifeEvent)
WITH e, r,
     CASE WHEN r.impact > 0 THEN "プラス"
          WHEN r.impact < 0 THEN "マイナス"
          ELSE "中立" END AS 方向
RETURN 方向,
       count(e) AS 件数,
       avg(abs(r.impact)) AS 平均強度,
       collect(e.title) AS 出来事一覧
ORDER BY 方向
```

### 6.4 禁忌事項の根拠トレース

```cypher
MATCH (c:Client {name: $name})-[:MUST_AVOID]->(ng:NgAction)
OPTIONAL MATCH (e:LifeEvent)-[ex:EXPLAINS]->(ng)
OPTIONAL MATCH (c)-[r:EXPERIENCED]->(e)
RETURN ng.action AS 禁忌,
       ng.reason AS 理由,
       e.title AS 背景となる出来事,
       e.ageRange AS 発生年齢,
       r.impact AS 影響度,
       ex.derivation AS 関連性
```

### 6.5 発達段階別レジリエンスマップ

```cypher
MATCH (c:Client {name: $name})-[r:EXPERIENCED]->(e:LifeEvent)-[:BELONGS_TO]->(ls:LifeStage)
WITH ls, 
     sum(CASE WHEN r.impact > 0 THEN r.impact ELSE 0 END) AS プラス合計,
     sum(CASE WHEN r.impact < 0 THEN r.impact ELSE 0 END) AS マイナス合計,
     count(e) AS 出来事数
RETURN ls.name AS 段階, ls.order AS 順序,
       プラス合計, マイナス合計,
       プラス合計 + マイナス合計 AS 純影響度,
       出来事数
ORDER BY ls.order
```

---

## 7. 命名規則・運用ルール

| 項目 | ルール |
|---|---|
| LifeEvent ID | `evt-{クライアントイニシャル}-{連番3桁}` 例: `evt-YK-001` |
| Person名 | 個人情報保護のため仮名可。`role`で関係性を明示 |
| period表記 | 「0歳」「3歳頃」「小学2年〜4年」「20代前半」等の自然な表現 |
| source | `母親聞取`, `本人聞取`, `支援記録`, `診断書`, `学校記録` 等 |
| 1回のバッチ | 1人の生育歴は1トランザクション内で投入する |

---

## 8. 実行例（完全版）

以下は架空のナラティブからの変換例。

**原文（抜粋）**:
> 健太は難産で生まれ、出生時に仮死状態となった。3歳児健診で言葉の遅れを指摘され、5歳で療育手帳B2を取得した。小学校では通常学級に入ったが、3年生の頃からいじめに遭い、不登校気味になった。担任の田中先生が個別に対応してくれたことで徐々に登校できるようになった。

```cypher
// === トランザクション開始 ===

// Client（既存を想定）
MERGE (c:Client {name: "山田健太"})

// LifeStageは事前セットアップ済み

// --- LifeEvent群 ---
MERGE (e1:LifeEvent {id: "evt-YK-001"})
SET e1 += {title:"出生時仮死", period:"出生時", ageRange:"0歳",
  description:"難産で出生時に一時的な仮死状態", 
  source:"母親聞取", reliability:"reported", tag:"medical"}

MERGE (e2:LifeEvent {id: "evt-YK-002"})
SET e2 += {title:"3歳児健診で言語遅滞指摘", period:"3歳", ageRange:"3歳",
  description:"3歳児健診で言葉の遅れを指摘される",
  source:"母親聞取", reliability:"reported", tag:"medical"}

MERGE (e3:LifeEvent {id: "evt-YK-003"})
SET e3 += {title:"療育手帳B2取得", period:"5歳", ageRange:"5歳",
  description:"療育手帳B2を取得",
  source:"母親聞取", reliability:"confirmed", tag:"welfare"}

MERGE (e4:LifeEvent {id: "evt-YK-004"})
SET e4 += {title:"通常学級でのいじめ・不登校", period:"小学3年〜", ageRange:"8歳〜",
  description:"通常学級で3年生頃からいじめに遭い不登校気味に",
  source:"母親聞取", reliability:"reported", tag:"social"}

MERGE (e5:LifeEvent {id: "evt-YK-005"})
SET e5 += {title:"担任の個別対応で登校回復", period:"小学校中学年", ageRange:"9歳頃",
  description:"担任の田中先生が個別対応し、徐々に登校できるように",
  source:"母親聞取", reliability:"reported", tag:"turning_point"}

// --- 登場人物 ---
MERGE (p1:Person {name:"田中先生", role:"小学校担任"})

// --- EXPERIENCED（影響度付き） ---
MERGE (c)-[:EXPERIENCED {impact:-4, note:"発達への影響示唆"}]->(e1)
MERGE (c)-[:EXPERIENCED {impact:-2, note:"障害の顕在化"}]->(e2)
MERGE (c)-[:EXPERIENCED {impact: 0, note:"制度上の手続き"}]->(e3)
MERGE (c)-[:EXPERIENCED {impact:-4, note:"対人関係トラウマ"}]->(e4)
MERGE (c)-[:EXPERIENCED {impact:+4, note:"信頼関係による回復"}]->(e5)

// --- BELONGS_TO ---
MATCH (ls0:LifeStage {name:"胎児期・出生"})
MERGE (e1)-[:BELONGS_TO]->(ls0)
MATCH (ls2:LifeStage {name:"幼児期"})
MERGE (e2)-[:BELONGS_TO]->(ls2)
MERGE (e3)-[:BELONGS_TO]->(ls2)
MATCH (ls3:LifeStage {name:"学齢期前半"})
MERGE (e4)-[:BELONGS_TO]->(ls3)
MERGE (e5)-[:BELONGS_TO]->(ls3)

// --- 因果関係 ---
MERGE (e1)-[:CAUSED {strength:3, certainty:"inferred",
  note:"出生時低酸素→発達遅延の可能性"}]->(e2)
MERGE (e2)-[:CAUSED {strength:4, certainty:"reported",
  note:"言語遅滞の指摘→手帳取得へ"}]->(e3)
MERGE (e4)-[:CAUSED {strength:4, certainty:"reported",
  note:"いじめ→担任が個別対応を開始"}]->(e5)

// --- INVOLVED ---
MERGE (e5)-[:INVOLVED {role:"支援"}]->(p1)

// --- 感情 ---
MERGE (em1:Emotion {name:"恐怖"})
MERGE (e4)-[:TRIGGERED {duration:"持続的"}]->(em1)
MERGE (em2:Emotion {name:"安心"})
MERGE (e5)-[:TRIGGERED {duration:"持続的"}]->(em2)

// --- 現在のケアへの接続 ---
// （既存NgAction/CarePreferenceがあれば紐づける）
// MATCH (ng:NgAction {action: "大声で叱る"})
// MERGE (e4)-[:EXPLAINS {derivation:"直接"}]->(ng)

// === トランザクション終了 ===
```

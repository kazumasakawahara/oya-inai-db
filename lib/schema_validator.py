"""
スキーマバリデーションモジュール (The Guardian)

SCHEMA_CONVENTION.md に基づき、プロパティ名の camelCase 自動変換、
ノードラベル・リレーションタイプ・列挙値の検証を行う。
LLM が生成した構造化データの品質を担保する「守護神」レイヤー。
"""

import re
import sys
from datetime import date, datetime


def _log(message: str, level: str = "INFO"):
    sys.stderr.write(f"[SchemaValidator:{level}] {message}\n")
    sys.stderr.flush()


# =============================================================================
# 正式なノードラベル (SCHEMA_CONVENTION.md 準拠)
# =============================================================================

VALID_NODE_LABELS_7687 = frozenset({
    "Client", "Condition", "NgAction", "CarePreference", "KeyPerson",
    "Guardian", "Hospital", "Certificate", "PublicAssistance", "Organization",
    "Supporter", "SupportLog", "MeetingRecord", "AuditLog", "LifeHistory",
    "Wish", "Identity", "ServiceProvider", "ProviderFeedback",
    # 第5の柱（親の機能移行）— SSOT v3.1
    "Relative", "CareRole",
    # かかりつけ医の構造化（P2 / 2026-07）— Hospital.doctor 文字列から昇格
    "Doctor",
    # 確認記録（SSOT v3.3 / 2026-07-12）—「確認したうえで0件」と「未確認」を
    # 区別する唯一の手段（SEMANTIC_MODEL ENT-24 / BRS-12）
    "Review",
})

# 生活困窮者自立支援DB（port 7688）は 2026-05 廃止。7688 用のラベル定義は撤去済み。
VALID_NODE_LABELS = VALID_NODE_LABELS_7687

# =============================================================================
# 正式なリレーションシップタイプ
# =============================================================================

VALID_RELATIONSHIP_TYPES = frozenset({
    # port 7687
    "HAS_CONDITION", "MUST_AVOID", "IN_CONTEXT", "REQUIRES", "ADDRESSES",
    "HAS_KEY_PERSON", "HAS_LEGAL_REP", "HAS_CERTIFICATE", "RECEIVES",
    "REGISTERED_AT", "TREATED_AT", "SUPPORTED_BY", "LOGGED", "RECORDED",
    "ABOUT", "FOLLOWS", "AUDIT_FOR", "HAS_HISTORY", "HAS_WISH",
    "HAS_IDENTITY", "USES_SERVICE", "HAS_FEEDBACK", "WROTE",
    # 第5の柱（親の機能移行）— SSOT v3.1
    "IS_PARENT_OF", "FAMILY_OF", "PERFORMS", "CAN_BE_PERFORMED_BY",
    # かかりつけ医の構造化（P2 / 2026-07）
    "HAS_DOCTOR",
    # 確認記録（SSOT v3.3 / 2026-07-12）Supporter → Review。
    # Review → Client は既存の ABOUT を再利用する。
    "REVIEWED",
    # 証拠・鮮度モデル（SSOT v3.4 / 2026-08-08・BRS-13）。いずれも追記専用。
    # CONTRADICTS: 新観測 → 既存事実（矛盾の保留。resolvedAt IS NULL = 係争中）
    # CONFIRMS:    Review → 既存事実（個別確認。無印 Review は従来の0件確認）
    "CONTRADICTS", "CONFIRMS",
})

# 廃止リレーション → 正式名のマッピング (書き込み時の自動修正用)
# HOLDS は 7688 用ではなく 7687 の旧・手帳リレーション（SCHEMA_CONVENTION §5）。
DEPRECATED_RELATIONSHIPS = {
    "PROHIBITED": "MUST_AVOID",
    "PREFERS": "REQUIRES",
    "EMERGENCY_CONTACT": "HAS_KEY_PERSON",
    "RELATES_TO": "IN_CONTEXT",
    "HAS_GUARDIAN": "HAS_LEGAL_REP",
    "HOLDS": "HAS_CERTIFICATE",
}

# =============================================================================
# 列挙値の定義
# =============================================================================

ENUM_VALUES = {
    "riskLevel": {"LifeThreatening", "Panic", "Discomfort"},
    # 訂正（2026-07-12・DRIFT-05）: 旧定義は High/Medium/Low を含んでいたが、
    # これは priority の値域との混同。effectiveness の正式値は SCHEMA_CONVENTION
    # §7.2 の4値のみ。priority の検証は同時に新設した。
    "effectiveness": {"Effective", "Ineffective", "Neutral", "Unknown"},
    "priority": {"High", "Medium", "Low"},
    "emotion": {"Joy", "Anger", "Sadness", "Fear", "Surprise", "Disgust", "Calm", "Anxiety", "Confusion", "Neutral"},
    # Monitoring: Condition の「経過観察中」など、継続監視状態（P2 / 2026-07 追加）
    "status": {"Active", "Inactive", "Pending", "Completed", "Suspended", "Monitoring"},
}

# =============================================================================
# ラベル限定の列挙値（2026-07-12 新設・SSOT v3.3）
# =============================================================================
# ENUM_VALUES は「プロパティ名だけ」で引くため、`source` のような一般的な名前を
# そこに入れると、他ノードの同名プロパティに誤検知が出る。
# Review の domain / source はこちらでラベル限定して検証する。
# 値域の正は SCHEMA_CONVENTION §7.7 / §7.8（意味は SEMANTIC_MODEL ENU-16 / ENU-17）。
LABEL_SCOPED_ENUM_VALUES = {
    "Review": {
        # 確認した領域。対応するノードラベル名をそのまま使う。
        # 0件が安全・権利に直結する6領域に限定。
        "domain": {
            "NgAction", "CarePreference", "KeyPerson",
            "Guardian", "Certificate", "CareRole",
        },
        # 誰に確認したか。信頼度の判断材料なので推測で埋めてはならない。
        # 「記録のみ」は最も弱い情報源（人に聞いていない）。
        "source": {
            "本人", "母親", "父親", "家族・親族", "主治医",
            "前事業所", "相談支援専門員", "後見人等", "記録のみ",
        },
    },
}


def validate_label_scoped_enum(label: str, prop_name: str, value: str) -> tuple[bool, str]:
    """
    ラベル限定の列挙値を検証する（Review.domain / Review.source 等）。

    ENUM_VALUES と違い、ノードラベルを見てから検証するので、
    他ノードの同名プロパティ（例: 別のノードの source）に誤検知しない。

    Returns:
        (is_valid, message)
    """
    scoped = LABEL_SCOPED_ENUM_VALUES.get(label)
    if not scoped or prop_name not in scoped:
        return True, ""

    valid_values = scoped[prop_name]
    if value in valid_values:
        return True, ""

    return False, (
        f"{label}.{prop_name} の値 '{value}' は不正です。"
        f" 有効な値: {sorted(valid_values)}"
    )

# =============================================================================
# 必須プロパティ・事実時間軸（SSOT v3.5 / SEMANTIC_MODEL v1.8・2026-09-03）
# =============================================================================
# 値の正は SEMANTIC_MODEL §6 machine-check JSON（requiredProperties / restrictedStatus /
# immutableProperties / conditionalRequired / relationshipProperties）。
# check_semantic_drift.py が以下の定数を正本と突合する（不一致は FAIL）。
#
# support-db は2本の時間軸を持つ（SCHEMA_CONVENTION §7.10 / BRS-14）:
#   知得時間 = lastConfirmedAt / Review / CONTRADICTS / AuditLog（§7.9・ここでは触れない）
#   事実時間 = registeredAt（不変）/ validFrom（任意）/ validTo（Inactive で必須）
# Guardian は CREATE / UPDATE を区別できないので、既定値の付与と不変プロパティの破棄は
# 書き込み経路（MERGE の ON CREATE / ON MATCH）が本モジュールの関数を呼んで行う。

# Phase 1（v1.6）で正本化されたが Guardian に定数が無かった必須プロパティ。
# 欠落は「警告」であって拒否ではない（書き込み経路が registeredAt を補うため）。
REQUIRED_PROPERTIES = {
    "NgAction": frozenset({"source", "status", "lastConfirmedAt", "registeredAt"}),
    "CarePreference": frozenset({"source", "status", "lastConfirmedAt", "registeredAt"}),
}

# この2ラベルの status は3値に制限（BRS-13）。
RESTRICTED_STATUS = {
    "NgAction": frozenset({"Active", "Pending", "Inactive"}),
    "CarePreference": frozenset({"Active", "Pending", "Inactive"}),
}

# CREATE 時に自動付与し、以後どの経路でも書き換えない（BRS-14「不変の登録日」）。
IMMUTABLE_PROPERTIES = {
    "NgAction": frozenset({"registeredAt"}),
    "CarePreference": frozenset({"registeredAt"}),
}

# validTo は status=Inactive で必須、Active/Pending では null 必須（BRS-14「validTo は裁定と同時」）。
CONDITIONAL_REQUIRED = {
    "NgAction": {
        "when": {"status": "Inactive"}, "require": ["validTo"],
        "forbidWhen": {"status": ["Active", "Pending"]}, "forbid": ["validTo"],
    },
    "CarePreference": {
        "when": {"status": "Inactive"}, "require": ["validTo"],
        "forbidWhen": {"status": ["Active", "Pending"]}, "forbid": ["validTo"],
    },
}

# リレーションのプロパティ規則。HAS_KEY_PERSON は交代を張り替えず履歴にする（ENT-08 / BRS-14）。
RELATIONSHIP_PROPERTIES = {
    "HAS_KEY_PERSON": {
        "required": ["rank", "startDate", "status"], "optional": ["endDate"],
        "status": ["Active", "Inactive"], "requireWhenInactive": ["endDate"],
    },
    "USES_SERVICE": {"required": ["startDate", "status"], "optional": ["endDate"]},
}

# date 型で保存するプロパティ（型検証と、書き込み前の date への変換対象）。
# 文字列のまま保存すると Cypher の date() 比較が null になり、時点照会から静かに漏れる。
DATE_PROPERTIES = {
    "NgAction": frozenset({"registeredAt", "validFrom", "validTo"}),
    "CarePreference": frozenset({"registeredAt", "validFrom", "validTo"}),
    "PublicAssistance": frozenset({"endDate"}),
}
RELATIONSHIP_DATE_PROPERTIES = {
    "HAS_KEY_PERSON": frozenset({"startDate", "endDate"}),
}


def _parse_date(value):
    """date / datetime / ISO 文字列（YYYY-MM-DD）を date にする。解釈できなければ ValueError。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "to_native"):  # neo4j.time.Date
        return _parse_date(value.to_native())
    if isinstance(value, str):
        return date.fromisoformat(value.strip()[:10])
    raise ValueError(f"date として解釈できません: {value!r}")


def coerce_date_properties(label: str, props: dict, date_props: dict | None = None) -> dict:
    """date プロパティの文字列を date に変換した新しい dict を返す（不正値はそのまま残す。検証は別）。"""
    table = DATE_PROPERTIES if date_props is None else date_props
    targets = table.get(label)
    if not targets:
        return dict(props)
    out = dict(props)
    for key in targets:
        if key in out and out[key] is not None:
            try:
                out[key] = _parse_date(out[key])
            except ValueError:
                pass
    return out


def validate_required_properties(label: str, props: dict) -> list[str]:
    """必須プロパティの欠落を警告文として返す（拒否しない。書き込み経路が既定値を補う）。"""
    required = REQUIRED_PROPERTIES.get(label)
    if not required:
        return []
    missing = sorted(k for k in required if props.get(k) is None)
    if not missing:
        return []
    return [f"{label}: 必須プロパティが未設定です: {missing}（registeredAt は新規作成時に自動付与）"]


def validate_fact_time(label: str, props: dict) -> list[str]:
    """事実時間軸の規則違反を返す。1件でもあれば書き込みに進んではならない。

    - status は RESTRICTED_STATUS の値域内
    - status=Inactive → validTo 必須 / Active・Pending → validTo は null
    - validFrom と validTo が両方あれば validFrom <= validTo
    - DATE_PROPERTIES は date として解釈できること（PublicAssistance.endDate は型検証のみ）
    """
    errors: list[str] = []
    parsed: dict[str, date] = {}
    for key in DATE_PROPERTIES.get(label, ()):
        value = props.get(key)
        if value is None:
            continue
        try:
            parsed[key] = _parse_date(value)
        except ValueError:
            errors.append(f"{label}.{key} の値 {value!r} は date（YYYY-MM-DD）として解釈できません")

    status = props.get("status")
    allowed = RESTRICTED_STATUS.get(label)
    if allowed and status is not None and status not in allowed:
        errors.append(f"{label}.status の値 '{status}' は不正です。有効な値: {sorted(allowed)}")

    rule = CONDITIONAL_REQUIRED.get(label)
    if rule and status is not None:
        if all(status == v for v in rule["when"].values()):
            for key in rule["require"]:
                if props.get(key) is None:
                    errors.append(
                        f"{label}: status={status} には {key} が必須です"
                        "（管理者裁定による Inactive 化と同一トランザクションで記入）"
                    )
        if all(status in v for v in rule["forbidWhen"].values()):
            for key in rule["forbid"]:
                if props.get(key) is not None:
                    errors.append(
                        f"{label}: status={status} のとき {key} は設定できません"
                        "（validTo が入る唯一の経路は Inactive 化の裁定）"
                    )

    if "validFrom" in parsed and "validTo" in parsed and parsed["validFrom"] > parsed["validTo"]:
        errors.append(
            f"{label}: validFrom({parsed['validFrom']}) が validTo({parsed['validTo']}) より後です"
        )
    return errors


def strip_immutable_properties(label: str, props: dict) -> tuple[dict, list[str]]:
    """既存ノードの更新（MERGE の ON MATCH）用。不変プロパティを入力から破棄し警告を返す。"""
    immutable = IMMUTABLE_PROPERTIES.get(label)
    if not immutable:
        return dict(props), []
    out = {k: v for k, v in props.items() if k not in immutable}
    dropped = sorted(k for k in props if k in immutable)
    warnings = [
        f"{label}.{k} は不変プロパティです。更新入力から破棄しました（初回登録日は書き換えない）"
        for k in dropped
    ]
    for w in warnings:
        _log(w, "WARN")
    return out, warnings


def apply_fact_time_defaults(label: str, props: dict, today: date | None = None) -> dict:
    """新規作成（MERGE の ON CREATE / CREATE）用。registeredAt が無ければ当日を付与し、date 型に揃える。"""
    out = coerce_date_properties(label, props)
    if label in IMMUTABLE_PROPERTIES and "registeredAt" in IMMUTABLE_PROPERTIES[label]:
        if out.get("registeredAt") is None:
            out["registeredAt"] = today or date.today()
    return out


def validate_relationship_properties(rel_type: str, props: dict) -> tuple[list[str], list[str]]:
    """リレーションのプロパティ規則。(errors, warnings) を返す。

    errors: status の値域外 / Inactive で endDate 欠落 / date として解釈できない値
    warnings: 必須プロパティの欠落（新規作成時は書き込み経路が startDate・status を補う）
    """
    rule = RELATIONSHIP_PROPERTIES.get(rel_type)
    if not rule:
        return [], []
    errors: list[str] = []
    warnings: list[str] = []

    for key in RELATIONSHIP_DATE_PROPERTIES.get(rel_type, ()):
        value = props.get(key)
        if value is None:
            continue
        try:
            _parse_date(value)
        except ValueError:
            errors.append(f"{rel_type}.{key} の値 {value!r} は date（YYYY-MM-DD）として解釈できません")

    status = props.get("status")
    if "status" in rule and status is not None and status not in rule["status"]:
        errors.append(f"{rel_type}.status の値 '{status}' は不正です。有効な値: {sorted(rule['status'])}")
    if status == "Inactive":
        for key in rule.get("requireWhenInactive", []):
            if props.get(key) is None:
                errors.append(
                    f"{rel_type}: status=Inactive には {key} が必須です"
                    "（交代は張り替えず、旧リレーションに endDate + Inactive を書く）"
                )

    missing = sorted(k for k in rule["required"] if props.get(k) is None)
    if missing:
        warnings.append(f"{rel_type}: 必須プロパティが未設定です: {missing}（新規作成時は startDate・status を自動付与）")
    return errors, warnings


def apply_relationship_defaults(rel_type: str, props: dict, today: date | None = None) -> dict:
    """新規作成用。HAS_KEY_PERSON の startDate（当日）・status（Active）を補い、date 型に揃える。"""
    rule = RELATIONSHIP_PROPERTIES.get(rel_type)
    if not rule:
        return dict(props)
    out = coerce_date_properties(rel_type, props, RELATIONSHIP_DATE_PROPERTIES)
    if "startDate" in rule["required"] and out.get("startDate") is None:
        out["startDate"] = today or date.today()
    if "status" in rule and out.get("status") is None:
        out["status"] = "Active"
    return out


# 安全クリティカルな riskLevel の別名 → 正規値（小文字キーで照合）。
# 誤入力による禁忌の優先度低下を防ぐ。ここに無い値は補正せず警告する
# （安全に関わる値を勝手に推測・捏造しない）。
RISK_LEVEL_ALIASES = {
    "lifethreatening": "LifeThreatening",
    "life_threatening": "LifeThreatening",
    "life-threatening": "LifeThreatening",
    "生命に関わる": "LifeThreatening",
    "生命の危険": "LifeThreatening",
    "致命的": "LifeThreatening",
    "critical": "LifeThreatening",
    "panic": "Panic",
    "パニック": "Panic",
    "discomfort": "Discomfort",
    "不快": "Discomfort",
    "ストレス": "Discomfort",
    # 汎用の高/中/低スケール。CLAUDE.md の緊急提示順（LifeThreatening → Panic →
    # Discomfort）に沿って対応づける。LLM が段階表現で
    # 出力した場合に安全側の正規値へ寄せる。ここに無い値は補正せず警告する。
    "高": "LifeThreatening",
    "中": "Panic",
    "低": "Discomfort",
    "high": "LifeThreatening",
    "medium": "Panic",
    "low": "Discomfort",
}


def normalize_risk_level(value: str) -> str:
    """riskLevel の別名を正規値に補正する。既に正規値ならそのまま返す。"""
    if not isinstance(value, str):
        return value
    if value in ENUM_VALUES["riskLevel"]:
        return value
    return RISK_LEVEL_ALIASES.get(value.strip().lower(), value)

# =============================================================================
# プロパティ名変換 (snake_case → camelCase)
# =============================================================================

# ServiceProvider レガシー名 → 正式名
LEGACY_PROPERTY_MAP = {
    "office_name": "name",
    "corp_name": "corporateName",
    "service_type": "serviceType",
    "office_number": "wamnetId",
    "closed_days": "closedDays",
    "hours_weekday": "hoursWeekday",
    "updated_at": "updatedAt",
}

# 汎用 snake_case → camelCase 変換で既知のマッピング
KNOWN_PROPERTY_MAP = {
    "blood_type": "bloodType",
    "risk_level": "riskLevel",
    "next_renewal_date": "nextRenewalDate",
    "client_id": "clientId",
    "display_code": "displayCode",
    "diagnosed_date": "diagnosedDate",
    "diagnosis_date": "diagnosisDate",
    "start_date": "startDate",
    "end_date": "endDate",
    "issued_date": "issuedDate",
    "discovered_date": "discoveredDate",
    "current_status": "currentStatus",
    "case_number": "caseNumber",
    "trigger_tag": "triggerTag",
    "next_action": "nextAction",
    "file_path": "filePath",
    "mime_type": "mimeType",
    "text_embedding": "textEmbedding",
    "summary_embedding": "summaryEmbedding",
    "target_type": "targetType",
    "target_name": "targetName",
    "client_name": "clientName",
    "user_name": "userName",
    "feedback_id": "feedbackId",
    "wamnet_id": "wamnetId",
    "corporate_name": "corporateName",
    "recipient_condition": "recipientCondition",
    "money_management": "moneyManagement",
}

# camelCase として正しいプロパティ名のセット (変換不要)
_CAMEL_CASE_PATTERN = re.compile(r"^[a-z][a-zA-Z0-9]*$")
_SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")


def _snake_to_camel(name: str) -> str:
    """snake_case を camelCase に汎用変換する"""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def normalize_property_name(name: str) -> str:
    """
    プロパティ名を camelCase に正規化する。

    1. LEGACY_PROPERTY_MAP / KNOWN_PROPERTY_MAP に完全一致 → マッピング値を返す
    2. snake_case パターンに一致 → camelCase に自動変換
    3. それ以外 → そのまま返す (name, dob 等の単一語)
    """
    # 既知のマッピング (完全一致)
    if name in LEGACY_PROPERTY_MAP:
        return LEGACY_PROPERTY_MAP[name]
    if name in KNOWN_PROPERTY_MAP:
        return KNOWN_PROPERTY_MAP[name]

    # 既に camelCase or 単一語 → そのまま
    if _CAMEL_CASE_PATTERN.match(name) or not _SNAKE_CASE_PATTERN.match(name):
        return name

    # snake_case → camelCase 汎用変換
    converted = _snake_to_camel(name)
    _log(f"プロパティ名を自動変換: {name} → {converted}")
    return converted


def normalize_properties(props: dict, label: str | None = None) -> dict:
    """
    プロパティ辞書のキーを camelCase に正規化する。
    値が変わることはない。キーの重複が発生した場合は新しい値で上書き。
    """
    normalized = {}
    for key, value in props.items():
        new_key = normalize_property_name(key)
        if new_key != key:
            _log(f"[{label or '?'}] プロパティ変換: {key} → {new_key}")
        normalized[new_key] = value
    return normalized


# =============================================================================
# バリデーション関数
# =============================================================================

def validate_node_label(label: str) -> tuple[bool, str]:
    """
    ノードラベルが正式なラベル一覧に含まれるか検証する。

    Returns:
        (is_valid, message)
    """
    if label in VALID_NODE_LABELS:
        return True, ""
    return False, f"未知のノードラベル: '{label}'. 正式なラベル一覧に存在しません。"


def validate_relationship_type(rel_type: str) -> tuple[bool, str, str]:
    """
    リレーションタイプを検証し、廃止名は正式名に自動修正する。

    Returns:
        (is_valid, message, corrected_type)
    """
    if rel_type in VALID_RELATIONSHIP_TYPES:
        return True, "", rel_type

    if rel_type in DEPRECATED_RELATIONSHIPS:
        corrected = DEPRECATED_RELATIONSHIPS[rel_type]
        _log(f"廃止リレーションを自動修正: {rel_type} → {corrected}")
        return True, f"廃止リレーション '{rel_type}' を '{corrected}' に修正", corrected

    return False, f"未知のリレーションタイプ: '{rel_type}'", rel_type


def validate_enum_value(prop_name: str, value: str) -> tuple[bool, str]:
    """
    列挙値プロパティの値を検証する。

    Returns:
        (is_valid, message)
    """
    if prop_name not in ENUM_VALUES:
        return True, ""

    valid_values = ENUM_VALUES[prop_name]
    if value in valid_values:
        return True, ""

    return False, (
        f"'{prop_name}' の値 '{value}' は不正です。"
        f" 有効な値: {sorted(valid_values)}"
    )


def validate_and_normalize_graph(extracted_graph: dict) -> tuple[dict, list[str]]:
    """
    LLM が生成したグラフ構造全体を検証・正規化する。

    - ノードラベルの検証
    - プロパティ名の camelCase 変換
    - リレーションタイプの検証 (廃止名の自動修正含む)
    - 列挙値の検証

    Returns:
        (normalized_graph, warnings)
        warnings にはバリデーション警告メッセージのリストが入る。
        致命的エラー (未知のラベル等) も warnings に含まれるが、処理は続行する。
    """
    warnings = []
    normalized = {
        "nodes": [],
        "relationships": [],
    }

    # --- ノードの検証・正規化 ---
    for node in extracted_graph.get("nodes", []):
        label = node.get("label", "")
        props = node.get("properties", {})

        # ラベル検証
        is_valid, msg = validate_node_label(label)
        if not is_valid:
            warnings.append(msg)

        # プロパティ名の camelCase 正規化
        normalized_props = normalize_properties(props, label)

        # 安全クリティカルな riskLevel は別名を正規値へ補正してから検証する
        if isinstance(normalized_props.get("riskLevel"), str):
            corrected_risk = normalize_risk_level(normalized_props["riskLevel"])
            if corrected_risk != normalized_props["riskLevel"]:
                _log(f"riskLevel を補正: {normalized_props['riskLevel']} → {corrected_risk}")
                normalized_props["riskLevel"] = corrected_risk

        # 列挙値の検証
        for prop_name, value in normalized_props.items():
            if isinstance(value, str):
                is_valid, msg = validate_enum_value(prop_name, value)
                if not is_valid:
                    warnings.append(msg)

                # ラベル限定の列挙値（Review.domain / Review.source）
                is_valid, msg = validate_label_scoped_enum(label, prop_name, value)
                if not is_valid:
                    warnings.append(msg)

        # 必須プロパティ（警告）と事実時間軸の規則（違反は書き込み不可）
        warnings.extend(validate_required_properties(label, normalized_props))
        warnings.extend(validate_fact_time(label, normalized_props))

        normalized["nodes"].append({
            **node,
            "properties": normalized_props,
        })

    # --- リレーションシップの検証・正規化 ---
    for rel in extracted_graph.get("relationships", []):
        rel_type = rel.get("type", "")

        # リレーションタイプの検証 (廃止名の自動修正)
        is_valid, msg, corrected = validate_relationship_type(rel_type)
        if msg:
            warnings.append(msg)

        # リレーションプロパティの camelCase 正規化
        rel_props = rel.get("properties", {})
        normalized_props = normalize_properties(rel_props, f"rel:{corrected}")

        # リレーションのプロパティ規則（HAS_KEY_PERSON の status 2値・Inactive の endDate）
        rel_errors, rel_warnings = validate_relationship_properties(corrected, normalized_props)
        warnings.extend(rel_errors)
        warnings.extend(rel_warnings)

        normalized["relationships"].append({
            **rel,
            "type": corrected,
            "properties": normalized_props,
        })

    if warnings:
        for w in warnings:
            _log(w, "WARN")

    return normalized, warnings

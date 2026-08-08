"""Clients router — client list, detail, emergency info, and support logs."""

from __future__ import annotations

import functools
import logging

from fastapi import APIRouter, HTTPException, Query

from app.lib.db_operations import create_audit_log, run_query
from app.lib.utils import calculate_age
from app.schemas.client import (
    CarePreference,
    ClientCreate,
    ClientDeleteResult,
    ClientDetail,
    ClientSummary,
    ClientUpdate,
    EmergencyInfo,
    KeyPerson,
    NgAction,
    SupportLogEntry,
)

logger = logging.getLogger(__name__)

_KANA_ROW_MAP = {
    "あ": "あいうえお",
    "か": "かきくけこがぎぐげご",
    "さ": "さしすせそざじずぜぞ",
    "た": "たちつてとだぢづでど",
    "な": "なにぬねの",
    "は": "はひふへほばびぶべぼぱぴぷぺぽ",
    "ま": "まみむめも",
    "や": "やゆよ",
    "ら": "らりるれろ",
    "わ": "わをん",
}

# ---------------------------------------------------------------------------
# アルファベット → 日本語読み（ひらがな）マッピング
# 例: M → えむ（あ行）、K → けー（か行）
# ---------------------------------------------------------------------------
_ALPHA_TO_KANA: dict[str, str] = {
    "A": "えー",    "B": "びー",    "C": "しー",    "D": "でぃー",
    "E": "いー",    "F": "えふ",    "G": "じー",    "H": "えいち",
    "I": "あい",    "J": "じぇー",  "K": "けー",    "L": "える",
    "M": "えむ",    "N": "えぬ",    "O": "おー",    "P": "ぴー",
    "Q": "きゅー",  "R": "あーる",  "S": "えす",    "T": "てぃー",
    "U": "ゆー",    "V": "ぶい",    "W": "だぶりゅー",
    "X": "えっくす", "Y": "わい",   "Z": "ぜっと",
}


def _name_to_kana(name: str) -> str:
    """漢字名・アルファベット名をひらがなに変換。

    - イニシャル表記（例: "M・K"）→ 各文字の日本語読みに変換（"えむ・けー"）
    - 漢字名 → pykakasi で変換
    """
    import re

    # 名前の先頭文字がアルファベットならイニシャル表記として処理
    if name and name[0].isascii() and name[0].isalpha():
        parts: list[str] = []
        for ch in name:
            upper = ch.upper()
            if upper in _ALPHA_TO_KANA:
                parts.append(_ALPHA_TO_KANA[upper])
            else:
                # 区切り文字（・、-、スペース等）はそのまま
                parts.append(ch)
        return "".join(parts)

    # 漢字名は pykakasi で変換（キャッシュ済みインスタンスを使用）
    kks = _get_kakasi()
    result = kks.convert(name)
    return "".join(item["hira"] for item in result)


@functools.lru_cache(maxsize=1)
def _get_kakasi():
    """pykakasi インスタンスをキャッシュして再利用する。"""
    from pykakasi import kakasi as Kakasi
    return Kakasi()


def _is_alpha_name(name: str) -> bool:
    """名前がアルファベット（イニシャル等）で始まるかを判定。"""
    return bool(name) and name[0].isascii() and name[0].isalpha()


def _matches_kana_row(kana: str, row_prefix: str) -> bool:
    """かな行の先頭文字でフィルタ（あ行→あいうえお のいずれかで始まるか）。

    row_prefix が "ABC" の場合は、元の名前がアルファベット始まりかで判定する
    （呼び出し元で別途処理）。
    """
    chars = _KANA_ROW_MAP.get(row_prefix, row_prefix)
    return any(kana.startswith(c) for c in chars)

# ---------------------------------------------------------------------------
# パース用ヘルパー関数（get_client / get_emergency の重複排除）
# ---------------------------------------------------------------------------

_RISK_ORDER = {"LifeThreatening": 1, "Panic": 2}


def _parse_ng_actions(raw: list[dict]) -> list[NgAction]:
    """NgAction の生データをパースし、riskLevel 順にソートして返す。"""
    filtered = [n for n in raw if n.get("action")]
    filtered.sort(key=lambda n: _RISK_ORDER.get(n.get("riskLevel", ""), 3))
    return [
        NgAction(
            action=n["action"],
            reason=n.get("reason"),
            risk_level=n.get("riskLevel") or "Discomfort",
        )
        for n in filtered
    ]


def _parse_care_preferences(raw: list[dict]) -> list[CarePreference]:
    """CarePreference の生データをパースして返す。"""
    return [
        CarePreference(
            category=cp["category"],
            instruction=cp["instruction"],
            priority=cp.get("priority"),
        )
        for cp in raw
        if cp.get("category")
    ]


def _parse_key_persons(raw: list[dict]) -> list[KeyPerson]:
    """KeyPerson の生データをパースし、rank 順にソートして返す。"""
    filtered = [kp for kp in raw if kp.get("name")]
    filtered.sort(key=lambda kp: kp.get("rank") or 999)
    return [
        KeyPerson(
            name=kp["name"],
            relationship=kp.get("relationship"),
            phone=kp.get("phone"),
            rank=kp.get("rank"),
        )
        for kp in filtered
    ]


router = APIRouter(prefix="/api/clients", tags=["clients"])


# ---------------------------------------------------------------------------
# GET /api/clients
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ClientSummary])
def list_clients(
    kana_prefix: str | None = Query(default=None, description="かな行頭文字でフィルタ（例: あ）"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ClientSummary]:
    """クライアント一覧を返す。kana_prefix が指定されれば kana フィールドで前方一致フィルタ。"""
    try:
        rows = run_query(
            """
            MATCH (c:Client)
            WHERE c.archived IS NULL OR c.archived = false
            OPTIONAL MATCH (c)-[:HAS_CONDITION]->(cond:Condition)
            RETURN c.name AS name,
                   c.dob AS dob,
                   c.bloodType AS blood_type,
                   c.kana AS kana,
                   collect(DISTINCT cond.name) AS conditions
            ORDER BY c.name
            """
        )

        summaries: list[ClientSummary] = []
        for row in rows:
            name = row["name"]
            # kana プロパティがなければ自動変換（アルファベット対応含む）
            kana: str | None = row.get("kana") or _name_to_kana(name)

            # フィルタ処理
            if kana_prefix:
                if kana_prefix == "ABC":
                    # 英字フィルタ: アルファベットで始まる名前のみ表示
                    if not _is_alpha_name(name):
                        continue
                else:
                    # かな行フィルタ: かな読みの先頭文字で判定
                    if not _matches_kana_row(kana, kana_prefix):
                        continue

            dob = row.get("dob")
            age = calculate_age(dob) if dob else None
            conditions = [c for c in (row.get("conditions") or []) if c]
            summaries.append(
                ClientSummary(
                    name=row["name"],
                    dob=str(dob) if dob else None,
                    age=age,
                    blood_type=row.get("blood_type"),
                    conditions=conditions,
                )
            )
        return summaries[skip : skip + limit]

    except Exception as exc:
        logger.error("list_clients failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /api/clients/{name}
# ---------------------------------------------------------------------------


@router.get("/{name}", response_model=ClientDetail)
def get_client(name: str) -> ClientDetail:
    """クライアントの詳細プロフィールを返す（1回の Cypher で全関連ノードを取得）。"""
    try:
        rows = run_query(
            """
            MATCH (c:Client {name: $name})
            OPTIONAL MATCH (c)-[:HAS_CONDITION]->(cond:Condition)
            OPTIONAL MATCH (c)-[:MUST_AVOID]->(ng:NgAction)
            OPTIONAL MATCH (c)-[:REQUIRES]->(cp:CarePreference)
            OPTIONAL MATCH (c)-[kpRel:HAS_KEY_PERSON]->(kp:KeyPerson)
            OPTIONAL MATCH (c)-[:HAS_CERTIFICATE]->(cert:Certificate)
            OPTIONAL MATCH (c)-[:TREATED_AT]->(h:Hospital)
            OPTIONAL MATCH (c)-[:HAS_LEGAL_REP]->(g:Guardian)
            RETURN c.name AS name,
                   c.dob AS dob,
                   c.bloodType AS blood_type,
                   collect(DISTINCT {name: cond.name, diagnosedDate: cond.diagnosedDate}) AS conditions,
                   collect(DISTINCT {action: ng.action, reason: ng.reason, riskLevel: ng.riskLevel}) AS ng_actions,
                   collect(DISTINCT {category: cp.category, instruction: cp.instruction, priority: cp.priority}) AS care_preferences,
                   collect(DISTINCT {name: kp.name, relationship: kp.relationship, phone: kp.phone, rank: kpRel.rank}) AS key_persons,
                   collect(DISTINCT cert {.*}) AS certificates,
                   head(collect(DISTINCT h {.*})) AS hospital,
                   head(collect(DISTINCT g {.*})) AS guardian
            """,
            {"name": name},
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"Client '{name}' not found")

        row = rows[0]
        dob = row.get("dob")
        age = calculate_age(dob) if dob else None

        # null エントリを除去（OPTIONAL MATCH で null プロパティが collect される）
        conditions = [c for c in (row.get("conditions") or []) if c.get("name")]

        ng_actions = _parse_ng_actions(row.get("ng_actions") or [])
        care_preferences = _parse_care_preferences(row.get("care_preferences") or [])
        key_persons = _parse_key_persons(row.get("key_persons") or [])

        certificates = [c for c in (row.get("certificates") or []) if c]
        hospital = row.get("hospital")
        guardian = row.get("guardian")

        return ClientDetail(
            name=row["name"],
            dob=str(dob) if dob else None,
            age=age,
            blood_type=row.get("blood_type"),
            conditions=conditions,
            ng_actions=ng_actions,
            care_preferences=care_preferences,
            key_persons=key_persons,
            certificates=certificates,
            hospital=hospital,
            guardian=guardian,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_client failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /api/clients/{name}/emergency
# ---------------------------------------------------------------------------


@router.get("/{name}/emergency", response_model=EmergencyInfo)
def get_emergency(name: str) -> EmergencyInfo:
    """緊急時情報を返す（1回の Cypher で取得、NgAction 優先度順、Safety First）。"""
    try:
        rows = run_query(
            """
            MATCH (c:Client {name: $name})
            OPTIONAL MATCH (c)-[:MUST_AVOID]->(ng:NgAction)
            OPTIONAL MATCH (c)-[:REQUIRES]->(cp:CarePreference)
            OPTIONAL MATCH (c)-[kpRel:HAS_KEY_PERSON]->(kp:KeyPerson)
            OPTIONAL MATCH (c)-[:TREATED_AT]->(h:Hospital)
            OPTIONAL MATCH (c)-[:HAS_LEGAL_REP]->(g:Guardian)
            RETURN c.name AS name,
                   collect(DISTINCT {action: ng.action, reason: ng.reason, riskLevel: ng.riskLevel}) AS ng_actions,
                   collect(DISTINCT {category: cp.category, instruction: cp.instruction, priority: cp.priority}) AS care_preferences,
                   collect(DISTINCT {name: kp.name, relationship: kp.relationship, phone: kp.phone, rank: kpRel.rank}) AS key_persons,
                   head(collect(DISTINCT h {.*})) AS hospital,
                   head(collect(DISTINCT g {.*})) AS guardian
            """,
            {"name": name},
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"Client '{name}' not found")

        row = rows[0]

        ng_actions = _parse_ng_actions(row.get("ng_actions") or [])
        care_preferences = _parse_care_preferences(row.get("care_preferences") or [])
        key_persons = _parse_key_persons(row.get("key_persons") or [])

        return EmergencyInfo(
            client_name=name,
            ng_actions=ng_actions,
            care_preferences=care_preferences,
            key_persons=key_persons,
            hospital=row.get("hospital"),
            guardian=row.get("guardian"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_emergency failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /api/clients/{name}/logs
# ---------------------------------------------------------------------------


@router.get("/{name}/logs", response_model=list[SupportLogEntry])
def get_logs(name: str, limit: int = Query(default=50, ge=1, le=200)) -> list[SupportLogEntry]:
    """クライアントの支援記録を返す（デフォルト 50 件）。"""
    try:
        exists = run_query("MATCH (c:Client {name: $name}) RETURN c.name AS n LIMIT 1", {"name": name})
        if not exists:
            raise HTTPException(status_code=404, detail=f"Client '{name}' not found")

        rows = run_query(
            """
            MATCH (s:Supporter)-[:LOGGED]->(sl:SupportLog)-[:ABOUT]->(c:Client {name: $name})
            RETURN sl.date AS date,
                   sl.situation AS situation,
                   sl.action AS action,
                   sl.effectiveness AS effectiveness,
                   sl.note AS note,
                   s.name AS supporter_name
            ORDER BY sl.date DESC
            LIMIT $limit
            """,
            {"name": name, "limit": limit},
        )

        return [
            SupportLogEntry(
                date=str(r.get("date", "")) or None,
                situation=r.get("situation"),
                action=r.get("action"),
                effectiveness=r.get("effectiveness"),
                note=r.get("note"),
                supporter_name=r.get("supporter_name"),
            )
            for r in rows
        ]

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_logs failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# POST /api/clients
# ---------------------------------------------------------------------------


@router.post("", response_model=ClientDetail, status_code=201)
def create_client(data: ClientCreate) -> ClientDetail:
    """新規クライアントを作成する。conditions が指定されれば Condition ノードも MERGE する。"""
    try:
        # MERGE で冪等にクライアントノードを作成
        params: dict = {"name": data.name}
        set_clauses: list[str] = []
        if data.dob is not None:
            set_clauses.append("c.dob = $dob")
            params["dob"] = data.dob
        if data.blood_type is not None:
            set_clauses.append("c.bloodType = $blood_type")
            params["blood_type"] = data.blood_type

        set_part = f"SET {', '.join(set_clauses)}" if set_clauses else ""
        run_query(
            f"""
            MERGE (c:Client {{name: $name}})
            {set_part}
            RETURN c.name AS name
            """,
            params,
        )

        # Condition ノードの MERGE とリレーション作成
        for cond_name in data.conditions:
            run_query(
                """
                MATCH (c:Client {name: $name})
                MERGE (cond:Condition {name: $cond_name})
                MERGE (c)-[:HAS_CONDITION]->(cond)
                """,
                {"name": data.name, "cond_name": cond_name},
            )

        # 監査ログの記録
        create_audit_log(
            user_name="api",
            action="CREATE",
            target_type="Client",
            target_name=data.name,
            details=f"Created client '{data.name}' via API",
            client_name=data.name,
        )

        return get_client(data.name)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("create_client failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# PUT /api/clients/{name}
# ---------------------------------------------------------------------------


@router.put("/{name}", response_model=ClientDetail)
def update_client(name: str, data: ClientUpdate) -> ClientDetail:
    """クライアント情報を更新する（non-None フィールドのみ）。"""
    try:
        # 存在チェック
        exists = run_query(
            "MATCH (c:Client {name: $name}) RETURN c.name AS n LIMIT 1",
            {"name": name},
        )
        if not exists:
            raise HTTPException(status_code=404, detail=f"Client '{name}' not found")

        # 更新対象フィールドを動的に構築（全フィールド None なら 400）
        params: dict = {"name": name}
        set_clauses: list[str] = []
        if data.dob is not None:
            set_clauses.append("c.dob = $dob")
            params["dob"] = data.dob
        if data.blood_type is not None:
            set_clauses.append("c.bloodType = $blood_type")
            params["blood_type"] = data.blood_type

        if not set_clauses:
            raise HTTPException(status_code=400, detail="更新するフィールドがありません。")

        if set_clauses:
            run_query(
                f"""
                MATCH (c:Client {{name: $name}})
                SET {', '.join(set_clauses)}
                RETURN c.name AS name
                """,
                params,
            )

        # 監査ログの記録
        updated_fields = [k for k, v in data.model_dump().items() if v is not None]
        create_audit_log(
            user_name="api",
            action="UPDATE",
            target_type="Client",
            target_name=name,
            details=f"Updated fields: {', '.join(updated_fields) or 'none'}",
            client_name=name,
        )

        return get_client(name)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("update_client failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# DELETE /api/clients/{name}
# ---------------------------------------------------------------------------


@router.delete("/{name}", response_model=ClientDeleteResult)
def delete_client(name: str) -> ClientDeleteResult:
    """クライアントを論理削除（アーカイブ）する。実データは削除しない。"""
    try:
        # 存在チェック
        exists = run_query(
            "MATCH (c:Client {name: $name}) RETURN c.name AS n LIMIT 1",
            {"name": name},
        )
        if not exists:
            raise HTTPException(status_code=404, detail=f"Client '{name}' not found")

        # 論理削除: archived フラグと日時を設定
        run_query(
            """
            MATCH (c:Client {name: $name})
            SET c.archived = true, c.archivedAt = datetime()
            RETURN c.name AS name
            """,
            {"name": name},
        )

        # 監査ログの記録
        create_audit_log(
            user_name="api",
            action="ARCHIVE",
            target_type="Client",
            target_name=name,
            details=f"Archived (soft-deleted) client '{name}' via API",
            client_name=name,
        )

        return ClientDeleteResult(
            status="archived",
            client_name=name,
            deleted_count=1,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("delete_client failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

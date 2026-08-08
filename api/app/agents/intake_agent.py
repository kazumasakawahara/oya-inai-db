"""Conversational intake agent -- 7-pillar guided information gathering.

Manages a multi-turn dialogue to collect client information following
the 7-pillar manifesto, then extracts and registers to Neo4j.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.agents.gemini_agent import extract_from_text, parse_json_from_response
from app.agents.validator import validate_schema
from app.config import settings
from app.lib.db_operations import register_to_database

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"

# ---------------------------------------------------------------------------
# 7-Pillar intake phases
# ---------------------------------------------------------------------------

INTAKE_PHASES = [
    {
        "id": 1,
        "pillar": "本人性（Identity）",
        "priority": "最優先",
        "prompt": (
            "まず基本情報を教えてください。"
            "お名前（フルネーム）、生年月日、血液型をお聞かせください。"
        ),
        "required_labels": ["Client"],
        "required_info": "氏名（フルネーム）、生年月日、血液型",
    },
    {
        "id": 2,
        "pillar": "ケアの暗黙知（Care Instructions）",
        "priority": "最優先",
        "prompt": (
            "次に、支援で最も大切な情報です。\n"
            "1. 絶対にしてはいけないこと（禁忌事項）はありますか？\n"
            "2. パニックや不安になった時に落ち着く方法はありますか？\n"
            "3. 食事・入浴・服薬で気をつけることはありますか？"
        ),
        "required_labels": ["NgAction", "CarePreference"],
        "required_info": "禁忌事項（してはいけないこと）、パニック時の対処法、日常ケアの注意点",
    },
    {
        "id": 3,
        "pillar": "安全ネット（Safety Net）",
        "priority": "最優先",
        "prompt": (
            "緊急時の連絡先を教えてください。\n"
            "1. ご家族など緊急時に連絡する方（お名前・続柄・電話番号）\n"
            "2. かかりつけの病院・クリニック（名前・電話番号）"
        ),
        "required_labels": ["KeyPerson", "Hospital"],
        "required_info": "緊急連絡先（氏名・続柄・電話番号）、かかりつけ病院（名前・電話番号）",
    },
    {
        "id": 4,
        "pillar": "法的基盤（Legal）",
        "priority": "高",
        "prompt": (
            "法的な情報について教えてください。\n"
            "1. 障害者手帳や受給者証をお持ちですか？（種類と有効期限）\n"
            "2. 成年後見人はいらっしゃいますか？"
        ),
        "required_labels": ["Certificate", "Guardian"],
        "required_info": "手帳・受給者証の種類と有効期限、成年後見人の有無",
    },
    {
        "id": 5,
        "pillar": "親の機能移行（Parental Transition）",
        "priority": "通常",
        "prompt": (
            "ご家族の状況を教えてください。\n"
            "1. 主な介護者（親御さん等）の健康状態\n"
            "2. 親御さんが現在担っている役割（通院付き添い、金銭管理等）"
        ),
        "required_labels": [],
        "required_info": "主介護者の健康状態、担っている役割",
    },
    {
        "id": 6,
        "pillar": "金銭的安全（Financial Safety）",
        "priority": "通常",
        "prompt": (
            "金銭管理について教えてください。\n"
            "1. お金の管理は誰がしていますか？\n"
            "2. 金銭的なトラブルや心配はありますか？"
        ),
        "required_labels": [],
        "required_info": "金銭管理者、金銭トラブルの有無",
    },
    {
        "id": 7,
        "pillar": "多機関連携（Multi-Agency）",
        "priority": "通常",
        "prompt": (
            "利用しているサービスについて教えてください。\n"
            "1. 現在利用している福祉サービス（事業所名等）\n"
            "2. 他に関わっている支援機関はありますか？"
        ),
        "required_labels": [],
        "required_info": "利用中の福祉サービス、関わっている支援機関",
    },
]

# Phase evaluation prompt template
PHASE_EVAL_PROMPT = (
    "以下のユーザーの回答が、{pillar}の情報として十分かどうか判断してください。\n"
    "必要な情報: {required_info}\n"
    "ユーザーの回答: {response}\n\n"
    '十分であれば "SUFFICIENT" とだけ回答してください。'
    "不足があれば具体的に何が不足しているか日本語で1〜2文で回答してください。"
)

# Confirmation keywords to trigger final registration
_CONFIRM_PATTERNS = re.compile(
    r"(登録して|登録する|OK|はい|お願い|確定|登録お願い)", re.IGNORECASE
)

# Skip keywords to move to next phase without complete info
_SKIP_PATTERNS = re.compile(
    r"(スキップ|飛ばして|わからない|不明|なし|ない|次へ)", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Intake Session
# ---------------------------------------------------------------------------


class IntakeSession:
    """Manages state for a single intake conversation."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.current_phase: int = 0  # 0 = not started yet
        self.collected_text: list[str] = []  # All user responses accumulated
        self.phase_responses: dict[int, list[str]] = {}  # Per-phase responses
        self.extracted_graph: dict | None = None
        self.is_complete: bool = False
        self._awaiting_confirmation: bool = False
        self._last_active: float = _time.time()

    # -- Phase navigation --------------------------------------------------

    def get_current_prompt(self) -> tuple[int, str, str]:
        """Return ``(phase_number, pillar_name, prompt_text)`` for the active phase."""
        if self.current_phase < 1 or self.current_phase > len(INTAKE_PHASES):
            phase = INTAKE_PHASES[0]
        else:
            phase = INTAKE_PHASES[self.current_phase - 1]
        return phase["id"], phase["pillar"], phase["prompt"]

    def add_response(self, text: str) -> None:
        """Record a user response for the current phase."""
        self.collected_text.append(text)
        phase = self.current_phase
        if phase not in self.phase_responses:
            self.phase_responses[phase] = []
        self.phase_responses[phase].append(text)

    def advance_phase(self) -> bool:
        """Move to the next phase. Returns ``False`` when all phases are done."""
        if self.current_phase >= len(INTAKE_PHASES):
            return False
        self.current_phase += 1
        return self.current_phase <= len(INTAKE_PHASES)

    def get_full_narrative(self) -> str:
        """Combine all collected responses into a single narrative text."""
        parts: list[str] = []
        for phase_id in sorted(self.phase_responses.keys()):
            phase_def = INTAKE_PHASES[phase_id - 1] if 1 <= phase_id <= len(INTAKE_PHASES) else None
            if phase_def:
                parts.append(f"【{phase_def['pillar']}】")
            parts.extend(self.phase_responses[phase_id])
            parts.append("")
        return "\n".join(parts)

    def get_progress(self) -> dict:
        """Return progress info for the frontend."""
        total = len(INTAKE_PHASES)
        current = min(self.current_phase, total)
        phase_def = INTAKE_PHASES[current - 1] if 1 <= current <= total else None
        return {
            "phase": current,
            "total": total,
            "pillar": phase_def["pillar"] if phase_def else "",
            "status": "active" if current <= total else "complete",
        }


# ---------------------------------------------------------------------------
# Session storage (in-process; sufficient for single-server deployment)
# ---------------------------------------------------------------------------

import time as _time

_sessions: dict[str, IntakeSession] = {}
_SESSION_TTL_SEC = 1800  # 30分


def get_or_create_session(session_id: str) -> IntakeSession:
    """Return an existing session or create a new one. Expired sessions are cleaned up."""
    _cleanup_expired_sessions()
    if session_id not in _sessions:
        _sessions[session_id] = IntakeSession(session_id)
        logger.info("Created new intake session: %s", session_id)
    session = _sessions[session_id]
    session._last_active = _time.time()
    return session


def cleanup_session(session_id: str) -> None:
    """Remove a session from memory (called on completion or disconnect)."""
    _sessions.pop(session_id, None)


def _cleanup_expired_sessions() -> None:
    """Remove sessions older than TTL."""
    now = _time.time()
    expired = [sid for sid, s in _sessions.items() if now - getattr(s, "_last_active", 0) > _SESSION_TTL_SEC]
    for sid in expired:
        logger.info("Expired intake session: %s", sid)
        _sessions.pop(sid, None)


# ---------------------------------------------------------------------------
# LLM-based phase evaluation
# ---------------------------------------------------------------------------


async def _evaluate_phase_response(pillar: str, required_info: str, response: str) -> str:
    """Use Gemini to decide whether the user's response is sufficient.

    Returns ``"SUFFICIENT"`` or a follow-up question in Japanese.
    """
    import google.generativeai as genai

    prompt = PHASE_EVAL_PROMPT.format(
        pillar=pillar,
        required_info=required_info,
        response=response,
    )
    try:
        genai.configure(api_key=settings.gemini_api_key or settings.google_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        result = model.generate_content(
            [{"role": "user", "parts": [prompt]}],
            generation_config={"temperature": 0},
        )
        return result.text.strip()
    except Exception as e:
        logger.warning("Phase evaluation failed, treating as sufficient: %s", e)
        return "SUFFICIENT"


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------


async def handle_intake_message(session_id: str, user_text: str) -> dict:
    """Process an intake message and return response + metadata.

    Returns a dict with keys:
        - ``response``: AI's next question or confirmation text
        - ``progress``: dict with phase info for the frontend
        - ``preview``: extracted graph dict (or ``None``)
        - ``complete``: ``True`` when all phases done and registered
        - ``registered_count``: count of registered nodes (when complete)
    """
    session = get_or_create_session(session_id)

    # -- Phase 0: first contact, send welcome + phase-1 question -----------
    if session.current_phase == 0:
        session.current_phase = 1
        _, pillar, prompt = session.get_current_prompt()
        welcome = (
            "初回面接（インテーク）を始めます。\n"
            "7つの柱に沿って、利用者さまの情報を聞き取らせていただきます。\n"
            "わからない項目は「スキップ」と言っていただければ次に進みます。\n\n"
            f"--- 第1の柱: {pillar} ---\n\n{prompt}"
        )
        return {
            "response": welcome,
            "progress": session.get_progress(),
            "preview": None,
            "complete": False,
            "registered_count": 0,
        }

    # -- Awaiting final confirmation ---------------------------------------
    if session._awaiting_confirmation:
        if _CONFIRM_PATTERNS.search(user_text):
            return await _do_registration(session)
        else:
            return {
                "response": (
                    "登録を進めてよろしいですか？「登録して」または「はい」でデータベースに保存します。\n"
                    "修正がある場合はその内容をお伝えください。"
                ),
                "progress": session.get_progress(),
                "preview": session.extracted_graph,
                "complete": False,
                "registered_count": 0,
            }

    # -- Record user response ----------------------------------------------
    session.add_response(user_text)

    # -- Check for skip request -------------------------------------------
    if _SKIP_PATTERNS.search(user_text):
        return await _advance_or_finish(session, skipped=True)

    # -- Evaluate whether current phase has enough info --------------------
    phase_def = INTAKE_PHASES[session.current_phase - 1]
    combined_response = "\n".join(session.phase_responses.get(session.current_phase, []))
    evaluation = await _evaluate_phase_response(
        pillar=phase_def["pillar"],
        required_info=phase_def["required_info"],
        response=combined_response,
    )

    if evaluation.startswith("SUFFICIENT"):
        return await _advance_or_finish(session, skipped=False)

    # Not enough info -- ask follow-up
    return {
        "response": f"ありがとうございます。もう少し教えてください。\n{evaluation}",
        "progress": session.get_progress(),
        "preview": None,
        "complete": False,
        "registered_count": 0,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _advance_or_finish(session: IntakeSession, *, skipped: bool) -> dict:
    """Advance to the next phase, do intermediate extraction, or finish."""
    prev_phase = session.current_phase
    preview = None

    # After phase 3 (the last safety-critical phase), do intermediate extraction
    if prev_phase == 3 and not skipped:
        preview = await _extract_preview(session)

    has_next = session.advance_phase()

    if has_next and session.current_phase <= len(INTAKE_PHASES):
        _, pillar, prompt = session.get_current_prompt()
        phase_def = INTAKE_PHASES[session.current_phase - 1]
        skip_note = "（スキップしました）\n\n" if skipped else ""
        response = (
            f"{skip_note}"
            f"--- 第{session.current_phase}の柱: {pillar} "
            f"[{phase_def['priority']}] ---\n\n{prompt}"
        )
        return {
            "response": response,
            "progress": session.get_progress(),
            "preview": preview,
            "complete": False,
            "registered_count": 0,
        }

    # All phases done -- extract full narrative and ask for confirmation
    return await _prepare_final_confirmation(session)


async def _extract_preview(session: IntakeSession) -> dict | None:
    """Run extraction on the narrative so far and return a preview."""
    narrative = session.get_full_narrative()
    try:
        graph = await extract_from_text(narrative)
        if graph:
            validation = validate_schema(graph)
            if not validation.is_valid:
                logger.warning("Intermediate extraction validation errors: %s", validation.errors)
            return graph
    except Exception as e:
        logger.warning("Intermediate extraction failed: %s", e)
    return None


async def _prepare_final_confirmation(session: IntakeSession) -> dict:
    """Extract the full narrative and present a confirmation preview."""
    narrative = session.get_full_narrative()
    graph = await extract_from_text(narrative)

    if not graph:
        return {
            "response": (
                "聞き取りが完了しましたが、情報の構造化に失敗しました。\n"
                "もう一度最初から情報を入力していただくか、サポートにお問い合わせください。"
            ),
            "progress": session.get_progress(),
            "preview": None,
            "complete": False,
            "registered_count": 0,
        }

    validation = validate_schema(graph)
    session.extracted_graph = graph
    session._awaiting_confirmation = True

    # Build a human-readable summary
    nodes = graph.get("nodes", [])
    summary_lines = ["聞き取りが完了しました。以下の情報を登録します：\n"]
    for node in nodes:
        label = node.get("label", "?")
        props = node.get("properties", {})
        name = props.get("name", props.get("action", props.get("type", "")))
        summary_lines.append(f"  - {label}: {name}")

    if validation.warnings:
        summary_lines.append(f"\n注意: {', '.join(validation.warnings)}")
    if validation.errors:
        summary_lines.append(f"\nエラー: {', '.join(validation.errors)}")

    summary_lines.append('\n「登録して」と言っていただければデータベースに保存します。')

    return {
        "response": "\n".join(summary_lines),
        "progress": session.get_progress(),
        "preview": graph,
        "complete": False,
        "registered_count": 0,
    }


async def _do_registration(session: IntakeSession) -> dict:
    """Register the extracted graph to Neo4j and clean up the session."""
    if not session.extracted_graph:
        return {
            "response": "登録するデータがありません。もう一度聞き取りを行ってください。",
            "progress": session.get_progress(),
            "preview": None,
            "complete": False,
            "registered_count": 0,
        }

    try:
        result = register_to_database(session.extracted_graph, user_name="intake_agent")
        registered_count = result.get("registered_count", 0)
        client_name = result.get("client_name", "不明")

        if result.get("status") == "success":
            response = (
                f"データベースへの登録が完了しました。\n"
                f"クライアント: {client_name}\n"
                f"登録ノード数: {registered_count}\n"
                f"登録タイプ: {', '.join(result.get('registered_types', []))}"
            )
            cleanup_session(session.session_id)
            return {
                "response": response,
                "progress": session.get_progress(),
                "preview": session.extracted_graph,
                "complete": True,
                "registered_count": registered_count,
            }
        else:
            error_msg = result.get("error", "不明なエラー")
            return {
                "response": f"登録中にエラーが発生しました: {error_msg}\nもう一度「登録して」と言ってください。",
                "progress": session.get_progress(),
                "preview": session.extracted_graph,
                "complete": False,
                "registered_count": 0,
            }
    except Exception as e:
        logger.error("Registration failed: %s", e, exc_info=True)
        return {
            "response": "登録中に予期しないエラーが発生しました。しばらくしてからもう一度お試しください。",
            "progress": session.get_progress(),
            "preview": session.extracted_graph,
            "complete": False,
            "registered_count": 0,
        }

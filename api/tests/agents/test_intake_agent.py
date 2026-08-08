"""Tests for conversational intake agent.

Tests cover IntakeSession state management, INTAKE_PHASES data integrity,
and the handle_intake_message async handler with mocked external dependencies.
All tests run without Neo4j, Gemini, or any API keys.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.agents.intake_agent import (
    IntakeSession,
    INTAKE_PHASES,
    handle_intake_message,
    _sessions,
)


# ---------------------------------------------------------------------------
# IntakeSession unit tests
# ---------------------------------------------------------------------------


class TestIntakeSessionCreation:
    """Verify initial state of a new IntakeSession."""

    def test_session_creation(self):
        """New session starts at phase 0 with empty collected text."""
        session = IntakeSession(session_id="test-001")
        assert session.current_phase == 0
        assert session.collected_text == []
        assert session.phase_responses == {}
        assert session.extracted_graph is None
        assert session.is_complete is False

    def test_session_has_session_id(self):
        """Session stores the provided session_id."""
        session = IntakeSession(session_id="abc-123")
        assert session.session_id == "abc-123"


class TestIntakeSessionPrompt:
    """Verify get_current_prompt returns correct phase data."""

    def test_get_current_prompt_initial(self):
        """Phase 0 (not started) returns the phase-1 prompt data."""
        session = IntakeSession(session_id="test-002")
        phase_id, pillar, prompt = session.get_current_prompt()
        assert phase_id == 1
        assert "本人性" in pillar
        assert len(prompt) > 0

    def test_get_current_prompt_after_advance(self):
        """After advancing to phase 2, prompt reflects phase 2."""
        session = IntakeSession(session_id="test-003")
        session.current_phase = 2
        phase_id, pillar, prompt = session.get_current_prompt()
        assert phase_id == 2
        assert "ケア" in pillar


class TestIntakeSessionResponses:
    """Verify response collection per phase."""

    def test_add_response(self):
        """add_response stores text under the current phase."""
        session = IntakeSession(session_id="test-004")
        session.current_phase = 1
        session.add_response("田中太郎、1990年1月1日、A型")
        assert 1 in session.phase_responses
        assert len(session.phase_responses[1]) == 1
        assert "田中太郎" in session.phase_responses[1][0]

    def test_add_response_accumulates(self):
        """Multiple responses in the same phase accumulate."""
        session = IntakeSession(session_id="test-005")
        session.current_phase = 1
        session.add_response("田中太郎")
        session.add_response("1990年1月1日")
        assert len(session.phase_responses[1]) == 2

    def test_phase_responses_separated(self):
        """Each phase has its own response list."""
        session = IntakeSession(session_id="test-006")
        session.current_phase = 1
        session.add_response("Phase 1 response")
        session.current_phase = 2
        session.add_response("Phase 2 response")
        assert 1 in session.phase_responses
        assert 2 in session.phase_responses
        assert session.phase_responses[1] != session.phase_responses[2]


class TestIntakeSessionPhaseAdvance:
    """Verify phase advancement logic."""

    def test_advance_phase(self):
        """advance_phase increments current_phase and returns True."""
        session = IntakeSession(session_id="test-007")
        session.current_phase = 0
        result = session.advance_phase()
        assert result is True
        assert session.current_phase == 1

    def test_advance_through_all_phases(self):
        """Can advance from 0 through all 7 phases."""
        session = IntakeSession(session_id="test-008")
        for expected in range(1, len(INTAKE_PHASES) + 1):
            result = session.advance_phase()
            assert result is True
            assert session.current_phase == expected

    def test_advance_past_last_phase(self):
        """advance_phase returns False when already at or past the last phase."""
        session = IntakeSession(session_id="test-009")
        session.current_phase = len(INTAKE_PHASES)
        result = session.advance_phase()
        assert result is False


class TestIntakeSessionNarrative:
    """Verify narrative text assembly."""

    def test_get_full_narrative(self):
        """Combines all phase responses with pillar headers."""
        session = IntakeSession(session_id="test-010")
        session.current_phase = 1
        session.add_response("田中太郎、1990-01-01、A型")
        session.current_phase = 2
        session.add_response("大声禁止、静かな部屋で落ち着く")
        narrative = session.get_full_narrative()
        assert "本人性" in narrative
        assert "田中太郎" in narrative
        assert "ケア" in narrative
        assert "大声禁止" in narrative

    def test_get_full_narrative_empty(self):
        """Empty session produces empty narrative."""
        session = IntakeSession(session_id="test-011")
        narrative = session.get_full_narrative()
        assert narrative == ""


class TestIntakeSessionProgress:
    """Verify progress reporting."""

    def test_get_progress(self):
        """Returns correct phase, total, and pillar info."""
        session = IntakeSession(session_id="test-012")
        session.current_phase = 3
        progress = session.get_progress()
        assert progress["phase"] == 3
        assert progress["total"] == 7
        assert "安全" in progress["pillar"] or "Safety" in progress["pillar"]

    def test_get_progress_phase_zero(self):
        """Phase 0 returns empty pillar string."""
        session = IntakeSession(session_id="test-013")
        session.current_phase = 0
        progress = session.get_progress()
        assert progress["phase"] == 0
        assert progress["pillar"] == ""


# ---------------------------------------------------------------------------
# INTAKE_PHASES data integrity tests
# ---------------------------------------------------------------------------


class TestIntakePhasesDefinition:
    """Verify the INTAKE_PHASES data structure."""

    def test_phases_have_required_fields(self):
        """All phases must have id, pillar, and prompt fields."""
        for phase in INTAKE_PHASES:
            assert "id" in phase, f"Phase missing 'id': {phase}"
            assert "pillar" in phase, f"Phase missing 'pillar': {phase}"
            assert "prompt" in phase, f"Phase missing 'prompt': {phase}"

    def test_phases_count_is_seven(self):
        """The manifesto defines exactly 7 pillars."""
        assert len(INTAKE_PHASES) == 7

    def test_phase_ids_sequential(self):
        """Phase ids are sequential from 1 to 7."""
        ids = [phase["id"] for phase in INTAKE_PHASES]
        assert ids == list(range(1, 8))

    def test_phases_have_nonempty_prompts(self):
        """Each phase prompt contains meaningful text."""
        for phase in INTAKE_PHASES:
            assert len(phase["prompt"]) > 10, f"Phase {phase['id']} has too short a prompt"

    def test_phases_have_priority(self):
        """Each phase includes a priority field."""
        for phase in INTAKE_PHASES:
            assert "priority" in phase, f"Phase {phase['id']} missing 'priority'"


# ---------------------------------------------------------------------------
# handle_intake_message async handler tests (mocked externals)
# ---------------------------------------------------------------------------


class TestHandleIntakeMessage:
    """Test the main intake message handler with mocked dependencies."""

    @pytest.fixture(autouse=True)
    def _clear_sessions(self):
        """Ensure session store is clean before and after each test."""
        _sessions.clear()
        yield
        _sessions.clear()

    @pytest.mark.asyncio
    async def test_first_message_starts_intake(self):
        """First message to a new session starts phase 1."""
        # handle_intake_message calls _evaluate_phase_response for non-zero
        # phases, but the first call (phase 0 -> 1) just returns the welcome.
        result = await handle_intake_message("session-new", "開始")
        assert "インテーク" in result["response"] or "面接" in result["response"]
        assert result["progress"]["phase"] == 1
        assert result["complete"] is False

    @pytest.mark.asyncio
    async def test_second_message_evaluates_response(self):
        """After intake starts, user response triggers phase evaluation."""
        # Start the session
        await handle_intake_message("session-eval", "開始")

        # Mock the LLM evaluation to return SUFFICIENT
        with patch(
            "app.agents.intake_agent._evaluate_phase_response",
            new_callable=AsyncMock,
            return_value="SUFFICIENT",
        ):
            result = await handle_intake_message(
                "session-eval",
                "田中太郎、1990年1月1日、A型",
            )
        # Should advance to phase 2
        assert result["progress"]["phase"] == 2
        assert result["complete"] is False

    @pytest.mark.asyncio
    async def test_skip_advances_phase(self):
        """Saying 'スキップ' advances to the next phase."""
        await handle_intake_message("session-skip", "開始")

        result = await handle_intake_message("session-skip", "スキップ")
        assert result["progress"]["phase"] == 2

    @pytest.mark.asyncio
    async def test_confirmation_triggers_registration(self):
        """'登録して' after all phases triggers registration."""
        # Create a session that has completed all phases
        session = IntakeSession(session_id="session-reg")
        session.current_phase = 7
        session._awaiting_confirmation = True
        session.extracted_graph = {
            "nodes": [
                {"label": "Client", "properties": {"name": "田中太郎"}},
            ],
            "relationships": [],
        }
        _sessions["session-reg"] = session

        mock_result = {
            "status": "success",
            "client_name": "田中太郎",
            "registered_count": 1,
            "registered_types": ["Client"],
        }

        with patch(
            "app.agents.intake_agent.register_to_database",
            return_value=mock_result,
        ):
            result = await handle_intake_message("session-reg", "登録して")

        assert result["complete"] is True
        assert result["registered_count"] == 1
        assert "田中太郎" in result["response"]
        # Session should be cleaned up
        assert "session-reg" not in _sessions

    @pytest.mark.asyncio
    async def test_confirmation_failure_does_not_clean_session(self):
        """Failed registration keeps the session alive for retry."""
        session = IntakeSession(session_id="session-fail")
        session.current_phase = 7
        session._awaiting_confirmation = True
        session.extracted_graph = {
            "nodes": [{"label": "Client", "properties": {"name": "失敗太郎"}}],
            "relationships": [],
        }
        _sessions["session-fail"] = session

        mock_result = {
            "status": "error",
            "error": "DB connection failed",
        }

        with patch(
            "app.agents.intake_agent.register_to_database",
            return_value=mock_result,
        ):
            result = await handle_intake_message("session-fail", "登録して")

        assert result["complete"] is False
        assert "session-fail" in _sessions

    @pytest.mark.asyncio
    async def test_awaiting_confirmation_rejects_non_confirm(self):
        """Non-confirmation text while awaiting keeps asking for confirmation."""
        session = IntakeSession(session_id="session-wait")
        session.current_phase = 7
        session._awaiting_confirmation = True
        session.extracted_graph = {"nodes": [], "relationships": []}
        _sessions["session-wait"] = session

        result = await handle_intake_message("session-wait", "ちょっと待って")
        assert result["complete"] is False
        assert "登録" in result["response"]

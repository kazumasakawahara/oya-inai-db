"""Comprehensive tests for the Gemini agent module.

Tests cover JSON parsing, DB tool functions, and safety compliance
with all external services mocked.
"""

import json
from unittest.mock import patch, AsyncMock, MagicMock

from app.agents.gemini_agent import (
    parse_json_from_response,
    get_extraction_prompt,
    search_client_info,
    search_ng_actions,
    search_care_preferences,
    search_emergency_contacts,
    search_hospital,
    search_guardian,
    search_support_logs,
    check_safety_compliance,
)


class TestParseJsonFromResponse:
    """Test JSON extraction from various Gemini response formats."""

    def test_plain_json(self):
        result = parse_json_from_response('{"nodes":[],"relationships":[]}')
        assert result == {"nodes": [], "relationships": []}

    def test_json_in_markdown_code_block(self):
        raw = '```json\n{"nodes":[{"temp_id":"c1","label":"Client","properties":{"name":"田中"}}],"relationships":[]}\n```'
        result = parse_json_from_response(raw)
        assert result is not None
        assert result["nodes"][0]["label"] == "Client"

    def test_json_in_plain_code_block(self):
        raw = '```\n{"key": "value"}\n```'
        result = parse_json_from_response(raw)
        assert result == {"key": "value"}

    def test_json_embedded_in_text(self):
        raw = 'Here is the result: {"status": "ok", "count": 5} end of output.'
        result = parse_json_from_response(raw)
        assert result is not None
        assert result["status"] == "ok"

    def test_invalid_json_returns_none(self):
        assert parse_json_from_response("not json at all") is None

    def test_empty_string_returns_none(self):
        assert parse_json_from_response("") is None

    def test_nested_json(self):
        raw = '{"data": {"nested": {"deep": true}}, "list": [1,2,3]}'
        result = parse_json_from_response(raw)
        assert result["data"]["nested"]["deep"] is True
        assert result["list"] == [1, 2, 3]

    def test_json_with_japanese(self):
        raw = '{"name": "田中太郎", "conditions": ["自閉スペクトラム症"]}'
        result = parse_json_from_response(raw)
        assert result["name"] == "田中太郎"


class TestGetExtractionPrompt:
    """Test extraction prompt loading."""

    def test_prompt_exists_and_has_content(self):
        prompt = get_extraction_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_prompt_contains_required_labels(self):
        prompt = get_extraction_prompt()
        assert "Client" in prompt
        assert "NgAction" in prompt

    def test_prompt_mentions_json(self):
        prompt = get_extraction_prompt()
        assert "json" in prompt.lower() or "JSON" in prompt


class TestSearchClientInfo:
    """Test search_client_info tool function.

    run_query is imported locally inside each tool function,
    so we patch at the source module: app.lib.db_operations.run_query
    """

    def test_client_found(self):
        mock_records = [
            {"name": "田中太郎", "dob": "1990-01-01", "bloodType": "A", "conditions": ["自閉症"]},
        ]
        with patch("app.lib.db_operations.run_query", return_value=mock_records):
            result = json.loads(search_client_info("田中太郎"))

        assert result["name"] == "田中太郎"
        assert result["bloodType"] == "A"

    def test_client_not_found(self):
        with patch("app.lib.db_operations.run_query", return_value=[]):
            result = json.loads(search_client_info("存在しない人"))

        assert "error" in result
        assert "見つかりません" in result["error"]


class TestSearchNgActions:
    """Test search_ng_actions tool function."""

    def test_ng_actions_found(self):
        mock_records = [
            {"action": "大声を出す", "reason": "パニック誘発", "riskLevel": "Panic"},
        ]
        with patch("app.agents.gemini_agent._resolve_client_name", return_value=("田中太郎", None)), \
             patch("app.lib.db_operations.run_query", return_value=mock_records):
            result = json.loads(search_ng_actions("田中太郎"))

        assert result["client_name"] == "田中太郎"
        assert len(result["ng_actions"]) == 1
        assert result["ng_actions"][0]["riskLevel"] == "Panic"

    def test_ng_actions_empty(self):
        with patch("app.lib.db_operations.run_query", return_value=[]):
            result = json.loads(search_ng_actions("テスト"))

        assert result["ng_actions"] == []


class TestSearchCarePreferences:
    """Test search_care_preferences tool function."""

    def test_care_preferences_found(self):
        mock_records = [
            {"category": "コミュニケーション", "instruction": "ゆっくり話す", "priority": "高"},
        ]
        with patch("app.agents.gemini_agent._resolve_client_name", return_value=("田中太郎", None)), \
             patch("app.lib.db_operations.run_query", return_value=mock_records):
            result = json.loads(search_care_preferences("田中太郎"))

        assert len(result["care_preferences"]) == 1
        assert result["care_preferences"][0]["category"] == "コミュニケーション"


class TestSearchEmergencyContacts:
    """Test search_emergency_contacts tool function."""

    def test_contacts_found(self):
        mock_records = [
            {"name": "田中花子", "relationship": "母", "phone": "090-1234-5678", "rank": 1},
        ]
        with patch("app.lib.db_operations.run_query", return_value=mock_records):
            result = json.loads(search_emergency_contacts("田中太郎"))

        assert len(result["contacts"]) == 1
        assert result["contacts"][0]["name"] == "田中花子"

    def test_contacts_empty(self):
        with patch("app.lib.db_operations.run_query", return_value=[]):
            result = json.loads(search_emergency_contacts("テスト"))

        assert result["contacts"] == []


class TestSearchHospital:
    """Test search_hospital tool function."""

    def test_hospital_found(self):
        mock_records = [
            {"name": "中央病院", "phone": "03-1234-5678", "address": "東京都"},
        ]
        with patch("app.lib.db_operations.run_query", return_value=mock_records):
            result = json.loads(search_hospital("田中太郎"))

        assert len(result["hospitals"]) == 1
        assert result["hospitals"][0]["name"] == "中央病院"


class TestSearchGuardian:
    """Test search_guardian tool function."""

    def test_guardian_found(self):
        mock_records = [
            {"name": "山田法律事務所", "type": "成年後見人", "phone": None, "organization": None},
        ]
        with patch("app.lib.db_operations.run_query", return_value=mock_records):
            result = json.loads(search_guardian("田中太郎"))

        assert len(result["guardians"]) == 1
        assert result["guardians"][0]["type"] == "成年後見人"


class TestSearchSupportLogs:
    """Test search_support_logs tool function."""

    def test_logs_found(self):
        mock_records = [
            {"date": "2026-04-01", "situation": "パニック", "action": "移動", "effectiveness": "Effective", "note": "ok", "supporter": "佐藤"},
        ]
        with patch("app.agents.gemini_agent._resolve_client_name", return_value=("田中太郎", None)), \
             patch("app.lib.db_operations.run_query", return_value=mock_records):
            result = json.loads(search_support_logs("田中太郎"))

        assert len(result["logs"]) == 1
        assert result["logs"][0]["situation"] == "パニック"

    def test_logs_empty(self):
        with patch("app.lib.db_operations.run_query", return_value=[]):
            result = json.loads(search_support_logs("テスト"))

        assert result["logs"] == []

    def test_logs_custom_limit(self):
        with patch("app.lib.db_operations.run_query", return_value=[]) as mock_rq:
            search_support_logs("テスト", limit=10)

        call_params = mock_rq.call_args[0][1]
        assert call_params["limit"] == 10


class TestCheckSafetyCompliance:
    """Test safety compliance checking."""

    def test_no_ng_actions_returns_safe(self):
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            check_safety_compliance("散歩に行きました", [])
        )
        assert result["is_violation"] is False
        assert result["risk_level"] == "None"

    def test_with_ng_actions_calls_gemini(self):
        """When ng_actions present, Gemini is called for safety check."""
        import asyncio
        ng_actions = [{"action": "大声を出す", "reason": "パニック", "riskLevel": "Panic"}]

        mock_response = MagicMock()
        mock_response.text = '{"is_violation": true, "warning": "禁忌事項に抵触", "risk_level": "Panic"}'

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel", return_value=mock_model):
            result = asyncio.get_event_loop().run_until_complete(
                check_safety_compliance("大声で呼びかけた", ng_actions)
            )

        assert result["is_violation"] is True

    def test_gemini_failure_returns_safe(self):
        """If Gemini fails, assume no violation (fail-safe)."""
        import asyncio
        ng_actions = [{"action": "test", "reason": "test", "riskLevel": "Panic"}]

        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel", side_effect=Exception("API Error")):
            result = asyncio.get_event_loop().run_until_complete(
                check_safety_compliance("test", ng_actions)
            )

        assert result["is_violation"] is False

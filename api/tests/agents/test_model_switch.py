"""Tests for dynamic LLM model switching.

Verifies that detect_model_switch correctly identifies model switch
commands in Japanese user messages, distinguishing between actual
switch requests (containing action verbs) and general questions or
partial matches.
"""

from app.agents.model_switch import detect_model_switch


class TestDetectModelSwitch:
    """Verify pattern matching for model switch detection."""

    # --- Specific model switch requests (should return a tuple) ---

    def test_detect_gemma_switch(self):
        """'gemma4を使って' triggers ollama provider."""
        result = detect_model_switch("gemma4を使って")
        assert result is not None
        assert result[0] == "ollama"

    def test_detect_gemini_switch(self):
        """'geminiに切り替えて' triggers gemini provider."""
        result = detect_model_switch("geminiに切り替えて")
        assert result is not None
        assert result[0] == "gemini"

    def test_detect_claude_switch(self):
        """'claudeを使って' triggers claude provider."""
        result = detect_model_switch("claudeを使って")
        assert result is not None
        assert result[0] == "claude"

    def test_detect_local_switch(self):
        """'ローカルモデルに切り替えて' triggers ollama provider."""
        result = detect_model_switch("ローカルモデルに切り替えて")
        assert result is not None
        assert result[0] == "ollama"

    def test_detect_cloud_switch(self):
        """'クラウドLLMを使って' triggers gemini provider."""
        result = detect_model_switch("クラウドLLMを使って")
        assert result is not None
        assert result[0] == "gemini"

    # --- Non-switch messages (should return None) ---

    def test_no_switch_normal_text(self):
        """General conversation should not trigger a switch."""
        assert detect_model_switch("今日の天気は？") is None

    def test_no_switch_partial_match(self):
        """Mentioning a model name without an action verb is not a switch."""
        assert detect_model_switch("geminiって何？") is None

    def test_no_switch_empty(self):
        """Empty string should not trigger a switch."""
        assert detect_model_switch("") is None

    # --- Case and context variations ---

    def test_switch_case_insensitive(self):
        """Model name matching should be case-insensitive."""
        result = detect_model_switch("Gemma4を使って")
        assert result is not None
        assert result[0] == "ollama"

    def test_switch_with_surrounding_text(self):
        """Switch command embedded in a longer sentence should be detected."""
        result = detect_model_switch("次はgemma4を使って回答して")
        assert result is not None
        assert result[0] == "ollama"


class TestDetectModelSwitchReturnShape:
    """Verify the return value structure of successful detections."""

    def test_returns_tuple_of_two_strings(self):
        """Successful detection returns a 2-element tuple of strings."""
        result = detect_model_switch("geminiに切り替えて")
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    def test_display_name_is_nonempty(self):
        """The display name (second element) should not be empty."""
        result = detect_model_switch("claudeを使って")
        assert result is not None
        assert len(result[1]) > 0

    def test_none_return_for_non_match(self):
        """Non-matching input returns exactly None (not False, not empty)."""
        result = detect_model_switch("こんにちは")
        assert result is None


class TestSwitchPatternsCoverage:
    """Ensure SWITCH_PATTERNS covers all expected providers."""

    def test_openai_gpt_switch(self):
        """'gptを使って' triggers openai provider."""
        result = detect_model_switch("gptを使って")
        assert result is not None
        assert result[0] == "openai"

    def test_openai_explicit_switch(self):
        """'openaiに切り替えて' triggers openai provider."""
        result = detect_model_switch("openaiに切り替えて")
        assert result is not None
        assert result[0] == "openai"

    def test_variation_ni_henkou(self):
        """Action verb 'に変更' is also recognized."""
        result = detect_model_switch("geminiに変更して")
        assert result is not None
        assert result[0] == "gemini"

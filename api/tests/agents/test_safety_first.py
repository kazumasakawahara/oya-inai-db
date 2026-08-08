"""Comprehensive tests for the Safety First emergency detection module."""

from unittest.mock import patch

from app.agents.safety_first import is_emergency, handle_emergency


class TestIsEmergency:
    """Test crisis keyword detection vs inquiry filtering."""

    # --- Crisis detection (should return True) ---

    def test_crisis_panic(self):
        assert is_emergency("田中さんがパニック中です") is True

    def test_crisis_collapsed(self):
        assert is_emergency("助けて！山田さんが倒れた") is True

    def test_crisis_collapsed_progressive(self):
        assert is_emergency("田中さんが倒れている") is True

    def test_crisis_sos(self):
        assert is_emergency("SOS 山田健太") is True

    def test_crisis_seizure(self):
        assert is_emergency("発作が起きた") is True

    def test_crisis_ambulance(self):
        assert is_emergency("救急車を呼んでください") is True

    def test_crisis_help(self):
        assert is_emergency("助けて！") is True

    def test_crisis_unconscious(self):
        assert is_emergency("意識がない状態です") is True

    # --- Inquiry filtering (should return False) ---

    def test_inquiry_teach(self):
        """情報照会キーワード「教えて」が含まれれば Safety First を発動しない。"""
        assert is_emergency("緊急連絡先を教えてください") is False

    def test_inquiry_check(self):
        assert is_emergency("山田健太さんの緊急連絡先を調べてください") is False

    def test_inquiry_confirm(self):
        assert is_emergency("禁忌事項の一覧を確認したい") is False

    def test_inquiry_list(self):
        assert is_emergency("緊急連絡先の一覧") is False

    def test_inquiry_want_to_know(self):
        assert is_emergency("NGアクションを知りたい") is False

    def test_inquiry_with_crisis_word(self):
        """情報照会インジケータが優先される（教えて + 発作）。"""
        assert is_emergency("発作が起きた時の対応を教えて") is False

    # --- General messages (should return False) ---

    def test_general_greeting(self):
        assert is_emergency("こんにちは") is False

    def test_general_daily(self):
        assert is_emergency("今日の予定を教えて") is False

    def test_general_registration(self):
        assert is_emergency("支援記録を登録してください") is False

    def test_general_empty(self):
        assert is_emergency("") is False

    def test_general_status(self):
        assert is_emergency("山田健太��んの様子を教えて") is False


class TestHandleEmergency:
    """Test emergency response generation with DB mocking."""

    def test_handle_emergency_with_client_name(self):
        mock_records = [
            {
                "c": {"name": "田中太郎"},
                "ng_actions": [
                    {"action": "大声を出す", "riskLevel": "Panic", "reason": "パニック誘発"},
                ],
                "care_prefs": [
                    {"category": "落ち着かせ方", "instruction": "静かな部屋に移動"},
                ],
                "key_persons": [
                    {"name": "田中花子", "relationship": "母", "phone": "090-1234-5678"},
                ],
                "h": None,
                "g": None,
            }
        ]
        with patch("app.agents.safety_first.run_query", return_value=mock_records):
            result = handle_emergency("田中太郎さんがパニック中です")

        assert "田中太郎" in result
        assert "大声を出す" in result
        assert "パニック" in result or "Panic" in result
        assert "田中花子" in result
        assert "090-1234-5678" in result

    def test_handle_emergency_no_client_name(self):
        result = handle_emergency("誰かが倒れた")

        assert "特定できません" in result

    def test_handle_emergency_client_not_found(self):
        with patch("app.agents.safety_first.run_query", return_value=[]):
            result = handle_emergency("田中太郎さんがパニック中")

        assert "見つかりません" in result
        assert "田中太郎" in result

    def test_handle_emergency_with_care_prefs(self):
        mock_records = [
            {
                "c": {"name": "山田花子"},
                "ng_actions": [],
                "care_prefs": [
                    {"category": "コミュニケーション", "instruction": "ゆっくり話す"},
                ],
                "key_persons": [],
                "h": None,
                "g": None,
            }
        ]
        with patch("app.agents.safety_first.run_query", return_value=mock_records):
            result = handle_emergency("山田花子さんが倒れた")

        assert "推奨ケア" in result
        assert "ゆっくり話す" in result

    def test_handle_emergency_with_key_persons(self):
        mock_records = [
            {
                "c": {"name": "佐藤一郎"},
                "ng_actions": [],
                "care_prefs": [],
                "key_persons": [
                    {"name": "佐藤花子", "relationship": "妻", "phone": "090-9999-8888"},
                ],
                "h": None,
                "g": None,
            }
        ]
        with patch("app.agents.safety_first.run_query", return_value=mock_records):
            result = handle_emergency("佐藤一郎さんが倒れた")

        assert "緊急連絡先" in result
        assert "佐藤花子" in result
        assert "妻" in result

    def test_handle_emergency_minimal_data(self):
        """Client exists but has no related data."""
        mock_records = [
            {
                "c": {"name": "最小太郎"},
                "ng_actions": [],
                "care_prefs": [],
                "key_persons": [],
                "h": None,
                "g": None,
            }
        ]
        with patch("app.agents.safety_first.run_query", return_value=mock_records):
            result = handle_emergency("最小太郎さんがパニック中")

        assert "最小太郎" in result
        assert "緊急情報" in result

    def test_handle_emergency_2char_name(self):
        """2-character kanji name is extracted correctly."""
        with patch("app.agents.safety_first.run_query", return_value=[]):
            result = handle_emergency("田中さんが倒れた")
        assert "田中" in result

    def test_handle_emergency_3char_name(self):
        """3-character kanji name is extracted correctly."""
        with patch("app.agents.safety_first.run_query", return_value=[]):
            result = handle_emergency("長谷川さんが倒れた")
        assert "長谷川" in result

    def test_handle_emergency_4char_name(self):
        """4-character kanji name is extracted correctly."""
        with patch("app.agents.safety_first.run_query", return_value=[]):
            result = handle_emergency("西園寺太さんが倒れた")
        assert "西園寺太" in result

    def test_handle_emergency_no_san_suffix(self):
        """Without さん suffix, name cannot be extracted."""
        result = handle_emergency("田中が倒れた")
        assert "特定できません" in result

    def test_handle_emergency_katakana_name_not_matched(self):
        """Katakana names are not matched by the kanji regex."""
        result = handle_emergency("タナカさんが倒れた")
        assert "特定できません" in result

    def test_handle_emergency_single_char_name_not_matched(self):
        """Single-character names (1 kanji) are not matched."""
        result = handle_emergency("張さんが倒れた")
        assert "特定できません" in result

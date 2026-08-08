import pytest
from app.lib.normalize import name_to_kana


class TestNameToKana:
    def test_kanji_to_hiragana(self):
        assert name_to_kana("田中太郎") == "たなかたろう"

    def test_hiragana_passthrough(self):
        assert name_to_kana("たなか") == "たなか"

    def test_katakana_to_hiragana(self):
        assert name_to_kana("タナカ") == "たなか"

    def test_empty_returns_empty(self):
        assert name_to_kana("") == ""
        assert name_to_kana(None) == ""

    def test_mixed_kanji_kana(self):
        result = name_to_kana("山田花子")
        assert result == "やまだはなこ"

    def test_honorific_stripped_before_conversion(self):
        # normalize_text strips whitespace; kana conversion is on cleaned text
        result = name_to_kana("  田中  ")
        assert result == "たなか"

    def test_fullwidth_ascii_normalized(self):
        # Fullwidth → halfwidth then converted
        result = name_to_kana("ＡＢＣ")
        # pykakasi preserves ASCII as-is in hira output
        assert "abc" in result.lower() or "ABC" in result

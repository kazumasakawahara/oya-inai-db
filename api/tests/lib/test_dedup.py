"""Tests for dedup.py text normalization functions."""
import unicodedata
import pytest
from unittest.mock import patch
from app.lib.dedup import normalize_text, normalize_name


class TestNormalizeText:
    def test_strips_leading_trailing_whitespace(self):
        assert normalize_text("  田中  ") == "田中"

    def test_collapses_multiple_spaces(self):
        assert normalize_text("田中  太郎") == "田中 太郎"

    def test_collapses_mixed_whitespace(self):
        assert normalize_text("田中\t 太郎") == "田中 太郎"

    def test_nfc_normalization(self):
        # NFD form of "が" (か + combining dakuten)
        nfd_ga = unicodedata.normalize("NFD", "が")
        assert normalize_text(nfd_ga) == "が"
        assert normalize_text(nfd_ga) == unicodedata.normalize("NFC", "が")

    def test_fullwidth_ascii_to_halfwidth(self):
        # ＡＢＣ → ABC, １２３ → 123
        assert normalize_text("ＡＢＣ１２３") == "ABC123"

    def test_fullwidth_symbols_to_halfwidth(self):
        assert normalize_text("！＠＃") == "!@#"

    def test_none_returns_empty_string(self):
        assert normalize_text(None) == ""

    def test_empty_string_returns_empty_string(self):
        assert normalize_text("") == ""

    def test_whitespace_only_returns_empty_string(self):
        assert normalize_text("   ") == ""

    def test_normal_text_unchanged(self):
        assert normalize_text("田中太郎") == "田中太郎"

    def test_mixed_fullwidth_and_japanese(self):
        assert normalize_text("田中ＡＢＣ") == "田中ABC"


class TestNormalizeName:
    def test_strips_san_suffix(self):
        assert normalize_name("田中さん") == "田中"

    def test_strips_sama_suffix(self):
        assert normalize_name("田中様") == "田中"

    def test_strips_kun_suffix(self):
        assert normalize_name("田中くん") == "田中"

    def test_strips_chan_suffix(self):
        assert normalize_name("田中ちゃん") == "田中"

    def test_strips_shi_suffix(self):
        assert normalize_name("田中氏") == "田中"

    def test_strips_sensei_suffix(self):
        assert normalize_name("田中先生") == "田中"

    def test_preserves_non_suffix_san(self):
        # "さんま" should not be stripped — さん is not at word boundary here
        # but さんま ends with ま, not さん at end
        assert normalize_name("さんま") == "さんま"

    def test_preserves_san_in_middle(self):
        assert normalize_name("さんま太郎") == "さんま太郎"

    def test_none_returns_empty_string(self):
        assert normalize_name(None) == ""

    def test_empty_string_returns_empty_string(self):
        assert normalize_name("") == ""

    def test_normalize_text_called_first(self):
        # Fullwidth + honorific: ＡＢＣさん → ABCさん → ABC
        assert normalize_name("ＡＢＣさん") == "ABC"

    def test_whitespace_stripped_before_honorific_check(self):
        assert normalize_name("  田中さん  ") == "田中"

    def test_name_without_honorific_unchanged(self):
        assert normalize_name("田中太郎") == "田中太郎"

    def test_only_honorific_returns_empty(self):
        assert normalize_name("さん") == ""


class TestNormalizeCondition:
    def test_canonical_name_unchanged(self):
        from app.lib.dedup import normalize_condition
        assert normalize_condition("自閉症スペクトラム障害") == "自閉症スペクトラム障害"

    def test_alias_asd_resolved(self):
        from app.lib.dedup import normalize_condition
        assert normalize_condition("ASD") == "自閉症スペクトラム障害"

    def test_alias_short_form_resolved(self):
        from app.lib.dedup import normalize_condition
        assert normalize_condition("自閉スペクトラム") == "自閉症スペクトラム障害"

    def test_alias_adhd_resolved(self):
        from app.lib.dedup import normalize_condition
        assert normalize_condition("ADHD") == "注意欠如多動症"

    def test_case_insensitive_asd(self):
        from app.lib.dedup import normalize_condition
        assert normalize_condition("asd") == "自閉症スペクトラム障害"

    def test_unknown_name_passthrough(self):
        from app.lib.dedup import normalize_condition
        assert normalize_condition("希少疾患X") == "希少疾患X"

    def test_none_returns_empty(self):
        from app.lib.dedup import normalize_condition
        assert normalize_condition(None) == ""

    def test_empty_returns_empty(self):
        from app.lib.dedup import normalize_condition
        assert normalize_condition("") == ""


class TestFindSemanticDuplicates:
    """Tests for find_semantic_duplicates() using mocked external calls."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_embed_text_returns_none(self):
        from unittest.mock import AsyncMock, patch
        from app.lib.dedup import find_semantic_duplicates

        with patch("app.lib.dedup.embed_text", new=AsyncMock(return_value=None)):
            result = await find_semantic_duplicates(
                text="車椅子禁止",
                label="NgAction",
                index_name="ng_action_embedding",
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_candidates_above_threshold(self):
        from unittest.mock import AsyncMock, patch
        from app.lib.dedup import find_semantic_duplicates

        fake_embedding = [0.1] * 768
        # run_query returns two rows; only the one with score >= 0.85 should appear
        mock_rows = [
            {"text": "車椅子使用禁止", "score": 0.92, "nodeId": "4:abc:1"},
            {"text": "走らないこと", "score": 0.70, "nodeId": "4:abc:2"},
        ]

        with (
            patch("app.lib.dedup.embed_text", new=AsyncMock(return_value=fake_embedding)),
            patch("app.lib.dedup.run_query", return_value=mock_rows),
        ):
            result = await find_semantic_duplicates(
                text="車椅子禁止",
                label="NgAction",
                index_name="ng_action_embedding",
                threshold=0.85,
                top_k=5,
            )

        # Only the row with score 0.92 is above threshold
        assert len(result) == 1
        assert result[0]["text"] == "車椅子使用禁止"
        assert result[0]["score"] == 0.92

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_text(self):
        from unittest.mock import AsyncMock, patch
        from app.lib.dedup import find_semantic_duplicates

        with patch("app.lib.dedup.embed_text", new=AsyncMock()) as mock_embed:
            result = await find_semantic_duplicates(
                text="",
                label="NgAction",
                index_name="ng_action_embedding",
            )
        assert result == []
        mock_embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_embed_text_exception_gracefully(self):
        from unittest.mock import AsyncMock, patch
        from app.lib.dedup import find_semantic_duplicates

        with patch(
            "app.lib.dedup.embed_text",
            new=AsyncMock(side_effect=RuntimeError("API error")),
        ):
            result = await find_semantic_duplicates(
                text="車椅子禁止",
                label="NgAction",
                index_name="ng_action_embedding",
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_handles_run_query_exception_gracefully(self):
        from unittest.mock import AsyncMock, patch
        from app.lib.dedup import find_semantic_duplicates

        fake_embedding = [0.1] * 768

        with (
            patch("app.lib.dedup.embed_text", new=AsyncMock(return_value=fake_embedding)),
            patch("app.lib.dedup.run_query", side_effect=RuntimeError("Neo4j error")),
        ):
            result = await find_semantic_duplicates(
                text="車椅子禁止",
                label="NgAction",
                index_name="ng_action_embedding",
            )
        assert result == []


class TestFindSimilarByKana:
    def test_finds_exact_kana_match(self):
        from app.lib.dedup import find_similar_by_kana

        # DB row already has kana stored; input converts to same kana via name_to_kana()
        # "田中太郎" → "たなかたろう" (pykakasi)
        mock_rows = [
            {"name": "田中太郎", "kana": "たなかたろう", "nodeId": "4:abc:1"},
        ]
        with patch("app.lib.dedup.run_query", return_value=mock_rows):
            result = find_similar_by_kana("田中太郎")  # exact same name → exact kana match
        assert len(result) == 1
        assert result[0]["name"] == "田中太郎"
        assert result[0]["similarity"] == 1.0
        assert result[0]["matchType"] == "kana"

    def test_finds_similar_kana(self):
        from app.lib.dedup import find_similar_by_kana

        mock_rows = [
            {"name": "田中太郎", "kana": "たなかたろう", "nodeId": "4:abc:1"},
            {"name": "佐藤花子", "kana": "さとうはなこ", "nodeId": "4:abc:2"},
        ]
        with patch("app.lib.dedup.run_query", return_value=mock_rows):
            result = find_similar_by_kana("田中次郎")  # たなかじろう - similar
        # 田中太郎 should be found (たなかたろう vs たなかじろう = high similarity)
        assert len(result) >= 1
        assert result[0]["name"] == "田中太郎"

    def test_returns_empty_for_no_match(self):
        from app.lib.dedup import find_similar_by_kana

        mock_rows = [
            {"name": "佐藤花子", "kana": "さとうはなこ", "nodeId": "4:abc:1"},
        ]
        with patch("app.lib.dedup.run_query", return_value=mock_rows):
            result = find_similar_by_kana("山田健太", threshold=0.9)
        assert result == []

    def test_returns_empty_for_empty_input(self):
        from app.lib.dedup import find_similar_by_kana

        result = find_similar_by_kana("")
        assert result == []
        result = find_similar_by_kana(None)
        assert result == []

    def test_handles_db_error_gracefully(self):
        from app.lib.dedup import find_similar_by_kana

        with patch("app.lib.dedup.run_query", side_effect=Exception("DB error")):
            result = find_similar_by_kana("田中太郎")
        assert result == []

    def test_respects_limit(self):
        from app.lib.dedup import find_similar_by_kana

        mock_rows = [
            {"name": f"田中{i}郎", "kana": f"たなか{chr(0x305F + i)}ろう", "nodeId": f"4:abc:{i}"}
            for i in range(10)
        ]
        with patch("app.lib.dedup.run_query", return_value=mock_rows):
            result = find_similar_by_kana("田中太郎", limit=3)
        assert len(result) <= 3

    def test_sorted_by_similarity_descending(self):
        from app.lib.dedup import find_similar_by_kana

        mock_rows = [
            {"name": "田中太郎", "kana": "たなかたろう", "nodeId": "4:abc:1"},
            {"name": "田中次郎", "kana": "たなかじろう", "nodeId": "4:abc:2"},
        ]
        with patch("app.lib.dedup.run_query", return_value=mock_rows):
            result = find_similar_by_kana("田中太郎")
        if len(result) >= 2:
            assert result[0]["similarity"] >= result[1]["similarity"]

    def test_rejects_invalid_label(self):
        from app.lib.dedup import find_similar_by_kana

        with patch("app.lib.dedup.run_query") as mock_query:
            result = find_similar_by_kana("田中太郎", label="Client; DROP TABLE")
        assert result == []
        mock_query.assert_not_called()

    def test_skips_rows_with_no_kana(self):
        from app.lib.dedup import find_similar_by_kana

        mock_rows = [
            {"name": "田中太郎", "kana": None, "nodeId": "4:abc:1"},
            {"name": "佐藤花子", "kana": "", "nodeId": "4:abc:2"},
        ]
        with patch("app.lib.dedup.run_query", return_value=mock_rows):
            result = find_similar_by_kana("田中太郎")
        assert result == []

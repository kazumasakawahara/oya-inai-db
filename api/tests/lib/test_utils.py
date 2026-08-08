"""Comprehensive tests for the utils module.

Tests cover Japanese era conversion, date parsing, age calculation,
and date formatting — all pure functions with no external dependencies.
"""

from datetime import date

import pytest

from app.lib.utils import (
    calculate_age,
    convert_wareki_to_seireki,
    format_date_with_age,
    safe_date_parse,
    GENGO_MAP,
)


# =============================================================================
# convert_wareki_to_seireki
# =============================================================================

class TestConvertWarekiToSeireki:
    """Test Japanese era (wareki) to Western calendar (seireki) conversion."""

    # --- Valid conversions: kanji era names ---

    def test_showa(self):
        assert convert_wareki_to_seireki("昭和50年3月15日") == "1975-03-15"

    def test_heisei(self):
        assert convert_wareki_to_seireki("平成7年12月1日") == "1995-12-01"

    def test_reiwa(self):
        assert convert_wareki_to_seireki("令和5年1月10日") == "2023-01-10"

    def test_meiji(self):
        assert convert_wareki_to_seireki("明治45年7月1日") == "1912-07-01"

    def test_taisho(self):
        assert convert_wareki_to_seireki("大正14年5月10日") == "1925-05-10"

    def test_reiwa_year1(self):
        assert convert_wareki_to_seireki("令和1年5月1日") == "2019-05-01"

    def test_showa_year1(self):
        assert convert_wareki_to_seireki("昭和1年12月25日") == "1926-12-25"

    # --- Valid conversions: alphabetic abbreviations ---

    def test_alpha_s(self):
        assert convert_wareki_to_seireki("S50.3.15") == "1975-03-15"

    def test_alpha_h(self):
        assert convert_wareki_to_seireki("H7.12.1") == "1995-12-01"

    def test_alpha_r(self):
        assert convert_wareki_to_seireki("R5.1.10") == "2023-01-10"

    def test_alpha_m(self):
        assert convert_wareki_to_seireki("M45.7.1") == "1912-07-01"

    def test_alpha_t(self):
        assert convert_wareki_to_seireki("T14.5.10") == "1925-05-10"

    def test_alpha_lowercase(self):
        assert convert_wareki_to_seireki("s50.3.15") == "1975-03-15"

    # --- Valid conversions: different separators ---

    def test_slash_separator(self):
        assert convert_wareki_to_seireki("昭和50/3/15") == "1975-03-15"

    def test_dash_separator(self):
        assert convert_wareki_to_seireki("昭和50-3-15") == "1975-03-15"

    def test_alpha_slash_separator(self):
        assert convert_wareki_to_seireki("H7/12/1") == "1995-12-01"

    def test_alpha_dash_separator(self):
        assert convert_wareki_to_seireki("R5-1-10") == "2023-01-10"

    # --- Invalid inputs ---

    def test_empty_string(self):
        assert convert_wareki_to_seireki("") is None

    def test_none_input(self):
        assert convert_wareki_to_seireki(None) is None

    def test_invalid_string(self):
        assert convert_wareki_to_seireki("invalid") is None

    def test_western_date_returns_none(self):
        assert convert_wareki_to_seireki("2026-04-05") is None

    def test_invalid_month(self):
        assert convert_wareki_to_seireki("令和5年13月1日") is None

    def test_invalid_day(self):
        assert convert_wareki_to_seireki("令和5年2月30日") is None

    def test_feb_29_non_leap_year(self):
        assert convert_wareki_to_seireki("令和5年2月29日") is None  # 2023 not leap year

    def test_feb_29_leap_year(self):
        assert convert_wareki_to_seireki("令和6年2月29日") == "2024-02-29"  # 2024 is leap year


class TestGengoMap:
    """Validate the era mapping table."""

    def test_all_eras_present(self):
        expected_eras = {"明治", "大正", "昭和", "平成", "令和", "M", "T", "S", "H", "R"}
        assert expected_eras.issubset(set(GENGO_MAP.keys()))

    def test_era_ranges_have_start_and_end(self):
        for era, info in GENGO_MAP.items():
            assert "start" in info, f"Era {era} missing 'start'"
            assert "end" in info, f"Era {era} missing 'end'"
            assert info["start"] <= info["end"], f"Era {era} start > end"


# =============================================================================
# safe_date_parse
# =============================================================================

class TestSafeDateParse:
    """Test date parsing with multiple format support."""

    def test_iso_format(self):
        assert safe_date_parse("2026-04-05") == date(2026, 4, 5)

    def test_slash_format(self):
        assert safe_date_parse("2026/04/05") == date(2026, 4, 5)

    def test_wareki_kanji(self):
        assert safe_date_parse("令和8年4月5日") == date(2026, 4, 5)

    def test_wareki_alpha(self):
        assert safe_date_parse("S50.3.15") == date(1975, 3, 15)

    def test_empty_returns_none(self):
        assert safe_date_parse("") is None

    def test_none_returns_none(self):
        assert safe_date_parse(None) is None

    def test_invalid_returns_none(self):
        assert safe_date_parse("not-a-date") is None

    def test_strips_whitespace(self):
        assert safe_date_parse("  2026-04-05  ") == date(2026, 4, 5)

    def test_stringified_non_string(self):
        """Handles non-string input via str() conversion."""
        assert safe_date_parse(20260405) is None  # int is not a valid date format

    def test_partial_date_returns_none(self):
        assert safe_date_parse("2026-04") is None


# =============================================================================
# calculate_age
# =============================================================================

class TestCalculateAge:
    """Test age calculation with various inputs."""

    def test_basic_age(self):
        age = calculate_age("2000-01-01", reference_date=date(2026, 4, 5))
        assert age == 26

    def test_date_object_input(self):
        age = calculate_age(date(2000, 1, 1), reference_date=date(2026, 4, 5))
        assert age == 26

    def test_birthday_not_yet(self):
        age = calculate_age("2000-12-31", reference_date=date(2026, 4, 5))
        assert age == 25

    def test_birthday_today(self):
        age = calculate_age("2000-04-05", reference_date=date(2026, 4, 5))
        assert age == 26

    def test_birthday_yesterday(self):
        age = calculate_age("2000-04-04", reference_date=date(2026, 4, 5))
        assert age == 26

    def test_birthday_tomorrow(self):
        age = calculate_age("2000-04-06", reference_date=date(2026, 4, 5))
        assert age == 25

    def test_wareki_string_input(self):
        age = calculate_age("昭和50年3月15日", reference_date=date(2026, 4, 5))
        assert age == 51

    def test_none_returns_none(self):
        assert calculate_age(None) is None

    def test_invalid_string_returns_none(self):
        assert calculate_age("not-a-date") is None

    def test_future_birth_returns_none(self):
        age = calculate_age("2030-01-01", reference_date=date(2026, 4, 5))
        assert age is None

    def test_same_day_birth(self):
        age = calculate_age("2026-04-05", reference_date=date(2026, 4, 5))
        assert age == 0

    def test_newborn(self):
        age = calculate_age("2025-12-01", reference_date=date(2026, 4, 5))
        assert age == 0

    def test_default_reference_date(self):
        """Without reference_date, should use today."""
        age = calculate_age("2000-01-01")
        assert age is not None
        assert age >= 25  # running in 2025+


# =============================================================================
# format_date_with_age
# =============================================================================

class TestFormatDateWithAge:
    """Test date formatting with age display."""

    def test_date_object(self):
        result = format_date_with_age(date(2000, 1, 1))
        assert "2000-01-01" in result
        assert "歳" in result

    def test_string_input(self):
        result = format_date_with_age("2000-01-01")
        assert "2000-01-01" in result
        assert "歳" in result

    def test_wareki_input(self):
        result = format_date_with_age("昭和50年3月15日")
        assert "1975-03-15" in result
        assert "歳" in result

    def test_none_returns_unknown(self):
        assert format_date_with_age(None) == "不明"

    def test_invalid_string_returns_original(self):
        assert format_date_with_age("invalid-date") == "invalid-date"

    def test_format_includes_parentheses(self):
        result = format_date_with_age(date(2000, 1, 1))
        assert "（" in result
        assert "）" in result

    def test_empty_string_input(self):
        result = format_date_with_age("")
        # Empty string fails safe_date_parse, returns original
        assert result == ""

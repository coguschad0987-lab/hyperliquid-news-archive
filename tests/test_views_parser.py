"""
Unit tests for X (Twitter) views parser.

These tests ensure accurate parsing of X's various view count formats
for ranking posts by popularity.
"""

import pytest
from twitter_news.views_parser import parse_views, format_views


class TestParseViewsAbbreviated:
    """Tests for abbreviated formats (K, M, B suffixes)."""

    def test_parse_k_integer(self):
        """Should parse whole K values."""
        assert parse_views("1K") == 1000
        assert parse_views("5K") == 5000
        assert parse_views("15K") == 15000
        assert parse_views("100K") == 100000

    def test_parse_k_decimal(self):
        """Should parse decimal K values."""
        assert parse_views("1.2K") == 1200
        assert parse_views("1.5K") == 1500
        assert parse_views("2.3K") == 2300
        assert parse_views("15.7K") == 15700

    def test_parse_m_integer(self):
        """Should parse whole M values."""
        assert parse_views("1M") == 1000000
        assert parse_views("5M") == 5000000
        assert parse_views("10M") == 10000000

    def test_parse_m_decimal(self):
        """Should parse decimal M values."""
        assert parse_views("1.5M") == 1500000
        assert parse_views("2.3M") == 2300000
        assert parse_views("1.23M") == 1230000

    def test_parse_b_suffix(self):
        """Should parse B (billion) values."""
        assert parse_views("1B") == 1000000000
        assert parse_views("1.5B") == 1500000000

    def test_case_insensitive(self):
        """Should handle uppercase and lowercase suffixes."""
        assert parse_views("1.2k") == 1200
        assert parse_views("1.2K") == 1200
        assert parse_views("1m") == 1000000
        assert parse_views("1M") == 1000000

    def test_comma_as_decimal(self):
        """Should handle comma as decimal separator (EU format in abbreviations)."""
        assert parse_views("1,2K") == 1200
        assert parse_views("1,5M") == 1500000

    def test_with_whitespace(self):
        """Should handle surrounding whitespace."""
        assert parse_views("  1.2K  ") == 1200
        assert parse_views(" 5M ") == 5000000

    def test_whitespace_before_suffix(self):
        """Should handle whitespace between number and suffix."""
        assert parse_views("1.2 K") == 1200
        assert parse_views("5 M") == 5000000


class TestParseViewsPlainNumbers:
    """Tests for plain number formats."""

    def test_parse_simple_integer(self):
        """Should parse simple integers."""
        assert parse_views("500") == 500
        assert parse_views("1200") == 1200
        assert parse_views("99999") == 99999

    def test_parse_comma_separated_us(self):
        """Should parse US format with commas."""
        assert parse_views("1,200") == 1200
        assert parse_views("12,345") == 12345
        assert parse_views("1,234,567") == 1234567

    def test_parse_dot_separated_eu(self):
        """Should parse EU format with dots as thousands."""
        assert parse_views("1.200") == 1200
        assert parse_views("12.345") == 12345
        assert parse_views("1.234.567") == 1234567

    def test_parse_space_separated(self):
        """Should parse space-separated thousands."""
        assert parse_views("1 200") == 1200
        assert parse_views("12 345") == 12345

    def test_single_digit(self):
        """Should parse single digit numbers."""
        assert parse_views("0") == 0
        assert parse_views("5") == 5
        assert parse_views("9") == 9

    def test_with_whitespace(self):
        """Should handle surrounding whitespace."""
        assert parse_views("  1200  ") == 1200
        assert parse_views(" 500 ") == 500


class TestParseViewsEdgeCases:
    """Edge case tests for robustness."""

    def test_empty_string(self):
        """Should return None for empty string."""
        assert parse_views("") is None
        assert parse_views("   ") is None

    def test_none_like_input(self):
        """Should handle None-like empty input."""
        assert parse_views("") is None

    def test_invalid_format(self):
        """Should return None for invalid formats."""
        assert parse_views("abc") is None
        assert parse_views("K") is None
        assert parse_views("views") is None
        assert parse_views("1.2.3K") is None

    def test_negative_numbers(self):
        """Should return None for negative numbers (views can't be negative)."""
        # Current implementation doesn't explicitly handle negatives
        # They would fail the regex, which is correct behavior
        assert parse_views("-100") is None

    def test_very_large_numbers(self):
        """Should handle very large numbers."""
        assert parse_views("999B") == 999000000000
        assert parse_views("1,000,000,000") == 1000000000

    def test_zero(self):
        """Should parse zero correctly."""
        assert parse_views("0") == 0
        assert parse_views("0K") == 0

    def test_decimal_precision_rounding(self):
        """Should handle decimal precision (truncated to int)."""
        # 1.99K should be 1990, not 2000 (truncation not rounding)
        assert parse_views("1.99K") == 1990
        # 1.999K
        assert parse_views("1.999K") == 1999


class TestParseViewsRealXFormats:
    """Tests based on actual X UI formats observed."""

    def test_typical_low_views(self):
        """Typical low view counts."""
        assert parse_views("234") == 234
        assert parse_views("1,234") == 1234

    def test_typical_medium_views(self):
        """Typical medium view counts (thousands)."""
        assert parse_views("5.2K") == 5200
        assert parse_views("15K") == 15000
        assert parse_views("99.9K") == 99900

    def test_typical_high_views(self):
        """Typical high view counts (millions)."""
        assert parse_views("1.2M") == 1200000
        assert parse_views("5M") == 5000000
        assert parse_views("10.5M") == 10500000

    def test_viral_views(self):
        """Viral post view counts."""
        assert parse_views("50M") == 50000000
        assert parse_views("100M") == 100000000
        assert parse_views("1B") == 1000000000


class TestFormatViews:
    """Tests for format_views function (reverse operation)."""

    def test_format_under_thousand(self):
        """Numbers under 1000 should not be abbreviated."""
        assert format_views(0) == "0"
        assert format_views(500) == "500"
        assert format_views(999) == "999"

    def test_format_thousands(self):
        """Thousands should use K suffix."""
        assert format_views(1000) == "1K"
        assert format_views(1200) == "1.2K"
        assert format_views(1500) == "1.5K"
        assert format_views(15000) == "15K"
        assert format_views(15700) == "15.7K"

    def test_format_millions(self):
        """Millions should use M suffix."""
        assert format_views(1000000) == "1M"
        assert format_views(1500000) == "1.5M"
        assert format_views(10000000) == "10M"

    def test_format_billions(self):
        """Billions should use B suffix."""
        assert format_views(1000000000) == "1B"
        assert format_views(1500000000) == "1.5B"

    def test_format_removes_trailing_zero(self):
        """Should remove unnecessary trailing zeros."""
        assert format_views(1000) == "1K"  # not "1.0K"
        assert format_views(2000000) == "2M"  # not "2.0M"


class TestRoundTrip:
    """Test that parse and format are roughly inverse operations."""

    def test_roundtrip_abbreviated(self):
        """Parsing formatted output should give original value."""
        values = [1000, 1500, 15000, 1000000, 1500000, 10000000]
        for val in values:
            formatted = format_views(val)
            parsed = parse_views(formatted)
            assert parsed == val, f"Roundtrip failed for {val}: formatted={formatted}, parsed={parsed}"

    def test_roundtrip_small_numbers(self):
        """Small numbers should roundtrip exactly."""
        for val in [0, 1, 50, 100, 500, 999]:
            formatted = format_views(val)
            parsed = parse_views(formatted)
            assert parsed == val


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

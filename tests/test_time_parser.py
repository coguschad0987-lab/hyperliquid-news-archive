"""
Unit tests for X (Twitter) time parser.

These tests ensure accurate parsing of X's various timestamp formats
for the "last 24 hours" filter requirement.
"""

import pytest
from datetime import datetime, timedelta
from twitter_news.time_parser import (
    parse_relative_time,
    parse_date_string,
    parse_x_time,
    is_within_hours,
    KST,
)


# Fixed reference time for deterministic testing: 2026-01-24 09:00:00 KST
REFERENCE_TIME = datetime(2026, 1, 24, 9, 0, 0, tzinfo=KST)


class TestParseRelativeTime:
    """Tests for parse_relative_time function."""

    def test_parse_seconds(self):
        """Should parse seconds correctly."""
        result = parse_relative_time("30s", REFERENCE_TIME)
        expected = REFERENCE_TIME - timedelta(seconds=30)
        assert result == expected

    def test_parse_minutes(self):
        """Should parse minutes correctly."""
        result = parse_relative_time("45m", REFERENCE_TIME)
        expected = REFERENCE_TIME - timedelta(minutes=45)
        assert result == expected

    def test_parse_hours(self):
        """Should parse hours correctly."""
        result = parse_relative_time("5h", REFERENCE_TIME)
        expected = REFERENCE_TIME - timedelta(hours=5)
        assert result == expected

    def test_parse_uppercase(self):
        """Should handle uppercase unit letters."""
        result = parse_relative_time("3H", REFERENCE_TIME)
        expected = REFERENCE_TIME - timedelta(hours=3)
        assert result == expected

    def test_parse_with_whitespace(self):
        """Should handle leading/trailing whitespace."""
        result = parse_relative_time("  2h  ", REFERENCE_TIME)
        expected = REFERENCE_TIME - timedelta(hours=2)
        assert result == expected

    def test_parse_single_digit(self):
        """Should parse single digit values."""
        result = parse_relative_time("1h", REFERENCE_TIME)
        expected = REFERENCE_TIME - timedelta(hours=1)
        assert result == expected

    def test_parse_large_value(self):
        """Should parse large numeric values."""
        result = parse_relative_time("120m", REFERENCE_TIME)
        expected = REFERENCE_TIME - timedelta(minutes=120)
        assert result == expected

    def test_invalid_unit(self):
        """Should return None for invalid unit."""
        assert parse_relative_time("5d", REFERENCE_TIME) is None
        assert parse_relative_time("5w", REFERENCE_TIME) is None

    def test_invalid_format(self):
        """Should return None for invalid format."""
        assert parse_relative_time("abc", REFERENCE_TIME) is None
        assert parse_relative_time("", REFERENCE_TIME) is None
        assert parse_relative_time("5", REFERENCE_TIME) is None
        assert parse_relative_time("h5", REFERENCE_TIME) is None

    def test_date_format_returns_none(self):
        """Should return None for date formats (handled by other function)."""
        assert parse_relative_time("Jan 24", REFERENCE_TIME) is None


class TestParseDateString:
    """Tests for parse_date_string function."""

    def test_parse_date_this_year(self):
        """Should parse date without year as current year."""
        result = parse_date_string("Jan 20", REFERENCE_TIME)
        expected = datetime(2026, 1, 20, 0, 0, 0, tzinfo=KST)
        assert result == expected

    def test_parse_date_with_year(self):
        """Should parse date with explicit year."""
        result = parse_date_string("Jan 24, 2025", REFERENCE_TIME)
        expected = datetime(2025, 1, 24, 0, 0, 0, tzinfo=KST)
        assert result == expected

    def test_parse_date_with_year_no_comma(self):
        """Should parse date with year without comma."""
        result = parse_date_string("Dec 31 2025", REFERENCE_TIME)
        expected = datetime(2025, 12, 31, 0, 0, 0, tzinfo=KST)
        assert result == expected

    def test_parse_various_months(self):
        """Should parse all month abbreviations correctly."""
        months_data = [
            ("Jan 1", 1), ("Feb 15", 2), ("Mar 10", 3), ("Apr 5", 4),
            ("May 20", 5), ("Jun 30", 6), ("Jul 4", 7), ("Aug 15", 8),
            ("Sep 1", 9), ("Oct 31", 10), ("Nov 11", 11), ("Dec 25", 12),
        ]
        # Use a reference in middle of year to avoid year rollover issues
        mid_year_ref = datetime(2026, 7, 1, 12, 0, 0, tzinfo=KST)

        for date_str, expected_month in months_data:
            result = parse_date_string(date_str, mid_year_ref)
            assert result is not None, f"Failed to parse {date_str}"
            assert result.month == expected_month, f"Wrong month for {date_str}"

    def test_parse_case_insensitive(self):
        """Should handle different cases for month names."""
        result1 = parse_date_string("JAN 20", REFERENCE_TIME)
        result2 = parse_date_string("jan 20", REFERENCE_TIME)
        result3 = parse_date_string("Jan 20", REFERENCE_TIME)
        assert result1 == result2 == result3

    def test_future_date_rolls_back_year(self):
        """Should interpret future dates as last year."""
        # Reference is Jan 24, 2026; "Feb 1" would be in the future
        # So it should be interpreted as Feb 1, 2025
        result = parse_date_string("Feb 1", REFERENCE_TIME)
        expected = datetime(2025, 2, 1, 0, 0, 0, tzinfo=KST)
        assert result == expected

    def test_past_date_stays_current_year(self):
        """Should interpret past dates as current year."""
        # Reference is Jan 24, 2026; "Jan 20" is in the past
        result = parse_date_string("Jan 20", REFERENCE_TIME)
        expected = datetime(2026, 1, 20, 0, 0, 0, tzinfo=KST)
        assert result == expected

    def test_single_digit_day(self):
        """Should parse single digit day."""
        result = parse_date_string("Jan 5", REFERENCE_TIME)
        expected = datetime(2026, 1, 5, 0, 0, 0, tzinfo=KST)
        assert result == expected

    def test_invalid_month(self):
        """Should return None for invalid month abbreviation."""
        assert parse_date_string("Xyz 24", REFERENCE_TIME) is None
        assert parse_date_string("January 24", REFERENCE_TIME) is None

    def test_invalid_day(self):
        """Should return None for invalid day."""
        assert parse_date_string("Feb 30", REFERENCE_TIME) is None
        assert parse_date_string("Feb 31, 2026", REFERENCE_TIME) is None

    def test_invalid_format(self):
        """Should return None for invalid formats."""
        assert parse_date_string("2026-01-24", REFERENCE_TIME) is None
        assert parse_date_string("24 Jan", REFERENCE_TIME) is None
        assert parse_date_string("", REFERENCE_TIME) is None

    def test_relative_time_returns_none(self):
        """Should return None for relative time formats."""
        assert parse_date_string("5h", REFERENCE_TIME) is None


class TestParseXTime:
    """Tests for the unified parse_x_time function."""

    def test_parses_relative_time(self):
        """Should correctly parse relative time strings."""
        result = parse_x_time("3h", REFERENCE_TIME)
        expected = REFERENCE_TIME - timedelta(hours=3)
        assert result == expected

    def test_parses_date_this_year(self):
        """Should correctly parse date without year."""
        result = parse_x_time("Jan 20", REFERENCE_TIME)
        expected = datetime(2026, 1, 20, 0, 0, 0, tzinfo=KST)
        assert result == expected

    def test_parses_date_with_year(self):
        """Should correctly parse date with year."""
        result = parse_x_time("Dec 31, 2025", REFERENCE_TIME)
        expected = datetime(2025, 12, 31, 0, 0, 0, tzinfo=KST)
        assert result == expected

    def test_returns_none_for_invalid(self):
        """Should return None for unparseable strings."""
        assert parse_x_time("invalid", REFERENCE_TIME) is None
        assert parse_x_time("", REFERENCE_TIME) is None
        assert parse_x_time("   ", REFERENCE_TIME) is None

    def test_handles_none_input(self):
        """Should handle None-like empty input."""
        assert parse_x_time("", REFERENCE_TIME) is None


class TestIsWithinHours:
    """Tests for is_within_hours function - critical for 24h filter."""

    def test_recent_hours_within_24h(self):
        """Recent hour-based times should be within 24h."""
        assert is_within_hours("1h", 24, REFERENCE_TIME) is True
        assert is_within_hours("12h", 24, REFERENCE_TIME) is True
        assert is_within_hours("23h", 24, REFERENCE_TIME) is True

    def test_recent_minutes_within_24h(self):
        """Recent minute-based times should be within 24h."""
        assert is_within_hours("5m", 24, REFERENCE_TIME) is True
        assert is_within_hours("59m", 24, REFERENCE_TIME) is True

    def test_recent_seconds_within_24h(self):
        """Recent second-based times should be within 24h."""
        assert is_within_hours("30s", 24, REFERENCE_TIME) is True

    def test_exactly_24h_boundary(self):
        """Test the exact 24 hour boundary."""
        # 24h ago should still be within (>= cutoff)
        # Reference: 2026-01-24 09:00:00
        # 24h = cutoff at 2026-01-23 09:00:00
        # "Jan 23" at 00:00 is before cutoff, so should be False
        assert is_within_hours("Jan 23", 24, REFERENCE_TIME) is False

    def test_yesterday_date_outside_24h(self):
        """Date from yesterday (>24h ago) should be outside window."""
        # Reference: 2026-01-24 09:00:00 KST
        # Jan 22 is definitely more than 24h ago
        assert is_within_hours("Jan 22", 24, REFERENCE_TIME) is False

    def test_date_from_last_year(self):
        """Date from last year should be outside 24h window."""
        assert is_within_hours("Dec 31, 2025", 24, REFERENCE_TIME) is False

    def test_date_within_24h(self):
        """Date that falls within 24h window (same day)."""
        # Reference: 2026-01-24 09:00:00
        # Jan 24 at 00:00 is 9 hours ago, within 24h
        assert is_within_hours("Jan 24", 24, REFERENCE_TIME) is True

    def test_custom_window_hours(self):
        """Should respect custom hour window."""
        # 2h window - "3h" should be outside
        assert is_within_hours("3h", 2, REFERENCE_TIME) is False
        # 2h window - "1h" should be inside
        assert is_within_hours("1h", 2, REFERENCE_TIME) is True

    def test_invalid_time_returns_false(self):
        """Invalid time strings should return False (fail-safe)."""
        assert is_within_hours("invalid", 24, REFERENCE_TIME) is False
        assert is_within_hours("", 24, REFERENCE_TIME) is False
        assert is_within_hours("5d", 24, REFERENCE_TIME) is False


class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_year_boundary_december_to_january(self):
        """Should handle year boundary correctly."""
        # Reference at start of 2026
        jan_1_ref = datetime(2026, 1, 1, 12, 0, 0, tzinfo=KST)

        # "Dec 31" without year should be 2025
        result = parse_date_string("Dec 31", jan_1_ref)
        assert result is not None
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 31

    def test_leap_year_feb_29(self):
        """Should handle Feb 29 on leap years."""
        # 2024 was a leap year
        result = parse_date_string("Feb 29, 2024", REFERENCE_TIME)
        expected = datetime(2024, 2, 29, 0, 0, 0, tzinfo=KST)
        assert result == expected

    def test_leap_year_feb_29_invalid_year(self):
        """Should reject Feb 29 on non-leap years."""
        # 2025 is not a leap year
        result = parse_date_string("Feb 29, 2025", REFERENCE_TIME)
        assert result is None

    def test_whitespace_variations(self):
        """Should handle various whitespace patterns."""
        # The regex uses \s+ which handles multiple spaces gracefully
        result1 = parse_x_time("Jan  24", REFERENCE_TIME)  # double space
        expected = datetime(2026, 1, 24, 0, 0, 0, tzinfo=KST)
        assert result1 == expected  # Multiple spaces are handled

    def test_timezone_awareness(self):
        """Parsed times should be timezone-aware (KST)."""
        result = parse_x_time("5h", REFERENCE_TIME)
        assert result is not None
        assert result.tzinfo is not None
        assert result.tzinfo == KST

    def test_date_returns_start_of_day(self):
        """Date parsing should return start of day (00:00:00)."""
        result = parse_date_string("Jan 20", REFERENCE_TIME)
        assert result is not None
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0


class TestRealisticScenarios:
    """Tests simulating real X timeline scenarios."""

    def test_typical_timeline_mix(self):
        """Test a mix of timestamps typical on X timeline."""
        # Reference: 2026-01-24 09:00:00 KST
        test_cases = [
            ("2m", True),      # Just posted
            ("45m", True),     # Under an hour
            ("3h", True),      # Few hours ago
            ("18h", True),     # Yesterday evening
            ("Jan 24", True),  # Today (at 00:00, 9h ago)
            ("Jan 23", False), # Yesterday (at 00:00, 33h ago)
            ("Jan 20", False), # 4 days ago
            ("Dec 25, 2025", False),  # Last year
        ]

        for time_str, expected_within in test_cases:
            result = is_within_hours(time_str, 24, REFERENCE_TIME)
            assert result == expected_within, (
                f"Failed for '{time_str}': expected {expected_within}, got {result}"
            )

    def test_boundary_at_9am(self):
        """Test 24h boundary when running at 9:00 AM."""
        # If we run at 9:00 AM on Jan 24:
        # - Cutoff is 9:00 AM on Jan 23
        # - "Jan 23" (00:00) is 33 hours ago -> outside
        # - "Jan 24" (00:00) is 9 hours ago -> inside
        # - "23h" is 23 hours ago -> inside
        # - Any hour value < 24 should be inside

        assert is_within_hours("23h", 24, REFERENCE_TIME) is True
        assert is_within_hours("Jan 24", 24, REFERENCE_TIME) is True
        assert is_within_hours("Jan 23", 24, REFERENCE_TIME) is False

    def test_repost_scenario(self):
        """
        Test scenario: original post is old, but repost is recent.
        The repost time ("3h") should pass the filter,
        even if we also see the original's date ("Jan 15").
        """
        # Repost timestamp
        repost_time = "3h"
        assert is_within_hours(repost_time, 24, REFERENCE_TIME) is True

        # Original post timestamp (old)
        original_time = "Jan 15"
        assert is_within_hours(original_time, 24, REFERENCE_TIME) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

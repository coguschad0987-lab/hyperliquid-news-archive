"""
Time parser for X (Twitter) relative time strings.

X displays timestamps in various formats:
- Relative: "5s", "2m", "3h" (seconds, minutes, hours ago)
- Date this year: "Jan 24", "Feb 5"
- Date with year: "Jan 24, 2025", "Dec 31, 2024"

This module converts these strings to absolute datetime objects
for filtering posts within the last 24 hours.
"""

import re
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

# Korean Standard Time
KST = ZoneInfo("Asia/Seoul")

# Regex patterns for different time formats
RELATIVE_PATTERN = re.compile(r"^(\d+)([smh])$", re.IGNORECASE)
DATE_THIS_YEAR_PATTERN = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})$",
    re.IGNORECASE
)
DATE_WITH_YEAR_PATTERN = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})$",
    re.IGNORECASE
)

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12
}


def parse_relative_time(
    time_str: str,
    reference_time: Optional[datetime] = None
) -> Optional[datetime]:
    """
    Parse X's relative time string (e.g., '5h', '30m', '45s') to absolute datetime.

    Args:
        time_str: The time string from X (e.g., "5h", "30m", "45s")
        reference_time: Reference datetime for calculation (defaults to now in KST)

    Returns:
        Absolute datetime in KST, or None if parsing fails
    """
    if reference_time is None:
        reference_time = datetime.now(KST)

    time_str = time_str.strip()
    match = RELATIVE_PATTERN.match(time_str)

    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2).lower()

    if unit == "s":
        delta = timedelta(seconds=value)
    elif unit == "m":
        delta = timedelta(minutes=value)
    elif unit == "h":
        delta = timedelta(hours=value)
    else:
        return None

    return reference_time - delta


def parse_date_string(
    time_str: str,
    reference_time: Optional[datetime] = None
) -> Optional[datetime]:
    """
    Parse X's date string (e.g., 'Jan 24', 'Jan 24, 2025') to absolute datetime.

    For dates without year, assumes the most recent occurrence of that date.
    Returns datetime at 00:00:00 of that day in KST.

    Args:
        time_str: The date string from X (e.g., "Jan 24", "Jan 24, 2025")
        reference_time: Reference datetime for year inference (defaults to now in KST)

    Returns:
        Absolute datetime in KST at start of day, or None if parsing fails
    """
    if reference_time is None:
        reference_time = datetime.now(KST)

    time_str = time_str.strip()

    # Try date with year first (e.g., "Jan 24, 2025")
    match = DATE_WITH_YEAR_PATTERN.match(time_str)
    if match:
        month_str = match.group(1).lower()
        day = int(match.group(2))
        year = int(match.group(3))
        month = MONTH_MAP.get(month_str)

        if month is None:
            return None

        try:
            return datetime(year, month, day, tzinfo=KST)
        except ValueError:
            return None

    # Try date this year (e.g., "Jan 24")
    match = DATE_THIS_YEAR_PATTERN.match(time_str)
    if match:
        month_str = match.group(1).lower()
        day = int(match.group(2))
        month = MONTH_MAP.get(month_str)

        if month is None:
            return None

        # Determine the year: use current year, but if the date is in the future,
        # it likely refers to last year
        year = reference_time.year
        try:
            candidate = datetime(year, month, day, tzinfo=KST)
        except ValueError:
            return None

        # If the parsed date is in the future, assume it's from last year
        if candidate > reference_time:
            year -= 1
            try:
                candidate = datetime(year, month, day, tzinfo=KST)
            except ValueError:
                return None

        return candidate

    return None


def parse_x_time(
    time_str: str,
    reference_time: Optional[datetime] = None
) -> Optional[datetime]:
    """
    Parse any X timestamp format to absolute datetime.

    Supports:
    - Relative times: "5s", "30m", "3h"
    - Date this year: "Jan 24"
    - Date with year: "Jan 24, 2025"

    Args:
        time_str: The time string from X
        reference_time: Reference datetime for calculation (defaults to now in KST)

    Returns:
        Absolute datetime in KST, or None if parsing fails
    """
    if reference_time is None:
        reference_time = datetime.now(KST)

    if not time_str:
        return None

    time_str = time_str.strip()

    # Try relative time first (most common for recent posts)
    result = parse_relative_time(time_str, reference_time)
    if result is not None:
        return result

    # Try date formats
    result = parse_date_string(time_str, reference_time)
    if result is not None:
        return result

    return None


def is_within_hours(
    time_str: str,
    hours: int = 24,
    reference_time: Optional[datetime] = None
) -> bool:
    """
    Check if the given X time string represents a time within the last N hours.

    Args:
        time_str: The time string from X
        hours: Number of hours for the window (default: 24)
        reference_time: Reference datetime for calculation (defaults to now in KST)

    Returns:
        True if the time is within the window, False otherwise (including parse failures)
    """
    if reference_time is None:
        reference_time = datetime.now(KST)

    parsed_time = parse_x_time(time_str, reference_time)
    if parsed_time is None:
        return False

    cutoff = reference_time - timedelta(hours=hours)
    return parsed_time >= cutoff

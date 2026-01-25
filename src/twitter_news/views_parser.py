"""
Views parser for X (Twitter) view count strings.

X displays view counts in various formats:
- Plain numbers: "1200", "500"
- With commas: "1,200", "12,345"
- With K suffix: "1.2K", "15K"
- With M suffix: "1.5M", "10M"
- With B suffix: "1.2B" (rare but possible)

This module converts these strings to integers for ranking posts by views.
"""

import re
from typing import Optional

# Multipliers for suffixes
SUFFIX_MULTIPLIERS = {
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
}

# Pattern for abbreviated format: "1.2K", "15M", "1B"
ABBREVIATED_PATTERN = re.compile(
    r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*([KMBkmb])\s*$"
)

# Pattern for plain/comma-separated numbers: "1,200", "1200", "1.200" (EU format)
PLAIN_NUMBER_PATTERN = re.compile(
    r"^\s*([0-9]{1,3}(?:[,.\s][0-9]{3})*|[0-9]+)\s*$"
)


def parse_views(views_str: str) -> Optional[int]:
    """
    Parse X's view count string to an integer.

    Handles various formats:
    - "1.2K" -> 1200
    - "1,200" -> 1200
    - "1.5M" -> 1500000
    - "500" -> 500
    - "12,345" -> 12345
    - "1.234" (EU thousands) -> 1234

    Args:
        views_str: The view count string from X

    Returns:
        Integer view count, or None if parsing fails
    """
    if not views_str:
        return None

    views_str = views_str.strip()

    if not views_str:
        return None

    # Try abbreviated format first (most common on X: "1.2K", "5M")
    match = ABBREVIATED_PATTERN.match(views_str)
    if match:
        number_str = match.group(1)
        suffix = match.group(2).lower()

        # Replace comma with dot for decimal parsing
        number_str = number_str.replace(",", ".")

        try:
            number = float(number_str)
            multiplier = SUFFIX_MULTIPLIERS.get(suffix, 1)
            return int(number * multiplier)
        except ValueError:
            return None

    # Try plain number format
    match = PLAIN_NUMBER_PATTERN.match(views_str)
    if match:
        number_str = match.group(1)

        # Remove all separators (commas, dots used as thousands, spaces)
        # Determine if dots are decimal or thousands separators
        cleaned = _clean_number_string(number_str)

        try:
            return int(cleaned)
        except ValueError:
            return None

    return None


def _clean_number_string(number_str: str) -> str:
    """
    Clean a number string by removing thousand separators.

    Handles:
    - "1,200" (US format)
    - "1.200" (EU format, dot as thousands)
    - "1 200" (space as thousands)

    Args:
        number_str: Raw number string

    Returns:
        Cleaned string with only digits
    """
    # Remove spaces
    number_str = number_str.replace(" ", "")

    # Count dots and commas
    dot_count = number_str.count(".")
    comma_count = number_str.count(",")

    # If only commas exist, they're thousand separators
    if comma_count > 0 and dot_count == 0:
        return number_str.replace(",", "")

    # If only dots exist and there are multiple, they're thousand separators (EU)
    if dot_count > 0 and comma_count == 0:
        # Check if it looks like EU format (dots as thousands separators)
        # EU format: "1.234.567" - dots separate every 3 digits
        if dot_count >= 1:
            parts = number_str.split(".")
            # If all parts after first are exactly 3 digits, it's EU thousands
            if all(len(p) == 3 for p in parts[1:]):
                return number_str.replace(".", "")
        # Single dot could be decimal, but for views we expect integers
        # If pattern is like "1.234" and 234 is 3 digits, treat as EU thousands
        return number_str.replace(".", "")

    # Mixed format - unlikely, just remove everything non-digit
    return re.sub(r"[^0-9]", "", number_str)


def format_views(count: int) -> str:
    """
    Format an integer view count to abbreviated string (for display/logging).

    Args:
        count: Integer view count

    Returns:
        Abbreviated string like "1.2K", "1.5M"
    """
    if count >= 1_000_000_000:
        num = f"{count / 1_000_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{num}B"
    elif count >= 1_000_000:
        num = f"{count / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{num}M"
    elif count >= 1_000:
        num = f"{count / 1_000:.1f}".rstrip("0").rstrip(".")
        return f"{num}K"
    else:
        return str(count)

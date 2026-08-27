from __future__ import annotations

from datetime import datetime, timezone
import re

"""
Time presentation utility for desktop and UI surfaces.

Invariant:
- Storage truth remains UTC (ISO 8601 strings in database / backend).
- UI presentation converts real timestamps (completed_at, updated_at,
  reviewed_at, created_at) to the system local timezone for display.
- Pure calendar dates (e.g. next_due_at="YYYY-MM-DD", schedule_date)
  represent full calendar days rather than specific points in time, and are
  never shifted across timezones.
"""

_PURE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_pure_date(value: str) -> bool:
    """Return True if ``value`` matches a pure YYYY-MM-DD date string."""
    return bool(_PURE_DATE_RE.match(value.strip()))


def utc_to_local_datetime(value: str | datetime | None) -> datetime | None:
    """Parse a UTC timestamp (ISO string or datetime) and convert to local datetime.

    If ``value`` is empty, None, or a pure date string (YYYY-MM-DD), returns None.
    """
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text or is_pure_date(text):
            return None
        # Normalize trailing 'Z' to '+00:00' for standard ISO parser
        normalized = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            try:
                dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone()


def format_local_timestamp(
    utc_value: str | datetime | None,
    *,
    fmt: str = "%Y-%m-%d %H:%M:%S",
    empty_placeholder: str = "",
) -> str:
    """Convert a UTC timestamp to system local time formatted as a string.

    - Real timestamps (e.g. '2026-08-27T13:45:00+00:00') are parsed as UTC
      and rendered in local system time.
    - Pure dates (e.g. '2026-08-27') are returned as-is without shifting.
    - Empty or None values return ``empty_placeholder``.
    """
    if not utc_value:
        return empty_placeholder

    if isinstance(utc_value, str):
        text = utc_value.strip()
        if not text:
            return empty_placeholder
        if is_pure_date(text):
            return text

    local_dt = utc_to_local_datetime(utc_value)
    if local_dt is None:
        return str(utc_value)

    return local_dt.strftime(fmt)

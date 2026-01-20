from datetime import datetime, timezone
from typing import Any, Optional

def parse_iso(dt_str: str):
    """
    Parse an ISO8601 datetime string into a timezone-aware datetime.

    Replaces a trailing 'Z' with '+00:00' and returns a datetime object,
    or None if the input is falsy.

    Args:
        dt_str (str): The ISO8601 datetime string to parse.

    Returns:
        datetime | None: A timezone-aware datetime in UTC, or None if input is empty.
    """

    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def utc_now() -> datetime:
    """
    Get the current UTC time as a timezone-aware datetime.

    Returns:
        datetime: The current time with tzinfo set to UTC.
    """

    return datetime.now(timezone.utc)

def parse_datetime(value: Any) -> Optional[datetime]:
    """
    Parse multiple datetime representations into a UTC-aware datetime.

    Accepts ISO8601 strings (including 'Z' suffix), Unix timestamps
    (int/float), and datetime objects, normalizing all to UTC. Returns
    None if parsing fails or the value is unsupported.

    Args:
        value (Any): A datetime, ISO8601 string, timestamp, or None.

    Returns:
        Optional[datetime]: A timezone-aware datetime in UTC, or None on failure.
    """
    
    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        v = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            try:
                ts = float(v)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                return None
    return None

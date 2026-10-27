# TIME HELPERS: kept in own file so tests can replace clock
# One place for "what time is it", so tests can replace the clock with fixed times

from datetime import datetime, timezone


def utc_now_iso():
    # Now in UTC as ISO 8601 text, e.g. 2026-10-27T09:15:02.123Z
    # Millisecond precision keeps 'newest first' ordering reliable
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
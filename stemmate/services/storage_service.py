# 50 MB DATA BUDGET (QR-01). We measure the database FILE, as in P1's ADR-002 (installed program is not counted)

import os

from ..errors import ApiError


def used_bytes(db_path):
    # Size of db file plus its write-ahead log. In WAL mode, cent saves can still sit in the '-wal' file, so it must be counted
    total = 0
    for path in (db_path, db_path + "-wal"):
        if os.path.exists(path):
            total += os.path.getsize(path)
    return total


def usage(db_path, limit_bytes):
    used = used_bytes(db_path)
    percent = round(used / limit_bytes * 100, 1) if limit_bytes else 0.0
    return {"used_bytes": used, "limit_bytes": limit_bytes, "percent": percent}


def ensure_room(db_path, limit_bytes, incoming_bytes):
    # Raise 507 if saving `incoming_bytes` more would pass the limit.
    # Called BEFORE anything is written, so existing data stays untouched.
    if used_bytes(db_path) + incoming_bytes > limit_bytes:
        raise ApiError(507, "STORAGE_LIMIT",
                       "Storage on this device is full, so this change was not saved. "
                       "Free some space or ask your administrator for help.")
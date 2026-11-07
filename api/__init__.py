"""API routers for Telegram Query."""
from __future__ import annotations

import contextlib

import db


def parse_groups(raw: str | None) -> list[int]:
    """'123,-456' -> [123, -456]; ignores malformed entries."""
    out = []
    for part in (raw or "").split(","):
        part = part.strip()
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out


@contextlib.contextmanager
def open_db():
    """Yield a DB connection and always close it."""
    conn = db.get_db()
    try:
        yield conn
    finally:
        conn.close()

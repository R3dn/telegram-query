"""SQLite storage + FTS5 (trigram) search for Telegram messages.

Schema:
  chats      - tracked Telegram groups/channels + sync state
  messages   - one row per message, PK (chat_id, msg_id)
  messages_fts - FTS5 external-content index on messages.text_norm (trigram tokenizer)

Search semantics:
  - Each phrase is matched as a substring sequence (trigram) in normalized text.
  - require_all=True  -> phrases are ANDed (classic search box behaviour)
  - require_all=False -> phrases are ORed, rows matching more phrases rank higher (AI keyword variants)
"""
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.environ.get(
    "TG_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "messages.db"),
)

# ---------------------------------------------------------------------------
# Text normalization (mixed English/Arabic search quality)
# ---------------------------------------------------------------------------

_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")  # tashkeel + tatweel
_CHAR_MAP = str.maketrans({
    "آ": "ا", "أ": "ا", "إ": "ا", "ٱ": "ا",   # alef variants -> plain alef
    "ى": "ي", "ئ": "ي",                        # alef maqsura / ya-hamza -> ya
    "ؤ": "و",                                  # waw-hamza -> waw
    "ة": "ه",                                  # taa marbuta -> ha
})


def normalize_text(text: str) -> str:
    """Lowercase, strip Arabic diacritics, unify alef/ya variants, collapse punctuation."""
    if not text:
        return ""
    t = text.lower()
    t = _DIACRITICS.sub("", t)
    t = t.translate(_CHAR_MAP)
    # Collapse any non-word char runs (incl. Arabic punctuation) into one space.
    t = re.sub(r"[^\w\u0600-\u06FF]+", " ", t)
    return t.strip()


def fts_quote(phrase: str) -> str:
    """Escape a phrase for use as one FTS5 string term."""
    return '"' + phrase.replace('"', '""') + '"'


# ---------------------------------------------------------------------------
# DB init
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id     INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    username    TEXT,
    kind        TEXT NOT NULL DEFAULT 'group',   -- group | channel
    last_msg_id INTEGER NOT NULL DEFAULT 0,
    last_synced TEXT,
    tracked     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS messages (
    chat_id     INTEGER NOT NULL,
    msg_id      INTEGER NOT NULL,
    date        TEXT NOT NULL,          -- ISO 8601 UTC
    sender_id   INTEGER,
    sender_name TEXT,
    text        TEXT NOT NULL DEFAULT '',
    text_norm   TEXT NOT NULL DEFAULT '',
    has_media   INTEGER NOT NULL DEFAULT 0,
    edited      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, msg_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date);
CREATE INDEX IF NOT EXISTS idx_messages_chat_date ON messages(chat_id, date);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    text_norm,
    content='messages',
    content_rowid='rowid',
    tokenize='trigram'
);
"""


def get_db(path: str = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def init_db(path: str = None):
    conn = get_db(path)
    conn.close()


# ---------------------------------------------------------------------------
# Write helpers (used by sync.py)
# ---------------------------------------------------------------------------

def upsert_chat(conn, chat_id, title, username=None, kind="group", tracked=1):
    conn.execute(
        """INSERT INTO chats (chat_id, title, username, kind, tracked)
           VALUES (?,?,?,?,?)
           ON CONFLICT(chat_id) DO UPDATE SET
             title=excluded.title, username=excluded.username,
             kind=excluded.kind, tracked=excluded.tracked""",
        (chat_id, title, username, kind, tracked),
    )


def get_tracked_chats(conn):
    return conn.execute("SELECT * FROM chats WHERE tracked=1 ORDER BY title").fetchall()


def get_sync_state(conn, chat_id):
    row = conn.execute(
        "SELECT last_msg_id, last_synced FROM chats WHERE chat_id=?", (chat_id,)
    ).fetchone()
    return (row["last_msg_id"], row["last_synced"]) if row else (0, None)


def update_sync_state(conn, chat_id, last_msg_id):
    conn.execute(
        "UPDATE chats SET last_msg_id=?, last_synced=? WHERE chat_id=?",
        (last_msg_id, datetime.now(timezone.utc).isoformat(), chat_id),
    )


def upsert_message(conn, chat_id, msg_id, date, sender_id, sender_name,
                   text, has_media=0, edited=0):
    conn.execute(
        """INSERT INTO messages (chat_id, msg_id, date, sender_id, sender_name,
                                 text, text_norm, has_media, edited)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(chat_id, msg_id) DO UPDATE SET
             date=excluded.date, sender_id=excluded.sender_id,
             sender_name=excluded.sender_name, text=excluded.text,
             text_norm=excluded.text_norm, has_media=excluded.has_media,
             edited=excluded.edited""",
        (chat_id, msg_id, date, sender_id, sender_name, text,
         normalize_text(text), has_media, edited),
    )


def reindex_fts(conn):
    """Rebuild the FTS index (external-content tables need explicit refresh)."""
    conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _expand_date(d, end=False):
    """YYYY-MM-DD -> full-day ISO bounds for string comparison against ISO dates."""
    if not d:
        return d
    d = d.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        return d + ("T23:59:59" if end else "T00:00:00")
    return d


def search(conn, phrases, chat_ids=None, sender=None,
          date_from=None, date_to=None, require_all=True, limit=200):
    """Search normalized text. Returns list of dict rows, newest first.

    phrases      - list of raw strings (will be normalized)
    require_all  - True: AND all phrases. False: OR, more matches = higher rank.
    """
    # Trigram tokenizer requires >= 3 chars per phrase; drop shorter ones.
    norm = [normalize_text(p) for p in phrases
            if len(normalize_text(p).replace(" ", "")) >= 3]
    if not norm:
        return []

    if require_all:
        match_expr = " AND ".join(fts_quote(p) for p in norm)
    else:
        match_expr = " OR ".join(fts_quote(p) for p in norm)

    query = f"""
        SELECT m.chat_id, m.msg_id, m.date, m.sender_id, m.sender_name,
               m.text, m.has_media, m.edited, c.title AS chat_title,
               bm25(messages_fts) AS rank
        FROM messages_fts
        JOIN messages m ON m.rowid = messages_fts.rowid
        JOIN chats c   ON c.chat_id = m.chat_id
        WHERE messages_fts MATCH ?
    """
    params = [match_expr]

    if chat_ids:
        marks = ",".join("?" * len(chat_ids))
        query += f" AND m.chat_id IN ({marks})"
        params.extend(chat_ids)
    if sender:
        query += " AND m.sender_name LIKE ?"
        params.append(f"%{sender}%")
    if date_from:
        query += " AND m.date >= ?"
        params.append(_expand_date(date_from))
    if date_to:
        query += " AND m.date <= ?"
        params.append(_expand_date(date_to, end=True))

    query += " ORDER BY rank LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def recent(conn, chat_ids=None, days=7, limit=500):
    """Recent messages, newest first - used as AI fallback context."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    query = """
        SELECT m.chat_id, m.msg_id, m.date, m.sender_id, m.sender_name,
               m.text, m.has_media, m.edited, c.title AS chat_title
        FROM messages m JOIN chats c ON c.chat_id = m.chat_id
        WHERE m.date >= ?
    """
    params = [since]
    if chat_ids:
        marks = ",".join("?" * len(chat_ids))
        query += f" AND m.chat_id IN ({marks})"
        params.extend(chat_ids)
    query += " ORDER BY m.date DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def stats(conn):
    n_msgs = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
    n_chats = conn.execute(
        "SELECT COUNT(*) c FROM chats WHERE tracked=1").fetchone()["c"]
    last = conn.execute("SELECT MAX(date) d FROM messages").fetchone()["d"]
    return {"messages": n_msgs, "chats": n_chats, "last_message": last}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    print(f"Initialized {DB_PATH}")

"""SQLite storage + FTS5 (trigram) search for Telegram messages.

Schema:
  chats         - tracked Telegram groups/channels + sync state + backfill checkpoints
  messages      - one row per message, PK (chat_id, msg_id)
  messages_fts  - FTS5 external-content index on messages.text_norm (trigram)
  app_settings  - key/value app state (scheduler, reindex flags, ...)
  saved_searches- named search + filter sets (v0.4)
  bookmarks     - starred messages + private notes, PK (chat_id, msg_id) (v0.4)
  schema_meta   - migration bookkeeping (schema version)

Search semantics:
  - Each phrase is matched as a substring sequence (trigram) in normalized text.
  - require_all=True  -> phrases are ANDed (classic search box behaviour)
  - require_all=False -> phrases are ORed, rows matching more phrases rank higher
"""
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config

DB_PATH = config.settings.db_path  # default location; tests pass explicit paths

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
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_ELONGATION = re.compile(r"(.)\1{2,}")          # 3+ repeats of one char
_LATIN_WORD = re.compile(r"[a-z]")
_DIGIT_RUN = re.compile(r"\d{2,}")               # prices / promo codes

# Arabizi digits used as letters (single digits inside Latin words only).
_ARABIZI_DIGITS = {"2": "ا", "3": "ع", "5": "خ",
                   "6": "ط", "7": "ح", "8": "ق", "9": "ص"}

# Gulf-dialect -> common form. Keys/values are stored raw and folded at import
# time so the map always matches already-normalized text. Replace entirely
# with env TGQ_DIALECT_MAP='{"from":"to",...}' (JSON).
_DIALECT_MAP_RAW = {
    "شلون": "كيف",
    "وين": "اين",
    "فين": "اين",
    "شنو": "ايش",
    "بكير": "مبكر",
    "الحين": "الان",
    "هالحين": "الان",
    "برضو": "ايضا",
    "برضه": "ايضا",
    "اكيد": "مؤكد",
}


def _fold(text: str) -> str:
    """Standard (v0.3) normalization pipeline, without the extended extras."""
    t = text.lower()
    t = _DIACRITICS.sub("", t)
    t = t.translate(_CHAR_MAP)
    t = re.sub(r"[^\w\u0600-\u06FF]+", " ", t)
    return t.strip()


def _load_dialect_map() -> dict[str, str]:
    raw = _DIALECT_MAP_RAW
    env = os.environ.get("TGQ_DIALECT_MAP", "").strip()
    if env:
        try:
            parsed = json.loads(env)
            raw = {str(k): str(v) for k, v in parsed.items()}
        except (ValueError, AttributeError):
            pass  # malformed override -> keep defaults
    # fold both sides so the map matches already-normalized words
    return {_fold(k): _fold(v) for k, v in raw.items() if k and v}


_DIALECT_MAP = _load_dialect_map()


def normalize_text(text: str) -> str:
    """Normalize for the FTS index and queries.

    Level "standard" (env NORMALIZATION) reproduces v0.3 exactly. Level
    "extended" (default) adds: Arabic-Indic digit folding, elongation
    collapse, Arabizi single-digit folding inside Latin words, and the Gulf
    dialect map. Deterministic; the original text is never modified - only
    this normalized copy is used for search.
    """
    if not text:
        return ""
    t = _fold(text)
    if config.settings.normalization_level != "extended":
        return t
    words = t.translate(_ARABIC_DIGITS).split()
    out = []
    for w in words:
        if len(w) > 2 and not w.isdigit():
            w = _ELONGATION.sub(r"\1", w)      # هااااي -> هاي (never digits)
        if _LATIN_WORD.search(w) and not _DIGIT_RUN.search(w):
            w = "".join(_ARABIZI_DIGITS.get(c, c) for c in w)
        w = _DIALECT_MAP.get(w, w)
        out.append(w)
    return " ".join(out)


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
    tracked     INTEGER NOT NULL DEFAULT 1,
    backfill_floor INTEGER NOT NULL DEFAULT 0    -- >0: paused backfill, resume below this id
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
    reply_to    INTEGER,                -- msg_id this replies to (v0.5)
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

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS saved_searches (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    q            TEXT NOT NULL DEFAULT '',
    chat_ids     TEXT NOT NULL DEFAULT '[]',  -- JSON array of group ids
    sender       TEXT NOT NULL DEFAULT '',
    media        TEXT NOT NULL DEFAULT '',    -- '' | '0' | '1'
    date_from    TEXT NOT NULL DEFAULT '',
    date_to      TEXT NOT NULL DEFAULT '',
    sort         TEXT NOT NULL DEFAULT 'desc',
    created_at   TEXT NOT NULL,
    last_used_at TEXT
);

CREATE TABLE IF NOT EXISTS bookmarks (
    chat_id    INTEGER NOT NULL,
    msg_id     INTEGER NOT NULL,
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (chat_id, msg_id),
    FOREIGN KEY (chat_id, msg_id) REFERENCES messages(chat_id, msg_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_bookmarks_updated ON bookmarks(updated_at);

-- v0.5: knowledge layer ------------------------------------------------
CREATE TABLE IF NOT EXISTS deals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    category     TEXT,
    vendor       TEXT,
    discount_pct REAL,
    price        REAL,
    currency     TEXT,
    promo_code   TEXT,
    eligibility  TEXT,
    geo          TEXT,
    valid_from   TEXT,
    expires      TEXT,
    status       TEXT NOT NULL DEFAULT 'unknown',  -- extracted: active|expired|upcoming|unknown
    user_status  TEXT,                             -- human: confirmed|dismissed (overrides UI)
    confidence   REAL,
    fingerprint  TEXT NOT NULL DEFAULT '',
    prompt_version TEXT NOT NULL DEFAULT '',
    model        TEXT NOT NULL DEFAULT '',
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deal_sources (
    deal_id  INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    chat_id  INTEGER NOT NULL,
    msg_id   INTEGER NOT NULL,
    PRIMARY KEY (deal_id, chat_id, msg_id),
    FOREIGN KEY (chat_id, msg_id) REFERENCES messages(chat_id, msg_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_deals_last_seen ON deals(last_seen);
CREATE INDEX IF NOT EXISTS idx_deal_sources_msg ON deal_sources(chat_id, msg_id);

CREATE TABLE IF NOT EXISTS briefs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    question   TEXT NOT NULL,
    chat_ids   TEXT NOT NULL DEFAULT '[]',
    date_from  TEXT,
    date_to    TEXT,
    notes      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS brief_versions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    brief_id       INTEGER NOT NULL REFERENCES briefs(id) ON DELETE CASCADE,
    version        INTEGER NOT NULL,
    answer_md      TEXT NOT NULL,
    keywords       TEXT NOT NULL DEFAULT '[]',
    prompt_version TEXT NOT NULL,
    model          TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    UNIQUE (brief_id, version)
);
CREATE TABLE IF NOT EXISTS brief_citations (
    version_id INTEGER NOT NULL REFERENCES brief_versions(id) ON DELETE CASCADE,
    idx        INTEGER NOT NULL,
    chat_id    INTEGER NOT NULL,
    msg_id     INTEGER NOT NULL,
    excerpt    TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (version_id, idx),
    FOREIGN KEY (chat_id, msg_id) REFERENCES messages(chat_id, msg_id)
        ON DELETE CASCADE
);

-- v0.5: AI task infrastructure ----------------------------------------
CREATE TABLE IF NOT EXISTS ai_task_cache (
    task           TEXT NOT NULL,
    scope_hash     TEXT NOT NULL,
    model          TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    fingerprint    TEXT NOT NULL,
    result         TEXT NOT NULL,          -- JSON payload
    created_at     TEXT NOT NULL,
    PRIMARY KEY (task, scope_hash, model, prompt_version, fingerprint)
);
CREATE TABLE IF NOT EXISTS ai_usage (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task       TEXT NOT NULL,
    requests   INTEGER NOT NULL DEFAULT 1,
    tokens_in  INTEGER,
    tokens_out INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_usage_created ON ai_usage(created_at);
CREATE TABLE IF NOT EXISTS faq_clusters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question        TEXT NOT NULL,               -- display form
    norm_key        TEXT NOT NULL UNIQUE,        -- normalized signature
    answer_md       TEXT,                        -- proposed answer (markdown)
    status          TEXT NOT NULL DEFAULT 'candidate',
    frequency       INTEGER NOT NULL DEFAULT 0,
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    prompt_version  TEXT,
    model           TEXT,
    source_questions TEXT NOT NULL DEFAULT '[]', -- JSON [{chat_id,msg_id,date}]
    source_answers   TEXT NOT NULL DEFAULT '[]',
    updated_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlists (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    terms         TEXT NOT NULL DEFAULT '[]',    -- JSON list
    exclude_terms TEXT NOT NULL DEFAULT '[]',
    chat_ids      TEXT NOT NULL DEFAULT '[]',    -- [] = all tracked groups
    enabled       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    last_match_at TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    chat_id      INTEGER NOT NULL,
    msg_id       INTEGER NOT NULL,
    matched_term TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    read         INTEGER NOT NULL DEFAULT 0,
    archived     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (watchlist_id, chat_id, msg_id),
    FOREIGN KEY (chat_id, msg_id) REFERENCES messages(chat_id, msg_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_alerts_state ON alerts(watchlist_id, read, archived);
CREATE TABLE IF NOT EXISTS watch_watermarks (
    chat_id     INTEGER PRIMARY KEY,
    last_msg_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS digest_schedules (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    frequency  TEXT NOT NULL DEFAULT 'daily',   -- daily | weekly
    chat_ids   TEXT NOT NULL DEFAULT '[]',
    hour       INTEGER NOT NULL DEFAULT 9,      -- UTC generation hour
    weekday    INTEGER NOT NULL DEFAULT 6,     -- 0=Mon..6=Sun (weekly)
    language   TEXT NOT NULL DEFAULT 'auto',    -- auto | en | ar
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_run   TEXT
);
CREATE TABLE IF NOT EXISTS digests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id  INTEGER REFERENCES digest_schedules(id) ON DELETE SET NULL,
    period_start TEXT NOT NULL,
    period_end   TEXT NOT NULL,
    content_md  TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model        TEXT NOT NULL,
    fingerprint  TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS digest_citations (
    digest_id INTEGER NOT NULL REFERENCES digests(id) ON DELETE CASCADE,
    idx       INTEGER NOT NULL,
    chat_id   INTEGER NOT NULL,
    msg_id    INTEGER NOT NULL,
    excerpt   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (digest_id, idx),
    FOREIGN KEY (chat_id, msg_id) REFERENCES messages(chat_id, msg_id)
        ON DELETE CASCADE
);

-- v0.7: discovery layer --------------------------------------------------
-- Daily per-chat term counts over normalized text (unigrams + bigrams).
-- Built incrementally above a watermark; powers trending-topic burst
-- scoring deterministically (no AI involved).
CREATE TABLE IF NOT EXISTS term_daily (
    chat_id INTEGER NOT NULL,
    day     TEXT NOT NULL,             -- UTC YYYY-MM-DD
    term    TEXT NOT NULL,             -- normalized token or "a b" bigram
    n       INTEGER NOT NULL DEFAULT 0, -- messages containing the term
    PRIMARY KEY (chat_id, day, term)
);
CREATE INDEX IF NOT EXISTS idx_term_daily_day ON term_daily(day);
CREATE INDEX IF NOT EXISTS idx_term_daily_term ON term_daily(term, day);

-- Named entities (brands, products, orgs, projects, places, events -
-- NEVER individual people). Gazetteer entries are matched against
-- text_norm deterministically; every mention keeps its source message.
CREATE TABLE IF NOT EXISTS entities (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    norm_name  TEXT NOT NULL UNIQUE,   -- db.normalize_text(name)
    kind       TEXT NOT NULL DEFAULT 'other',
    aliases    TEXT NOT NULL DEFAULT '[]',  -- JSON normalized extra names
    source     TEXT NOT NULL DEFAULT 'auto', -- deals | manual | llm
    ignored    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entity_mentions (
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    chat_id   INTEGER NOT NULL,
    msg_id    INTEGER NOT NULL,
    date      TEXT NOT NULL,
    PRIMARY KEY (entity_id, chat_id, msg_id),
    FOREIGN KEY (chat_id, msg_id) REFERENCES messages(chat_id, msg_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_date ON entity_mentions(entity_id, date);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_msg ON entity_mentions(chat_id, msg_id);

-- Unanswered-questions radar: questions detected with no substantive
-- reply. Human-controlled status; replies arrive incrementally.
CREATE TABLE IF NOT EXISTS open_questions (
    chat_id     INTEGER NOT NULL,
    msg_id      INTEGER NOT NULL,
    text        TEXT NOT NULL,
    asked_at    TEXT NOT NULL,
    replies     INTEGER NOT NULL DEFAULT 0,
    followers   INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'open',  -- open | answered | ignored
    answered_by INTEGER,                       -- best-effort msg pointer
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (chat_id, msg_id),
    FOREIGN KEY (chat_id, msg_id) REFERENCES messages(chat_id, msg_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_open_questions_status
    ON open_questions(status, asked_at);

-- v0.8: decisions & commitments ------------------------------------------
-- Structured decision/commitment records extracted from conversations.
-- Same contract as deals: typed rows, per-row citations verified against
-- the archive, computed status, human confirm/dismiss gate.
CREATE TABLE IF NOT EXISTS decisions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,               -- decision text (source language)
    detail       TEXT NOT NULL DEFAULT '',    -- one-line context/scope
    kind         TEXT,                        -- decision | commitment | plan
    owner        TEXT,                        -- person/team that owns it
    due_date     TEXT,                        -- YYYY-MM-DD or NULL
    status       TEXT NOT NULL DEFAULT 'proposed', -- extracted judgment
    user_status  TEXT,                        -- human: confirmed|dismissed
    confidence   REAL,
    fingerprint  TEXT NOT NULL DEFAULT '',
    prompt_version TEXT NOT NULL DEFAULT '',
    model        TEXT NOT NULL DEFAULT '',
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision_sources (
    decision_id INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    chat_id     INTEGER NOT NULL,
    msg_id      INTEGER NOT NULL,
    PRIMARY KEY (decision_id, chat_id, msg_id),
    FOREIGN KEY (chat_id, msg_id) REFERENCES messages(chat_id, msg_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_decisions_last_seen ON decisions(last_seen);
CREATE INDEX IF NOT EXISTS idx_decisions_due ON decisions(due_date);
CREATE INDEX IF NOT EXISTS idx_decision_sources_msg
    ON decision_sources(chat_id, msg_id);

-- v0.8.1: deterministic follow-up tracking --------------------------------
-- Newer messages that discuss an open decision (>= 2 title keywords),
-- found incrementally above each decision's per-chat watermark (max
-- msg_id over its sources + stored follow-ups). Pure keyword matching
-- over text_norm - never AI, never a full-archive scan.
CREATE TABLE IF NOT EXISTS decision_followups (
    decision_id   INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    chat_id       INTEGER NOT NULL,
    msg_id        INTEGER NOT NULL,
    matched_terms TEXT NOT NULL DEFAULT '[]',   -- JSON keywords that hit
    created_at    TEXT NOT NULL,
    PRIMARY KEY (decision_id, chat_id, msg_id),
    FOREIGN KEY (chat_id, msg_id) REFERENCES messages(chat_id, msg_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_decision_followups_msg
    ON decision_followups(chat_id, msg_id);
"""


SCHEMA_VERSION = 8


def _migrate(conn):
    """Versioned, idempotent, additive-only migrations. Never destructive."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key='version'").fetchone()
    current = int(row["value"]) if row else 1
    if current < 2:
        # v2: backfill checkpoint column (no-op when already present)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(chats)")]
        if "backfill_floor" not in cols:
            conn.execute("ALTER TABLE chats ADD COLUMN backfill_floor "
                         "INTEGER NOT NULL DEFAULT 0")
        current = 2
    if current < 3:
        # v3: app_settings / saved_searches / bookmarks (created by SCHEMA
        # for fresh databases; this branch bumps existing ones). Extended
        # normalization changed text_norm semantics -> flag a one-time
        # background reindex for archives that already have messages.
        n = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
        if n and config.settings.normalization_level == "extended":
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) "
                "VALUES ('needs_reindex', '1')")
        current = 3
    if current < 4:
        # v4: knowledge layer tables (deals/briefs/ai cache+usage, created
        # by SCHEMA) + messages.reply_to capture for context expansion.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(messages)")]
        if "reply_to" not in cols:
            conn.execute("ALTER TABLE messages ADD COLUMN reply_to INTEGER")
        current = 4
    if current < 5:
        # v5: monitoring layer (watchlists/alerts/digests/faqs, created by
        # SCHEMA). No data transforms needed.
        current = 5
    if current < 6:
        # v6: discovery layer (term_daily/entities/entity_mentions/
        # open_questions, created by SCHEMA) + per-model usage recording.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(ai_usage)")]
        if "model" not in cols:
            conn.execute("ALTER TABLE ai_usage ADD COLUMN model "
                         "TEXT NOT NULL DEFAULT ''")
        # Existing archives need a one-time discovery backfill (visible
        # job, queued by app.py on the next start; idempotent).
        n = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
        if n:
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) "
                "VALUES ('needs_discover_backfill', '1')")
        current = 6
    if current < 7:
        # v7: decisions layer (decisions/decision_sources, created by
        # SCHEMA for fresh and existing databases). No data transforms.
        current = 7
    if current < 8:
        # v8: deterministic decision follow-ups (decision_followups,
        # created by SCHEMA). No data transforms.
        current = 8
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
        (str(current),))


def get_db(path: str = None) -> sqlite3.Connection:
    p = Path(path) if path else DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=20000")
    conn.execute("PRAGMA foreign_keys=ON")
    if str(p) not in _INITIALIZED:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
        _INITIALIZED.add(str(p))
    return conn


_INITIALIZED = set()


def init_db(path: str = None):
    conn = get_db(path)
    conn.close()


# ---------------------------------------------------------------------------
# App settings (scheduler state, reindex flags, future feature settings)
# ---------------------------------------------------------------------------

def get_setting(conn, key: str, default: str | None = None) -> str | None:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key: str, value: str):
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)))


# ---------------------------------------------------------------------------
# Telegram deep links
# ---------------------------------------------------------------------------

def message_link(chat_id: int | None, username: str | None,
                 msg_id: int) -> str | None:
    """External link to the original message, when Telegram provides one.

    - Public groups/channels: https://t.me/<username>/<msg_id>
    - Supergroups/channels (no username): https://t.me/c/<id>/<msg_id>
      (only works for members - that is Telegram's rule, not ours)
    - Basic groups / DMs: no per-message links exist.
    Never fabricates a URL: returns None when no usable link exists.
    """
    if username and msg_id is not None:
        return f"https://t.me/{username}/{msg_id}"
    if chat_id is not None and msg_id is not None and \
            chat_id <= -1000000000000:  # Telethon supergroup/channel mark
        c_id = -(chat_id + 1000000000000)
        if c_id > 0:
            return f"https://t.me/c/{c_id}/{msg_id}"
    return None


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
        "SELECT last_msg_id, last_synced, backfill_floor FROM chats "
        "WHERE chat_id=?", (chat_id,),
    ).fetchone()
    if row:
        return (row["last_msg_id"], row["last_synced"], row["backfill_floor"])
    return (0, None, 0)


def set_backfill_progress(conn, chat_id, last_msg_id, floor):
    """Checkpoint backfill state. floor=0 means the backfill is complete."""
    conn.execute(
        "UPDATE chats SET last_msg_id=?, backfill_floor=?, last_synced=? "
        "WHERE chat_id=?",
        (last_msg_id, floor, datetime.now(timezone.utc).isoformat(), chat_id),
    )


def update_sync_state(conn, chat_id, last_msg_id):
    conn.execute(
        "UPDATE chats SET last_msg_id=?, last_synced=? WHERE chat_id=?",
        (last_msg_id, datetime.now(timezone.utc).isoformat(), chat_id),
    )


def upsert_message(conn, chat_id, msg_id, date, sender_id, sender_name,
                   text, has_media=0, edited=0, reply_to=None):
    """Insert/update one message, keeping the FTS index in sync incrementally
    (never a full rebuild - external-content FTS5 supports row-level upkeep)."""
    norm = normalize_text(text)
    row = conn.execute(
        "SELECT rowid, text_norm FROM messages WHERE chat_id=? AND msg_id=?",
        (chat_id, msg_id),
    ).fetchone()
    if row is not None:  # update: drop the old index entry, then re-add
        conn.execute(
            "INSERT INTO messages_fts(messages_fts, rowid, text_norm) "
            "VALUES('delete', ?, ?)",
            (row["rowid"], row["text_norm"] or ""),
        )
    cur = conn.execute(
        """INSERT INTO messages (chat_id, msg_id, date, sender_id, sender_name,
                                 text, text_norm, has_media, edited, reply_to)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(chat_id, msg_id) DO UPDATE SET
             date=excluded.date, sender_id=excluded.sender_id,
             sender_name=excluded.sender_name, text=excluded.text,
             text_norm=excluded.text_norm, has_media=excluded.has_media,
             edited=excluded.edited, reply_to=excluded.reply_to""",
        (chat_id, msg_id, date, sender_id, sender_name, text,
         norm, has_media, edited, reply_to),
    )
    conn.execute(
        "INSERT INTO messages_fts(rowid, text_norm) VALUES (?, ?)",
        (row["rowid"] if row is not None else cur.lastrowid, norm),
    )


def reindex_fts(conn):
    """Manual full FTS rebuild - not used by sync anymore (upsert_message
    maintains the index incrementally). Keep for repairs/migrations."""
    conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")


def delete_chats_messages(conn, chat_ids):
    """Permanently delete the archived messages of the given chats and
    reset their sync state (so a re-track re-backfills from scratch).
    Bookmarks of those messages are removed as well (the FK cascades, this
    is belt-and-suspenders for connections without the pragma).
    Rebuilds the FTS index once at the end. Destructive - used only by the
    explicit 'untrack & delete' action."""
    for cid in chat_ids:
        conn.execute(
            "DELETE FROM bookmarks WHERE chat_id=?", (cid,))
        conn.execute("DELETE FROM messages WHERE chat_id=?", (cid,))
        conn.execute(
            "UPDATE chats SET last_msg_id=0, backfill_floor=0 WHERE chat_id=?",
            (cid,))
    reindex_fts(conn)


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
          date_from=None, date_to=None, require_all=True, limit=200,
          bookmarked=None, min_msg_id=None):
    """Search normalized text. Returns list of dict rows, newest first.

    phrases      - list of raw strings (will be normalized)
    require_all  - True: AND all phrases. False: OR, more matches = higher rank.
    bookmarked   - True: only bookmarked messages. False/None: all messages.
    min_msg_id   - only messages with msg_id > this (incremental pipelines).
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

    query = """
        SELECT m.chat_id, m.msg_id, m.date, m.sender_id, m.sender_name,
               m.text, m.has_media, m.edited, c.title AS chat_title,
               c.username AS chat_username,
               (b.chat_id IS NOT NULL) AS bookmarked, b.note AS bookmark_note,
               bm25(messages_fts) AS rank
        FROM messages_fts
        JOIN messages m ON m.rowid = messages_fts.rowid
        JOIN chats c   ON c.chat_id = m.chat_id
        LEFT JOIN bookmarks b
               ON b.chat_id = m.chat_id AND b.msg_id = m.msg_id
        WHERE messages_fts MATCH ? AND c.tracked = 1
    """
    params = [match_expr]

    if chat_ids:
        marks = ",".join("?" * len(chat_ids))
        query += f" AND m.chat_id IN ({marks})"
        params.extend(chat_ids)
    if sender:
        query += " AND m.sender_name = ?"
        params.append(sender)
    if date_from:
        query += " AND m.date >= ?"
        params.append(_expand_date(date_from))
    if date_to:
        query += " AND m.date <= ?"
        params.append(_expand_date(date_to, end=True))
    if bookmarked:
        query += " AND b.chat_id IS NOT NULL"
    if min_msg_id is not None:
        query += " AND m.msg_id > ?"
        params.append(int(min_msg_id))

    query += " ORDER BY rank LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def browse(conn, chat_ids=None, sender=None, date_from=None, date_to=None,
           media=None, cursor=None, limit=50, sort="desc", bookmarked=None):
    """Keyset-paginated chronological feed across tracked chats.

    cursor - "date|chat_id|msg_id" of the last row of the previous page
              (returned as next_cursor). Ignored if malformed.
    sort   - "desc" (newest first) or "asc" (oldest first).
    bookmarked - True: only bookmarked messages. False/None: all messages.
    Returns (rows, next_cursor, has_more).
    """
    desc = sort != "asc"
    query = """
        SELECT m.chat_id, m.msg_id, m.date, m.sender_id, m.sender_name,
               m.text, m.text_norm, m.has_media, m.edited,
               c.title AS chat_title,
               c.username AS chat_username,
               (b.chat_id IS NOT NULL) AS bookmarked, b.note AS bookmark_note
        FROM messages m JOIN chats c ON c.chat_id = m.chat_id
        LEFT JOIN bookmarks b
               ON b.chat_id = m.chat_id AND b.msg_id = m.msg_id
        WHERE c.tracked = 1
    """
    params = []
    if chat_ids:
        marks = ",".join("?" * len(chat_ids))
        query += f" AND m.chat_id IN ({marks})"
        params.extend(chat_ids)
    if sender:
        query += " AND m.sender_name = ?"
        params.append(sender)
    if date_from:
        query += " AND m.date >= ?"
        params.append(_expand_date(date_from))
    if date_to:
        query += " AND m.date <= ?"
        params.append(_expand_date(date_to, end=True))
    if media is not None:
        query += " AND m.has_media = ?"
        params.append(1 if media else 0)
    if bookmarked:
        query += " AND b.chat_id IS NOT NULL"
    if cursor:
        try:
            c_date, c_chat, c_msg = cursor.split("|", 2)
            c_chat, c_msg = int(c_chat), int(c_msg)
        except ValueError:
            c_date = None
        if c_date is not None:
            if desc:
                query += (" AND (m.date < ? OR (m.date = ? AND (m.chat_id < ?"
                          " OR (m.chat_id = ? AND m.msg_id < ?))))")
            else:
                query += (" AND (m.date > ? OR (m.date = ? AND (m.chat_id > ?"
                          " OR (m.chat_id = ? AND m.msg_id > ?))))")
            params.extend([c_date, c_date, c_chat, c_chat, c_msg])
    order = "DESC" if desc else "ASC"
    query += (f" ORDER BY m.date {order}, m.chat_id {order}, m.msg_id {order}"
              " LIMIT ?")
    params.append(limit + 1)
    rows = conn.execute(query, params).fetchall()
    has_more = len(rows) > limit
    out = [dict(r) for r in rows[:limit]]
    next_cursor = None
    if has_more and out:
        last = out[-1]
        next_cursor = f"{last['date']}|{last['chat_id']}|{last['msg_id']}"
    return out, next_cursor, has_more


def senders(conn, chat_ids=None, limit=200):
    """Distinct sender names with message counts, for filter dropdowns."""
    query = ("SELECT sender_name, COUNT(*) AS count FROM messages "
             "WHERE sender_name IS NOT NULL AND sender_name != ''")
    params = []
    if chat_ids:
        marks = ",".join("?" * len(chat_ids))
        query += f" AND chat_id IN ({marks})"
        params.extend(chat_ids)
    query += " GROUP BY sender_name ORDER BY count DESC, sender_name LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(query, params).fetchall()]


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


def conversation(conn, chat_id: int, msg_id: int, before: int = 12,
                 after: int = 12) -> dict | None:
    """Reconstruct the conversation around one message (v0.7).

    Honest about data limits: ``reply_to`` is only captured going forward
    (v0.5+), so the reply chain is completed with a same-chat message-id
    window (Telegram's natural order) around the target. Every returned
    row is the original archived message - nothing is inferred.

    Returns {"target", "ancestors", "replies", "rows"} or None when the
    message does not exist. ``rows`` is the chronological context window
    (target flagged with is_target, direct replies flagged is_reply).
    """
    target = conn.execute(
        """SELECT m.*, c.title AS chat_title, c.username AS chat_username
           FROM messages m JOIN chats c ON c.chat_id = m.chat_id
           WHERE m.chat_id=? AND m.msg_id=?""",
        (chat_id, msg_id)).fetchone()
    if target is None:
        return None

    # reply chain upward (captured going forward; cycle-safe, max 10 hops)
    ancestors, seen, cur = [], {(chat_id, msg_id)}, target["reply_to"]
    while cur is not None and (chat_id, cur) not in seen and len(ancestors) < 10:
        row = conn.execute(
            """SELECT m.*, c.title AS chat_title, c.username AS chat_username
               FROM messages m JOIN chats c ON c.chat_id = m.chat_id
               WHERE m.chat_id=? AND m.msg_id=?""",
            (chat_id, cur)).fetchone()
        if row is None:
            break
        ancestors.append(dict(row))
        seen.add((chat_id, cur))
        cur = row["reply_to"]
    ancestors.reverse()

    # direct replies to the target (captured going forward)
    replies = [dict(r) for r in conn.execute(
        """SELECT m.*, c.title AS chat_title, c.username AS chat_username
           FROM messages m JOIN chats c ON c.chat_id = m.chat_id
           WHERE m.chat_id=? AND m.reply_to=?
           ORDER BY m.msg_id LIMIT 20""", (chat_id, msg_id)).fetchall()]
    reply_ids = {(chat_id, r["msg_id"]) for r in replies}

    # same-chat id window around the target = the visible conversation
    lo = conn.execute(
        "SELECT MIN(msg_id) m FROM (SELECT msg_id FROM messages "
        "WHERE chat_id=? AND msg_id<? ORDER BY msg_id DESC LIMIT ?)",
        (chat_id, msg_id, max(1, before))).fetchone()["m"]
    hi = conn.execute(
        "SELECT MAX(msg_id) m FROM (SELECT msg_id FROM messages "
        "WHERE chat_id=? AND msg_id>? ORDER BY msg_id ASC LIMIT ?)",
        (chat_id, msg_id, max(1, after))).fetchone()["m"]
    where, params = "m.chat_id=? AND m.msg_id>=?", [chat_id, lo or msg_id]
    if hi is not None:
        where += " AND m.msg_id<=?"
        params.append(hi)
    rows = [dict(r) for r in conn.execute(
        f"""SELECT m.*, c.title AS chat_title, c.username AS chat_username
            FROM messages m JOIN chats c ON c.chat_id = m.chat_id
            WHERE {where}
            ORDER BY m.msg_id""", params)]
    for r in rows:
        r["is_target"] = 1 if r["msg_id"] == msg_id else 0
        r["is_reply"] = 1 if (chat_id, r["msg_id"]) in reply_ids else 0
    return {"target": dict(target), "ancestors": ancestors,
            "replies": replies, "rows": rows}


def stats(conn):
    """Archive stats. Message counts include only TRACKED chats, so the
    numbers always match what browse/search/AI can actually see (messages
    of untracked chats stay on disk but are hidden)."""
    n_msgs = conn.execute(
        "SELECT COUNT(*) c FROM messages WHERE chat_id IN "
        "(SELECT chat_id FROM chats WHERE tracked=1)").fetchone()["c"]
    n_chats = conn.execute(
        "SELECT COUNT(*) c FROM chats WHERE tracked=1").fetchone()["c"]
    last = conn.execute(
        "SELECT MAX(m.date) d FROM messages m JOIN chats c ON c.chat_id = m.chat_id "
        "WHERE c.tracked=1").fetchone()["d"]
    pending = conn.execute(
        "SELECT COUNT(*) c FROM chats WHERE tracked=1 "
        "AND (backfill_floor > 0 OR last_msg_id = 0)").fetchone()["c"]
    return {"messages": n_msgs, "chats": n_chats, "last_message": last,
            "pending_backfills": pending}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    print(f"Initialized {DB_PATH}")

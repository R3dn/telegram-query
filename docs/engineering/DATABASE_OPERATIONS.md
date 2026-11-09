# Database Operations — Telegram Query

One SQLite database (`data/messages.db` by default), WAL mode, schema
version 9. This runbook covers what an operator actually needs: layout,
migrations, maintenance, backup/restore, integrity, and the concurrency
model.

## 1. Layout & tuning (as the app opens it)

```
messages.db        the archive (all tables + FTS5 index + sqlite_stat1)
messages.db-wal    write-ahead log (checkpointed automatically)
messages.db-shm    WAL index (transient)
tg_session.session Telethon session — NOT part of the archive DB
```

Per-connection pragmas set by `db.get_db()`:

| Pragma | Value | Why |
|---|---|---|
| `journal_mode` | WAL | readers never block the writer; crash-safe |
| `synchronous` | NORMAL | WAL companion; fsync per checkpoint instead of per commit. App-crash safe; a power loss can lose the last moments of a backfill, which re-fetches from its checkpoint |
| `busy_timeout` | 20 s | polite contention handling between request threads and the sync job |
| `foreign_keys` | ON | citation tables stay honest |
| `cache_size` | 8 MB | keeps hot index pages in RAM for long-lived connections |

The app opens **one connection per request** (short-lived) and separate
connections for the sync job and scheduler — the correct pattern for
SQLite with WAL.

## 2. Schema versions & migrations

`schema_meta.version` records the applied version (currently **9**).
Migrations are **additive-only and idempotent**, run automatically at
startup, and never destroy data. v9 (this release):

- `idx_messages_date_id (date, chat_id, msg_id)` — **replaces**
  `idx_messages_date` (prefix-compatible; makes keyset pagination an
  index seek).
- `idx_messages_chat_sender (chat_id, sender_name)` — senders dropdown
  (−48…−71 % latency at 500 k rows).
- `idx_messages_reply (chat_id, reply_to)` — conversation reply lookups.
- One-time `ANALYZE` so the planner uses them immediately.

**Testing a migration on a copy:** point `TG_DB_PATH` at a copy of your
real archive and start the app — it prints/logs normally and updates
the copy. The test suite also covers a fresh DB and a v5→v9 upgrade
with data preservation checks.

To check the current version:

```bash
python -c "import sqlite3; print(sqlite3.connect('data/messages.db').execute(\"SELECT value FROM schema_meta WHERE key='version'\").fetchone())"
```

## 3. Planner statistics (ANALYZE)

The v9 indexes need fresh stats for the planner. `db.analyze_if_stale`
runs as a **post-sync hook**: when the message count has **doubled**
since the last analyze (and grew by ≥5 000), it runs `ANALYZE` in the
job thread. Cost: 0.33 s at 500 k rows — amortized O(log growth), never
in a request.

If you ever see a query inexplicably slow after big manual writes
(outside the app), run once:

```bash
python -c "import sqlite3; c=sqlite3.connect('data/messages.db'); c.execute('ANALYZE'); c.commit()"
```

## 4. Backups

Online, consistent, compacted — the app can keep running:

```bash
python scripts/backup_db.py                 # -> data/backups/messages-<utc-stamp>.db
python scripts/backup_db.py --keep 14       # retention
python scripts/backup_db.py --db X --out Y  # custom paths
```

`VACUUM INTO` produces a **standalone, fully compacted** snapshot
(no `-wal`/`-shm` needed to restore). A backup schedule (daily, keep 2
weeks) is the whole policy; `--keep` prunes old snapshots.

**What is NOT in a backup:** the Telegram session file and `.env`
(secrets — copy separately, once, with restrictive permissions).

### Restore

1. Stop the app.
2. Replace the archive (or point `TG_DB_PATH` at the backup):

```bash
move data\messages.db data\messages.db.broken
copy data\backups\messages-20261110-030000.db data\messages.db
```

3. Start the app. The backup carries its schema version; migrations
   apply if needed.
4. The next sync re-fetches anything newer than the snapshot from
   Telegram itself — the archive is rebuildable from source + backups.

## 5. Integrity checks

```bash
python -c "import sqlite3; c=sqlite3.connect('data/messages.db'); print(c.execute('PRAGMA integrity_check').fetchone()[0])"
# expect: ok
```

The FTS index can be rebuilt from the content table at any time
(keeps `text_norm` as-is):

```bash
python -c "import sqlite3; c=sqlite3.connect('data/messages.db'); c.execute(\"INSERT INTO messages_fts(messages_fts) VALUES('rebuild')\"); c.commit()"
```

## 6. Concurrency model & contention

- One writer at a time (SQLite). The sync job is the main writer;
  API writes (bookmarks, alerts, watchlists…) are tiny and bounded by
  the 20 s busy timeout.
- WAL lets readers proceed during writes; the benchmark ran 8
  concurrent readers against a live writer with flat RSS and no
  timeouts.
- The one rule: **never** a second app process (or sync CLI beside the
  app) on the same session/archive.

## 7. Growth & housekeeping

- ~0.5 KB/message with indexes (500 k ≈ 290 MB).
- WAL is checkpointed automatically (SQLite default: 1 000 pages);
  after very large backfills a one-time `PRAGMA wal_checkpoint(TRUNCATE)`
  shrinks `-wal` if you need the disk back immediately.
- Untracked groups' messages stay on disk (hidden) until
  "untrack & delete" — that's the only user-facing delete, and it
  rebuilds the FTS index when it runs.
- `PRAGMA optimize` on close is not needed; ANALYZE maintenance covers
  planner health.

## 8. Repair playbook

| Symptom | Action |
|---|---|
| `database is locked` errors | almost always a second process — check for stray `python sync.py`/app instances; busy_timeout handles the rest |
| Search misses obvious messages | run the reindex job (Settings) — rewrites `text_norm` with current rules and rebuilds FTS |
| `messages.db-wal` huge | checkpoint (above); verify no long-running reader process |
| App starts, UI empty, DB present | check `/api/health/ready` (503 = DB unreadable) and file permissions on the data dir |
| Slow queries after heavy manual writes | `ANALYZE` (§3) |

"""Safe online backup of the Telegram Query archive.

Uses SQLite's own backup mechanism (VACUUM INTO): a consistent snapshot
written while the app can keep running - readers are never blocked and
a running sync's committed state is captured correctly. The output is a
fully compacted, standalone database (no -wal/-shm needed to restore).

Usage:
  python scripts/backup_db.py                      # -> data/backups/
  python scripts/backup_db.py --db path --out dir
  python scripts/backup_db.py --keep 10             # retention

Restore = stop the app, replace the archive file with the backup (or
point TG_DB_PATH at it), start the app. Full procedure:
docs/engineering/DATABASE_OPERATIONS.md.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sqlite3  # noqa: E402

import db  # noqa: E402


def backup(db_path: Path, out_dir: Path, keep: int = 0) -> Path:
    if not db_path.exists():
        raise SystemExit(f"no database at {db_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"messages-{stamp}.db"
    # VACUUM INTO: online, consistent, compacted snapshot in one step
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA busy_timeout=20000")
        conn.execute("VACUUM INTO ?", (str(target),))
    finally:
        conn.close()
    if keep > 0:
        backups = sorted(out_dir.glob("messages-*.db"))
        for old in backups[:-keep]:
            old.unlink(missing_ok=True)
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=None,
                    help="archive path (default: the configured TG_DB_PATH)")
    ap.add_argument("--out", default=None,
                    help="output directory (default: <db dir>/backups)")
    ap.add_argument("--keep", type=int, default=0,
                    help="keep only the newest N backups (0 = keep all)")
    args = ap.parse_args()

    db_path = Path(args.db) if args.db else db.DB_PATH
    out_dir = Path(args.out) if args.out else db_path.parent / "backups"
    target = backup(db_path, out_dir, args.keep)
    size_mb = target.stat().st_size / 1e6
    print(f"backup complete: {target} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()

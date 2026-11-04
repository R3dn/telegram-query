"""Telegram sync CLI - fetches and incrementally updates group messages.

Usage:
  python sync.py                      incremental sync of tracked groups (new messages)
  python sync.py --days 3            re-fetch last 3 days (edits included) + new messages
  python sync.py --full              backfill entire history of tracked groups
  python sync.py --list              list chats you're in
  python sync.py --track <id> [...]   start tracking chat(s), full backfill
  python sync.py --untrack <id> [...] stop tracking chat(s)
  python sync.py --interactive       pick groups to track (first run)

The web app's "Sync now" button runs the same code with days=SYNC_DAYS (default 3).
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

import db
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import User, Channel, Chat

API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tg_session")


def need_creds():
    if not API_ID or not API_HASH:
        print("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH.")
        print("Get them from https://my.telegram.org -> API development tools,")
        print("then copy .env.example to .env and fill them in.")
        sys.exit(1)


def sender_name(msg) -> str:
    s = msg.sender
    if s is None:
        return ""
    if isinstance(s, User):
        name = " ".join(filter(None, [s.first_name, s.last_name]))
        return f"@{s.username} ({name})" if s.username else name
    if isinstance(s, (Channel, Chat)):
        return getattr(s, "title", "") or ""
    return ""


def msg_text(msg) -> str:
    parts = []
    if msg.message:
        parts.append(msg.message)
    if getattr(msg, "media", None):
        parts.append("[image]")
    return " ".join(parts)


def store_message(conn, chat_id, msg):
    if msg.date is None:
        return
    date = msg.date.astimezone(timezone.utc).isoformat()
    db.upsert_message(
        conn, chat_id, msg.id, date, msg.sender_id, sender_name(msg), msg_text(msg),
        has_media=1 if getattr(msg, "media", None) else 0,
        edited=1 if getattr(msg, "edit_date", None) else 0,
    )


async def iter_with_flood_retry(client, chat, **kwargs):
    """Yield messages, transparently waiting out Telegram flood limits."""
    it = client.iter_messages(chat, wait_time=1, **kwargs)
    while True:
        try:
            msg = await it.__anext__()
        except StopAsyncIteration:
            return
        except FloodWaitError as e:
            print(f"  FloodWait: sleeping {e.seconds}s ...")
            await asyncio.sleep(e.seconds + 1)
        else:
            yield msg


async def sync_chat(client, conn, chat_id, full=False, days=None, incremental=True):
    """Sync one chat.

    days=N        - re-fetch ALL messages from the last N days (catches edits)
    incremental   - fetch messages newer than the last synced message ID
    full=True     - fetch entire history (ignores sync state)
    Default (days=None) = plain incremental sync.
    """
    chat = await client.get_entity(chat_id)
    title = getattr(chat, "title", "") or str(chat_id)
    if isinstance(chat, User):
        kind = "user"
    elif isinstance(chat, Channel) and not getattr(chat, "megagroup", False):
        kind = "channel"
    else:
        kind = "group"
    db.upsert_chat(conn, chat_id, title, getattr(chat, "username", None), kind)

    last_msg_id, _ = db.get_sync_state(conn, chat_id)
    min_id = 0 if full else last_msg_id
    newest_id = last_msg_id
    count = 0
    since = (datetime.now(timezone.utc) - timedelta(days=days)) if days else None

    def tick():
        nonlocal count
        count += 1
        if count % 500 == 0:
            db.reindex_fts(conn)
            conn.commit()
            print(f"  ... {count} messages")

    try:
        if since:
            print(f"[{title}] re-scanning last {days} day(s) "
                  f"(since {since:%Y-%m-%d %H:%M} UTC, edits included) ...")
            async for msg in iter_with_flood_retry(client, chat):
                if msg.date and msg.date.astimezone(timezone.utc) < since:
                    break
                store_message(conn, chat_id, msg)
                newest_id = max(newest_id, msg.id)
                tick()

        if incremental:
            if min_id > 0:
                print(f"[{title}] fetching new messages (id > {min_id}) ...")
                async for msg in iter_with_flood_retry(client, chat, min_id=min_id):
                    store_message(conn, chat_id, msg)
                    newest_id = max(newest_id, msg.id)
                    tick()
            elif not since:
                print(f"[{title}] full backfill ...")
                async for msg in iter_with_flood_retry(client, chat):
                    store_message(conn, chat_id, msg)
                    newest_id = max(newest_id, msg.id)
                    tick()
    except Exception as e:
        print(f"  error: {e}")

    db.update_sync_state(conn, chat_id, newest_id)
    conn.commit()
    db.reindex_fts(conn)
    conn.commit()
    total = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
    print(f"[{title}] {count} messages processed, DB total: {total}")


async def list_chats(client, conn):
    print("\nChats you're in (id  title  [T=tracked]):")
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            tracked = conn.execute(
                "SELECT tracked FROM chats WHERE chat_id=?",
                (dialog.id,),
            ).fetchone()
            mark = "T" if tracked and tracked["tracked"] else " "
            print(f" {mark} {dialog.id:>12}  {dialog.name}")


async def interactive_track(client, conn):
    await list_chats(client, conn)
    raw = input("\nComma-separated chat IDs to track (empty = keep current): ").strip()
    if not raw:
        return
    ids = [int(x) for x in raw.replace(" ", "").split(",") if x]
    for cid in ids:
        entity = await client.get_entity(cid)
        db.upsert_chat(conn, cid, getattr(entity, "title", str(cid)),
                       getattr(entity, "username", None))
        print(f" tracking {cid}: {getattr(entity, 'title', cid)}")
    conn.commit()


async def run(args):
    need_creds()
    db.init_db()
    conn = db.get_db()
    client = TelegramClient(SESSION, int(API_ID), API_HASH)

    await client.start()
    me = await client.get_me()
    print(f"Logged in as {me.first_name}")

    try:
        if args.list:
            await list_chats(client, conn)
        elif args.track:
            for cid in args.track:
                entity = await client.get_entity(cid)
                db.upsert_chat(conn, cid, getattr(entity, "title", str(cid)),
                               getattr(entity, "username", None))
                await sync_chat(client, conn, cid, full=True)
            conn.commit()
        elif args.untrack:
            for cid in args.untrack:
                conn.execute(
                    "UPDATE chats SET tracked=0 WHERE chat_id=?", (cid,))
                print(f" untracked {cid}")
            conn.commit()
        elif args.interactive:
            await interactive_track(client, conn)
        else:
            chats = db.get_tracked_chats(conn)
            if not chats:
                print("No tracked chats yet. Choose groups:")
                await interactive_track(client, conn)
                chats = db.get_tracked_chats(conn)
            for chat in chats:
                await sync_chat(client, conn, chat["chat_id"],
                                full=args.full, days=args.days)
    finally:
        await client.disconnect()
        conn.close()
    print("Done.")


def main():
    ap = argparse.ArgumentParser(description="Telegram message sync")
    ap.add_argument("--list", action="store_true", help="list your groups")
    ap.add_argument("--track", nargs="+", type=int, metavar="ID",
                    help="start tracking chat ID(s) and backfill")
    ap.add_argument("--untrack", nargs="+", type=int, metavar="ID")
    ap.add_argument("--full", action="store_true",
                    help="backfill entire history from scratch")
    ap.add_argument("--days", type=int, metavar="N",
                    help="re-fetch the last N days of messages (edits included)")
    ap.add_argument("--interactive", action="store_true",
                    help="pick groups to track interactively")
    args = ap.parse_args()

    need_creds()
    db.init_db()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

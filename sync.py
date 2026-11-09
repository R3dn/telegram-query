"""Telegram sync - fetches and incrementally updates group messages.

CLI usage:
  python sync.py                      incremental sync of tracked groups
  python sync.py --days 3            re-fetch last 3 days (edits included)
  python sync.py --full              backfill entire history of tracked groups
  python sync.py --list              list chats you're in
  python sync.py --track <id> [...]   start tracking chat(s), full backfill
  python sync.py --untrack <id> [...] stop tracking chat(s)
  python sync.py --login             log in to Telegram (interactive) and exit

The web app runs the same code through jobs.run_sync_job(); there the client
connects NON-interactively and fails with a clear error when the account is
not authenticated (use the web login wizard or `python sync.py --login`).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import threading
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.errors import ChatIdInvalidError, FloodWaitError
from telethon.tl.types import Channel, Chat, User

import config
import db

# Set by the web app's "stop" endpoint; checked between messages/chats.
CANCEL = threading.Event()


@dataclass
class SyncArgs:
    """What to sync. Built by the CLI (main) or by jobs.run_sync_job()."""
    list: bool = False
    track: list[int] | None = None
    untrack: list[int] | None = None
    full: bool = False
    days: int | None = None
    interactive: bool = False
    login_interactive: bool = True   # False when run from the web app
    login: bool = False
    force: bool = False              # CLI only: run beside a live app


def need_creds():
    if not config.settings.telegram_configured:
        print("Missing TG_API_ID / TG_API_HASH.")
        print("Get them from https://my.telegram.org -> API development tools,")
        print("then copy .env.example to .env and fill them in.")
        sys.exit(1)


def make_client(login_interactive: bool = True) -> TelegramClient:
    """Create a client. Async: call `await make_client(...)`.

    login_interactive=True (CLI): `start()` prompts for phone/code.
    login_interactive=False (web jobs): connect + fail with a clear
    error if the stored session is not signed in - never prompts.
    """
    need_creds()
    return TelegramClient(str(config.settings.session_path),
                          int(config.settings.tg_api_id),
                          config.settings.tg_api_hash)


async def connect_client(client: TelegramClient, login_interactive: bool) -> TelegramClient:
    if login_interactive:
        await client.start()
        return client
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError(
            "Telegram account is not authenticated. Log in from the web app "
            "or run: python sync.py --login")
    return client


def _app_running() -> bool:
    """Is the web app (this same installation) serving right now? Cheap
    local probe of the health endpoint (no credentials cross the wire)."""
    try:
        url = (f"http://{config.settings.host}:{config.settings.port}"
               "/api/health")
        with urllib.request.urlopen(url, timeout=0.8) as r:
            return getattr(r, "status", None) == 200
    except Exception:  # noqa: BLE001 - any failure means "not running"
        return False


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
        reply_to=getattr(msg, "reply_to_msg_id", None),
    )


async def iter_with_flood_retry(client, chat, **kwargs):
    """Yield messages, transparently waiting out Telegram flood limits.
    Stops early (cleanly) when a cancel was requested."""
    it = client.iter_messages(chat, wait_time=1, **kwargs)
    while True:
        if CANCEL.is_set():
            return
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
    """Sync one chat. Returns True when the chat processed without an
    error, False otherwise (failed resolution or a fetch error).

    days=N        - re-fetch ALL messages from the last N days (catches edits)
    incremental   - fetch messages newer than the last synced message ID
    full=True     - fetch entire history from scratch
    History backfills are checkpointed (chats.backfill_floor) so they can be
    stopped and resumed without losing progress.
    Default (days=None) = plain incremental sync (+ backfill resume if paused).
    A chat that cannot be resolved (deleted, migrated to a supergroup, this
    account left/was kicked) is skipped with a log line naming it - one
    dead group must not abort the whole sync job.
    """
    try:
        chat = await client.get_entity(chat_id)
    except Exception as e:
        row = conn.execute("SELECT title FROM chats WHERE chat_id=?",
                           (chat_id,)).fetchone()
        title = row["title"] if row else str(chat_id)
        if isinstance(e, ChatIdInvalidError):
            print(f"[{title}] skipped - chat ID is invalid "
                  f"(deleted, migrated to a supergroup, or you left it)")
            print(f"  untrack it to stop syncs from retrying: "
                  f"python sync.py --untrack {chat_id}")
        else:
            print(f"[{title}] skipped - could not resolve the chat ({e})")
        return False
    title = getattr(chat, "title", "") or str(chat_id)
    if isinstance(chat, User):
        kind = "user"
    elif isinstance(chat, Channel) and not getattr(chat, "megagroup", False):
        kind = "channel"
    else:
        kind = "group"
    db.upsert_chat(conn, chat_id, title, getattr(chat, "username", None), kind)

    last_msg_id, _, floor = db.get_sync_state(conn, chat_id)
    min_id = 0 if full else last_msg_id
    newest_id = last_msg_id
    if full:
        floor = 0
    count = 0
    ok = True   # flipped to False on a fetch error (v9: a failed sync must
                # not be reported to the scheduler as a successful one)
    since = (datetime.now(timezone.utc) - timedelta(days=days)) if days else None

    def tick():
        nonlocal count
        count += 1
        if count % 200 == 0:
            conn.commit()  # short transactions -> tiny write-lock windows
        if count % 500 == 0:
            print(f"  ... {count} messages")

    async def run_backfill(max_id=None):
        """Walk history newest->oldest, checkpointing every 500 messages.
        On cancel, saves the floor so the next sync resumes right here."""
        nonlocal newest_id, count
        kwargs = {"max_id": max_id} if max_id else {}
        seen = None
        async for msg in iter_with_flood_retry(client, chat, **kwargs):
            store_message(conn, chat_id, msg)
            newest_id = max(newest_id, msg.id)
            seen = msg.id
            count += 1
            if count % 200 == 0:
                conn.commit()
            if count % 500 == 0:
                conn.commit()
                db.set_backfill_progress(conn, chat_id, newest_id, seen)
                print(f"  ... {count} messages (checkpoint id {seen})")
        conn.commit()
        if seen is not None:
            paused = CANCEL.is_set()
            db.set_backfill_progress(conn, chat_id, newest_id,
                                     seen if paused else 0)
            conn.commit()
            if paused:
                print("  backfill paused - progress saved (sync again to resume)")
            else:
                print("  backfill complete")

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

            if floor > 0:
                print(f"[{title}] resuming backfill below id {floor} ...")
                await run_backfill(max_id=floor - 1)
            elif min_id == 0 and not since:
                print(f"[{title}] full backfill ...")
                await run_backfill()
    except Exception as e:
        ok = False
        print(f"  error: {e}")

    db.update_sync_state(conn, chat_id, newest_id)
    conn.commit()
    total = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
    print(f"[{title}] {count} messages processed, DB total: {total}")
    return ok


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


async def fetch_dialogs():
    """List every group/channel dialog as dicts (used by the web UI).
    Runs non-interactively: fails clearly when not logged in."""
    client = make_client(login_interactive=False)
    await connect_client(client, login_interactive=False)
    out = []
    try:
        async for d in client.iter_dialogs():
            if not (d.is_group or d.is_channel):
                continue
            kind = "channel" if (d.is_channel and not d.is_group) else "group"
            out.append({
                "chat_id": d.id,
                "title": d.name or str(d.id),
                "username": getattr(d.entity, "username", None),
                "kind": kind,
            })
    finally:
        await client.disconnect()
    return out


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


async def run(args: SyncArgs):
    need_creds()
    db.init_db()
    if args.login_interactive and _app_running() and not args.force:
        print("The Telegram Query web app appears to be running "
              f"(http://{config.settings.host}:{config.settings.port}).")
        print("Two processes must not share one Telegram session - the app's")
        print("own scheduler/sync would race this CLI run. Stop the app, or")
        print("use the app's UI (or --force to accept the risk).")
        sys.exit(2)
    conn = db.get_db()
    client = make_client(login_interactive=args.login_interactive)
    await connect_client(client, args.login_interactive)

    try:
        me = await client.get_me()
        print(f"Logged in as {me.first_name}")

        if args.login:
            print("Session is valid - the web app can now sync.")
            return

        if args.list:
            await list_chats(client, conn)
        elif args.track:
            for cid in args.track:
                if CANCEL.is_set():
                    print("Cancelled - remaining chats skipped.")
                    break
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
            outcomes = []
            for chat in chats:
                if CANCEL.is_set():
                    print("Cancelled - remaining chats skipped.")
                    break
                outcomes.append(await sync_chat(
                    client, conn, chat["chat_id"],
                    full=args.full, days=args.days))
            # v9: honest failure propagation. A sync where EVERY chat
            # failed is a failed sync: the job runner marks the job as
            # failed and the scheduler stops recording a bogus
            # last_success. Partial failures stay per-chat warnings -
            # one dead group must not fail an otherwise good sync.
            if chats and outcomes and not any(outcomes):
                raise RuntimeError(
                    f"all {len(chats)} tracked chat(s) failed to sync - "
                    "see the job log above (network? session? flood?)")
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
    ap.add_argument("--login", action="store_true",
                    help="log in to Telegram interactively, then exit")
    ap.add_argument("--force", action="store_true",
                    help="run even when the web app appears to be running "
                         "(two processes sharing one Telegram session can "
                         "invalidate it)")
    ns = ap.parse_args()
    args = SyncArgs(list=ns.list, track=ns.track, untrack=ns.untrack,
                    full=ns.full, days=ns.days, interactive=ns.interactive,
                    login_interactive=True, login=ns.login, force=ns.force)

    need_creds()
    db.init_db()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

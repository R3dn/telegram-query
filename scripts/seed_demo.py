"""Seed a synthetic demo archive so the UI can be explored without Telegram.

Creates (or replaces) a demo database with ten fictional English-speaking
groups and a few hundred fake messages, then prints how to run the app
against it. Never touches your real database.

Usage:
    python scripts/seed_demo.py            # data/demo.db
    python scripts/seed_demo.py --path my_demo.db
    python scripts/seed_demo.py --messages 800

Run the app against it:
    TG_DB_PATH=data/demo.db TG_SESSION_PATH=data/demo python app.py
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402

# Ten fictional groups (all English, all fake - no real communities).
GROUPS = [
    (-10012340001, "Tech Deals & Gadgets", "techdealsdemo", "channel"),
    (-10012340002, "Weekend Hikers", "weekendhikers", "group"),
    (-10012340003, "Home Cooking Club", None, "group"),
    (-10012340004, "Photography Enthusiasts", "photoclub", "group"),
    (-10012340005, "Board Game Nights", None, "group"),
    (-10012340006, "Crypto & Finance Talk", "financetalk", "channel"),
    (-10012340007, "Fitness Motivation", None, "group"),
    (-10012340008, "Indie Game Devs", "indiegamedevs", "group"),
    (-10012340009, "Coffee Lovers", "coffeelovers", "channel"),
    (-10012340010, "Volunteer Network", None, "group"),
]

SENDERS = [
    "Sara (sara_dev)", "Omar K.", "Dave", "Maya", "Jules",
    "Pete T.", "Lena C.", "Marc B.", "Kim", "Trail Mix",
]

DEALS = [
    ("GadgetHub Store", "Laptop sleeves 30% off with code SLEEVE30", "SLEEVE30"),
    ("Pizza Palace", "Buy one get one free on all large pizzas, code PALACE2", "PALACE2"),
    ("Bean & Brew", "Free size upgrade on any latte this Friday", None),
    ("Runner's Corner", "20% discount on all trail shoes this weekend", "TRAIL20"),
    ("PixelPrints", "Photo prints half price, code FRAMES50", "FRAMES50"),
    ("Tabletop Toys", "Board game bundle deal - 3 games for $45", None),
    ("KeyCrunch Coffee", "Subscription discount code WAKEUP15 for new members", "WAKEUP15"),
    ("FitGear Online", "Resistance bands deal - 40% off with code BAND40", "BAND40"),
]

CHAT = [
    "Has anyone tried the new hiking trail near the north ridge?",
    "The sunset from the summit was incredible yesterday",
    "Best time to arrive is before 7am on weekends, parking fills up",
    "Bringing extra water is a must in summer - learned that the hard way",
    "Trail conditions report: muddy after rain, take the eastern path",
    "Who is in for Saturday's meetup?",
    "Any recommended budget lenses for landscape shots?",
    "Shot on a 35mm prime, straight out of camera, no edits",
    "What shutter speed do you use for birds in flight?",
    "Our next board game night is Friday - bringing the new expansion",
    "Rules question: can you trade resources during someone else's turn?",
    "Meal prep Sunday went well - five lunches ready for the week",
    "Sourdough starter is finally alive after three attempts",
    "Anyone got a good pancake recipe that does not need buttermilk?",
    "Finished the first playable build of my puzzle game today",
    "Unity or Godot for a 2D platformer in 2026?",
    "Shader compilation times are brutal this week",
    "Six months into the home gym setup - consistency beats intensity",
    "New personal record on deadlifts today, small wins add up",
    "Reminder: volunteer orientation for the food bank is on Thursday",
    "We still need two more people for the beach cleanup",
    "DCA is not a strategy, it is a personality type",
    "Market update: sideways again, expectations unchanged",
    "The new pour-over kit arrived - this changes everything",
    "Light roast vs dark roast, the eternal debate returns",
]

# v0.7 discovery content (deterministic): the same announcement posted in
# several groups (cross-group stories), Q&A threads with captured replies,
# recurring brand mentions (entities), and bilingual Arabic messages.
ANNOUNCEMENTS = [
    ("Community meetup this Saturday 7pm at the central park pavilion, "
     "everyone welcome - bring snacks and drinks for the group"),
    ("Aurora Coffee is giving free size upgrades all weekend, tell them "
     "the community sent you for the discount"),
]
QA_THREADS = [
    (-10012340004, "What shutter speed do you use for birds in flight?",
     "Use 1/2000s with burst mode, works every time for me"),
    (-10012340008, "Which engine for a 2D platformer in 2026?",
     "Godot 4 is lighter for small 2D games, Unity if you need console ports"),
    (-10012340009, "هل يوجد كوبون خصم لمتجر نيمبوس هوستنج؟",
     "نعم، كود NIMBUS20 يعطيك خصم عشرين بالمئة على أول شهر"),
]
ENTITY_BRANDS = [
    ("Aurora Coffee", "brand"),
    ("Nimbus Hosting", "brand"),
    ("GadgetHub", "brand"),
    ("Trail Mix Co", "brand"),
]
ARABIC_CHAT = [
    "شلون أسعار القهوة هالأسبوع؟ ارتفعت مرة",
    "هااااي شباب، أحد جرب خدمة توصيل نيمبوس هوستنج الجديدة؟",
    "توصيل مجاني من متجر أورورا كافيه اليوم فقط، استغلوا العرض",
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed a synthetic demo archive")
    ap.add_argument("--path", default=str(
        Path(__file__).resolve().parent.parent / "data" / "demo.db"))
    ap.add_argument("--messages", type=int, default=600)
    args = ap.parse_args()

    path = Path(args.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)

    conn = db.get_db(str(path))
    rng = random.Random(42)  # deterministic demo content
    for chat_id, title, username, kind in GROUPS:
        db.upsert_chat(conn, chat_id, title, username, kind)

    now = datetime.now(timezone.utc)
    per_group = max(1, args.messages // len(GROUPS))
    n = 0
    for gi, (chat_id, _, _, kind) in enumerate(GROUPS):
        for i in range(per_group):
            sender = rng.choice(SENDERS)
            if kind == "channel" or rng.random() < 0.30:
                biz, offer, code = rng.choice(DEALS)
                text = f"{biz}: {offer}" + (f" - code {code}" if code else "")
            else:
                text = rng.choice(CHAT)
            msg_id = 1000 + gi * 1000 + i
            date = (now - timedelta(minutes=(gi * per_group + i) * 17)).isoformat()
            db.upsert_message(conn, chat_id, msg_id, date,
                              70000 + rng.randint(1, 40), sender, text,
                              has_media=1 if rng.random() < 0.10 else 0,
                              edited=1 if rng.random() < 0.04 else 0)
            n += 1

    # ---- v0.7 discovery content (ids far above the random block) ----
    mid = 20000
    for text in ANNOUNCEMENTS:
        for chat_id in (-10012340001, -10012340003, -10012340005):
            db.upsert_message(conn, chat_id, mid, (now - timedelta(days=1)).isoformat(),
                              70001, "Announcer Bot", text)
            mid += 1
    for chat_id, question, answer in QA_THREADS:
        q_date = (now - timedelta(days=2)).isoformat()
        db.upsert_message(conn, chat_id, mid, q_date, 70002, "Curious Member", question)
        db.upsert_message(conn, chat_id, mid + 1,
                          (now - timedelta(days=2, minutes=-4)).isoformat(),
                          70003, "Helpful Member", answer, reply_to=mid)
        mid += 2
    # one intentionally UNANSWERED question for the radar
    db.upsert_message(conn, -10012340002, mid,
                      (now - timedelta(days=1)).isoformat(),
                      70002, "Curious Member",
                      "Anyone know if the north ridge lot allows overnight parking?")
    mid += 1
    for d in range(0, 25, 2):
        for gi, (chat_id, _, _, _) in enumerate(GROUPS[:4]):
            name, _ = ENTITY_BRANDS[(d + gi) % len(ENTITY_BRANDS)]
            db.upsert_message(conn, chat_id, mid,
                              (now - timedelta(days=d)).isoformat(),
                              70010 + gi, rng.choice(SENDERS),
                              f"{name} update: the community buzz around "
                              f"{name} keeps growing this month")
            mid += 1
    for i, text in enumerate(ARABIC_CHAT):
        db.upsert_message(conn, (-10012340002, -10012340009, -10012340007)[i % 3],
                          mid, (now - timedelta(days=1, hours=i)).isoformat(),
                          70020 + i, "عضو نشيط", text)
        mid += 1
    conn.commit()

    # pretend history is fully synced so no "backfill pending" states show
    for r in conn.execute(
            "SELECT chat_id, MAX(msg_id) m FROM messages GROUP BY chat_id"
    ).fetchall():
        conn.execute("UPDATE chats SET last_msg_id=?, backfill_floor=0 "
                     "WHERE chat_id=?", (r["m"], r["chat_id"]))
    conn.commit()

    # build the v0.7 discovery data so Discover/Entities are alive on
    # first open (deterministic; the app keeps them fresh after each sync)
    import discover
    import entities
    discover.build_terms(conn, full=True, verbose=lambda *_: None)
    discover.scan_questions(conn, days=3650, verbose=lambda *_: None)
    for name, kind in ENTITY_BRANDS:
        entities.add_entity(conn, name, kind=kind, source="manual",
                            verbose=lambda *_: None)
    entities.match_and_discover(conn, verbose=lambda *_: None)
    conn.commit()

    s = db.stats(conn)
    conn.close()
    print(f"Seeded {n} synthetic messages into {path}")
    print(f"Groups: {s['chats']}, messages: {s['messages']}")
    print("\nRun the app against it:")
    print(f"  TG_DB_PATH={path} TG_SESSION_PATH=data/demo python app.py")


if __name__ == "__main__":
    main()

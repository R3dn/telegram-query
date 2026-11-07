"""Seed a synthetic demo archive so the UI can be explored without Telegram.

Creates (or replaces) a demo database with two fictional groups and a few
hundred mixed Arabic/English messages, then prints how to run the app
against it. Never touches your real database.

Usage:
    python scripts/seed_demo.py            # data/demo.db
    python scripts/seed_demo.py --path my_demo.db

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

SENDERS = [
    ("@sara_dev", "سارة (Sara)"),
    ("@omar_k", "Omar K."),
    ("@lina_hikes", "لينا (Lina)"),
    ("@dave", "Dave"),
    ("@faisal_z", "فيصل (Faisal)"),
    ("@maya", "Maya"),
]

DEALS = [
    ("Pizza Palace", "Buy one get one free on all large pizzas, code PALACE2", "PALACE2"),
    ("Burger Barn", "20% off app orders this weekend", None),
    ("سوق الخضار", "خصم 15% على جميع المنتجات يوم الجمعة فقط", "GREEN15"),
    ("Coffee Corner", "Free upgrade to large on any latte", None),
    ("شاورما هاوس", "وجبة شاورما بـ 12 ريال بدل 18، اليوم فقط", None),
    ("TechHub Store", "Laptop sleeves 30% off with code SLEEVE30", "SLEEVE30"),
]

CHAT = [
    "Has anyone tried the new hiking trail near المفتل؟",
    "the sunset from the northern ridge was incredible yesterday 🌄",
    "أفضل وقت للوصول هو قبل الساعة ٧ صباحاً",
    "Bringing extra water is a must in summer — learned that the hard way",
    " trail conditions report: muddy after rain, take the eastern path",
    "من معي يوم السبت للنزهة؟",
    "Parking fills up by 8am on weekends fyi",
    "شفت الغزلان قرب المحطة الثالثة 🦌",
]

HISTORY = [
    "anyone have the maintenance schedule PDF for the 2023 model?",
    "the dealership quoted me 480 for the 40k service — is that normal?",
    "جدول الصيانة موجود في التطبيق الرسمي",
    "oil change every 10k km is what the manual says",
    "I hear a faint whistle above 120 km/h, any ideas?",
    "صوت الصفير غالباً من طارة المكيف",
    "check the door seals first, mine had the same issue",
    "fuel consumption dropped after the software update 📉",
    "استهلاك البنزين عندي صار أفضل بعد التحديث",
    "warranty covered the water pump replacement fully 👍",
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed a synthetic demo archive")
    ap.add_argument("--path", default=str(
        Path(__file__).resolve().parent.parent / "data" / "demo.db"))
    ap.add_argument("--messages", type=int, default=400)
    args = ap.parse_args()

    path = Path(args.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)

    conn = db.get_db(str(path))
    rng = random.Random(42)  # deterministic demo content
    db.upsert_chat(conn, -10012340001, "Tech Deals سر التقنية", "techdealsdemo", "channel")
    db.upsert_chat(conn, -10012340002, "Weekend Hikers", None, "group")

    now = datetime.now(timezone.utc)
    n = 0
    for i in range(args.messages):
        group = -10012340001 if i % 3 else -10012340002
        sender_handle, sender_name = rng.choice(SENDERS)
        if group == -10012340001 and rng.random() < 0.45:
            biz, offer, code = rng.choice(DEALS)
            text = f"{biz}: {offer}" + (f" — code {code}" if code else "")
        elif group == -10012340001:
            text = rng.choice(HISTORY)
        else:
            text = rng.choice(CHAT)
        msg_id = 1000 + i
        date = (now - timedelta(minutes=i * 37)).isoformat()
        db.upsert_message(conn, group, msg_id, date, 70000 + rng.randint(1, 9),
                         sender_name, text,
                         has_media=1 if rng.random() < 0.12 else 0,
                         edited=1 if rng.random() < 0.04 else 0)
        n += 1
    conn.commit()

    # pretend history is fully synced so no "backfill pending" states show
    conn.execute("UPDATE chats SET last_msg_id=1400, backfill_floor=0")
    conn.commit()

    s = db.stats(conn)
    conn.close()
    print(f"Seeded {n} synthetic messages into {path}")
    print(f"Groups: {s['chats']}, messages: {s['messages']}")
    print("\nRun the app against it:")
    print(f"  TG_DB_PATH={path} TG_SESSION_PATH=data/demo python app.py")


if __name__ == "__main__":
    main()

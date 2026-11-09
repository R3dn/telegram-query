"""Repeatable performance benchmark for Telegram Query.

Measures, at small/medium/large dataset sizes:

  1. ingestion  - messages/second through the REAL db.upsert_message
                  path (the exact function sync.py uses, commits every
                  200 rows, like the sync loop)
  2. database   - direct query latency + EXPLAIN QUERY PLAN for the hot
                  read paths (browse/search/senders/groups/stats)
  3. api        - HTTP latency P50/P95/P99 and throughput against the
                  REAL app (uvicorn subprocess, like production usage)

Usage (each size runs isolated; results are printed as JSON):

  python scripts/benchmark.py seed  --messages 50000
  python scripts/benchmark.py db    --messages 50000
  python scripts/benchmark.py api  --messages 50000
  python scripts/benchmark.py all   --messages 50000

The seeded dataset is deterministic (fixed RNG): mixed Arabic/English
community content, ~200 senders, dates spread over 2 years, media flags,
reply threads, a known rare term, and known-frequency search terms.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BENCH_DIR = ROOT / "data" / "bench"

# --- content pool (fixed; frequencies matter for search realism) -----------
EN_TEMPLATES = [
    "The new pour-over kit arrived, it changes everything for morning brews",
    "Anyone got a good pancake recipe that does not need buttermilk?",
    "Trail conditions report: muddy after rain, take the eastern path",
    "What shutter speed do you use for birds in flight?",
    "Unity or Godot for a 2D platformer this year?",
    "Meal prep Sunday went well, five lunches ready for the week",
    "Reminder: volunteer orientation for the food bank is on Thursday",
    "Market update: sideways again, expectations unchanged",
    "Best time to arrive is before 7am on weekends, parking fills up",
    "Sourdough starter is finally alive after three attempts",
    "Finished the first playable build of my puzzle game today",
    "New personal record on deadlifts today, small wins add up",
    "Rules question: can you trade resources during someone else's turn?",
    "Bringing extra water is a must in summer, learned that the hard way",
    "DCA is not a strategy, it is a personality type",
    "Shader compilation times are brutal this week",
    "Light roast vs dark roast, the eternal debate returns",
    "We still need two more people for the beach cleanup",
]
AR_TEMPLATES = [
    "شلون أسعار القهوة هالحين؟ ارتفعت مرة ثانية",
    "توصيل مجاني من متجر أورورا كافيه اليوم فقط، استغلوا العرض",
    "هااااي شباب، أحد جرب خدمة توصيل نيمبوس هوستنج الجديدة؟",
    "هل يوجد كوبون خصم لمتجر نيمبوس هوستنج؟",
    "أفضل وقت للوصول قبل الساعة سبعة صباحاً في عطلة نهاية الأسبوع",
    "أحد عنده وصفة بانكيك بدون لبن؟ جربت وحدة وما ضبطت",
    "الطرق موحلة بعد المطر، خذوا المسار الشرقي",
    "شكراً على التنبيه، وصلني الإشعار اليوم الصباح",
    "شنو أفضل عدسة للمشاهد الطبيعية بميزانية محدودة؟",
    "اجتماع الفريق بكرة الساعة عشرة، لا تتأخرون",
]
DEAL_LINES = [
    "عرض خاص: خصم 25٪ على جميع أنواع القهوة بكود AURORA25",
    "Limited offer: Nimbus Hosting first month free with code NIMBUS20",
    "GadgetHub weekend sale - 40% off all cables and chargers, code CABLE40",
    "تخفيضات نهاية الموسم من متجر الواحة، خصم يصل إلى 50٪",
]
QUESTION_LINES = [
    "Does anyone know if the community garden is open on Mondays?",
    "Which mechanic do you trust for brake service around here?",
    "هل تعامل أحد مع شركة التأمين الجديدة؟ شلون تجربتكم؟",
]
RARE_TERM = "xylophone-quartz-benchmark"
SENDERS = [f"member_{i:03d}" for i in range(200)]

CHAT_DEFS = [
    (-10012340001, "Coffee & Roasts Club", "roastclub", "group"),
    (-10012340002, "Trail & Outdoor KSA", "trailksa", "group"),
    (-10012340003, "Photo Walks", "photowalks", "group"),
    (-10012340004, "Indie Game Dev", "gamedevs", "group"),
    (-10012340005, "Home Cooking", "homecooks", "group"),
    (-10012340006, "Fitness Corner", "fitcorner", "group"),
    (-10012340007, "Market Watch", "marketwatch", "channel"),
    (-10012340008, "Aurora Coffee (official)", "auroracoffee", "channel"),
    (-10012340009, "نقطة تجمع", "noqta", "group"),
    (-10012340010, "عروض الخليج", "khajoffers", "channel"),
]


def bench_path(messages: int) -> Path:
    return BENCH_DIR / f"bench_{messages}.db"


# ---------------------------------------------------------------------------
# Seeding (uses the REAL ingestion path so seeding IS the ingestion benchmark)
# ---------------------------------------------------------------------------

def seed(messages: int) -> dict:
    import db  # noqa: E402  (after sys.path + env)

    path = bench_path(messages)
    for suffix in ("", "-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(1234)
    conn = db.get_db(str(path))
    try:
        for chat_id, title, username, kind in CHAT_DEFS:
            db.upsert_chat(conn, chat_id, title, username, kind)

        now = datetime.now(timezone.utc)
        per_chat = messages // len(CHAT_DEFS)
        t0 = time.perf_counter()
        n = 0
        for chat_id, _, _, kind in CHAT_DEFS:
            base_date = now - timedelta(days=rng.randint(1, 700))
            for i in range(per_chat):
                r = rng.random()
                if kind == "channel" or r < 0.12:
                    text = rng.choice(DEAL_LINES)
                elif r < 0.20:
                    text = rng.choice(QUESTION_LINES)
                elif r < 0.55:
                    text = rng.choice(EN_TEMPLATES)
                else:
                    text = rng.choice(AR_TEMPLATES)
                if rng.random() < 0.004:
                    text = f"{text} {RARE_TERM}"   # rare but findable
                if rng.random() < 0.05:
                    text = f"{text} {rng.choice(EN_TEMPLATES)}"
                date = (base_date + timedelta(
                    minutes=rng.randint(0, int(60 * 24 * 730 / len(CHAT_DEFS)))
                )).isoformat()
                reply = i - 1 if (i > 0 and rng.random() < 0.15) else None
                db.upsert_message(
                    conn, chat_id, i + 1, date, rng.randint(1, 5000),
                    rng.choice(SENDERS), text,
                    has_media=1 if rng.random() < 0.10 else 0,
                    edited=1 if rng.random() < 0.03 else 0,
                    reply_to=reply,
                )
                n += 1
                if n % 200 == 0:   # mirror the sync loop's commit cadence
                    conn.commit()
            conn.commit()
        elapsed = time.perf_counter() - t0
        total = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
        # mirror the app's post-sync maintenance: refresh planner
        # statistics once the archive has grown (db.analyze_if_stale is
        # registered as a POST_SYNC_HOOKS entry in production)
        db.analyze_if_stale(conn)
        conn.commit()
    finally:
        conn.close()

    db_size = path.stat().st_size
    wal = Path(str(path) + "-wal")
    wal_size = wal.stat().st_size if wal.exists() else 0
    return {
        "messages": total,
        "seed_seconds": round(elapsed, 2),
        "ingest_msgs_per_sec": round(total / elapsed, 1),
        "db_bytes": db_size,
        "wal_bytes": wal_size,
    }


# ---------------------------------------------------------------------------
# Direct database benchmarks (no HTTP; isolates query cost)
# ---------------------------------------------------------------------------

def _percentiles(samples: list[float]) -> dict:
    def pct(p):
        if not samples:
            return None
        s = sorted(samples)
        k = max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))
        return round(s[k] * 1000, 2)   # ms
    return {"p50_ms": pct(50), "p95_ms": pct(95), "p99_ms": pct(99),
            "mean_ms": round(statistics.fmean(samples) * 1000, 2)
            if samples else None}


def _time_query(fn, n: int, warmup: int = 3) -> dict:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t)
    return _percentiles(samples)


def db_bench(messages: int, samples: int = 60) -> dict:
    import db  # noqa: E402

    path = str(bench_path(messages))
    conn = db.get_db(path)
    out: dict = {"messages": messages, "queries": {}}
    try:
        # browse first page
        out["queries"]["browse_first_page"] = _time_query(
            lambda: db.browse(conn, limit=50), samples)
        # browse deep: 30 pages in, measured page fetch
        def deep():
            rows, cursor, _ = [], None, True
            for _ in range(30):
                rows, cursor, _ = db.browse(conn, cursor=cursor, limit=50)
            return rows
        out["queries"]["browse_deep_30pages"] = _time_query(deep, max(5, samples // 6))
        # search: common EN term ("recipe" ~ same hit rate as the Arabic term)
        out["queries"]["search_common_en"] = _time_query(
            lambda: db.search(conn, ["recipe"], require_all=False), samples)
        # search: Arabic term
        out["queries"]["search_arabic"] = _time_query(
            lambda: db.search(conn, ["القهوة"], require_all=False), samples)
        # search: multi-phrase OR (like the UI's offer|عرض)
        out["queries"]["search_bilingual_or"] = _time_query(
            lambda: db.search(conn, ["offer", "عرض"], require_all=False), samples)
        # search with a 3-chat filter (scope chips)
        out["queries"]["search_filtered"] = _time_query(
            lambda: db.search(conn, ["offer", "عرض"], require_all=False,
                             chat_ids=[-10012340001, -10012340002, -10012340003]),
            samples)
        # search: rare term
        out["queries"]["search_rare"] = _time_query(
            lambda: db.search(conn, [RARE_TERM], require_all=False), samples)
        # senders aggregate
        out["queries"]["senders_all"] = _time_query(
            lambda: db.senders(conn), samples)
        # senders for a 3-chat selection (UI group filter)
        out["queries"]["senders_filtered"] = _time_query(
            lambda: db.senders(conn, chat_ids=[-10012340001, -10012340002,
                                               -10012340003]), samples)
        # groups aggregate (mirrors the current api/archive.py SQL)
        groups_sql = ("""
            SELECT c.chat_id, c.title, c.kind, c.username, c.last_synced,
                   (SELECT COUNT(*) FROM messages m
                     WHERE m.chat_id = c.chat_id) AS message_count,
                   (SELECT MAX(m.date) FROM messages m
                     WHERE m.chat_id = c.chat_id) AS last_message
            FROM chats c
            WHERE c.tracked = 1
            ORDER BY c.title COLLATE NOCASE""")
        out["queries"]["groups_aggregate"] = _time_query(
            lambda: conn.execute(groups_sql).fetchall(), samples)
        # stats (4 aggregate queries, as the endpoint does)
        out["queries"]["stats"] = _time_query(lambda: db.stats(conn), samples)
        # conversation
        out["queries"]["conversation"] = _time_query(
            lambda: db.conversation(conn, -10012340001, 500),
            max(5, samples // 6))

        # EXPLAIN QUERY PLAN for the two hottest queries
        plans = {}
        for name, sql, params in (
            ("browse", """SELECT m.chat_id, m.msg_id, m.date, m.sender_id,
                    m.sender_name, m.text, m.text_norm, m.has_media, m.edited
                FROM messages m JOIN chats c ON c.chat_id = m.chat_id
                WHERE c.tracked = 1 ORDER BY m.date DESC, m.chat_id DESC,
                    m.msg_id DESC LIMIT 51""", ()),
            ("senders", """SELECT sender_name, COUNT(*) AS count FROM messages
                WHERE sender_name IS NOT NULL AND sender_name != ''
                GROUP BY sender_name ORDER BY count DESC LIMIT 200""", ()),
            ("groups", groups_sql, ()),
        ):
            plans[name] = [
                " ".join(str(r[k]) for k in r.keys())
                for r in conn.execute("EXPLAIN QUERY PLAN " + sql, params)]
        out["explain_query_plan"] = plans
    finally:
        conn.close()
    return out


# ---------------------------------------------------------------------------
# API benchmarks (real app subprocess)
# ---------------------------------------------------------------------------

API_PORT = 8199


def _start_app(db_path: Path):
    env = dict(os.environ)
    env.update({
        "TG_DB_PATH": str(db_path),
        "TG_SESSION_PATH": str(db_path.parent / "bench-session"),
        "TG_API_ID": "123456", "TG_API_HASH": "bench",
        "HOST": "127.0.0.1", "PORT": str(API_PORT),
        "AI_API_KEY": "",          # AI off: deterministic benches only
    })
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "app.py")],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import httpx
    import psutil
    base = f"http://127.0.0.1:{API_PORT}"
    for _ in range(100):
        try:
            if httpx.get(base + "/api/health", timeout=1).status_code == 200:
                return proc, psutil.Process(proc.pid)
        except Exception:
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError("app did not become healthy")


def api_bench(messages: int, samples: int = 100, conc_seconds: float = 12.0,
              conc_workers: int = 8) -> dict:
    import httpx

    db_path = bench_path(messages)
    proc, ps = None, None
    try:
        proc, ps = _start_app(db_path)
        base = f"http://127.0.0.1:{API_PORT}"
        rss_before = ps.memory_info().rss
        client = httpx.Client(base_url=base, timeout=30)

        scenarios = {
            "health": "/api/health",
            "app_state": "/api/app/state",
            "stats": "/api/stats",
            "groups": "/api/groups",
            "senders": "/api/senders",
            "browse_first": "/api/messages?limit=50",
            "message_one": "/api/message/-10012340001/500",
            "context": "/api/message/-10012340001/500/context",
            "search_common": "/api/search?q=recipe&limit=200",
            "search_arabic": "/api/search?q=%D8%A7%D9%84%D9%82%D9%87%D9%88%D8%A9&limit=200",
            "search_bilingual": "/api/search?q=offer%7C%D8%B9%D8%B1%D8%B6&limit=200",
            "search_filtered": "/api/search?q=offer%7C%D8%B9%D8%B1%D8%B6&groups=-10012340001,-10012340002,-10012340003&limit=200",
            "senders_filtered": "/api/senders?groups=-10012340001,-10012340002,-10012340003",
            "search_rare": f"/api/search?q={RARE_TERM}&limit=200",
        }

        out: dict = {"messages": messages, "endpoints": {},
                     "payload_bytes": {}}
        # warmup + latency samples (sequential)
        for name, url in scenarios.items():
            for _ in range(5):
                r = client.get(url)
                if r.status_code != 200:
                    raise RuntimeError(f"{name} -> {r.status_code}: {r.text[:200]}")
            times, sizes = [], []
            for _ in range(samples):
                t = time.perf_counter()
                r = client.get(url)
                times.append(time.perf_counter() - t)
                sizes.append(len(r.content))
            out["endpoints"][name] = _percentiles(times)
            out["payload_bytes"][name] = int(statistics.fmean(sizes))

        # deep browse: follow 30 cursor pages, measure total
        def deep_browse():
            cursor, hops = None, 0
            t = time.perf_counter()
            url = "/api/messages?limit=50"
            while hops < 30:
                u = url + (f"&cursor={cursor}" if cursor else "")
                page = client.get(u).json()
                cursor = page.get("next_cursor")
                if not cursor:
                    break
                hops += 1
            return time.perf_counter() - t
        deep_samples = [deep_browse() for _ in range(8)]
        out["endpoints"]["browse_deep_30pages"] = _percentiles(deep_samples)

        # concurrency: mixed browse/search at N workers for S seconds
        import concurrent.futures
        stop_at = time.monotonic() + conc_seconds
        mix = ["/api/messages?limit=50", "/api/search?q=coffee&limit=200",
               "/api/messages?limit=50", "/api/search?q=offer%7C%D8%B9%D8%B1%D8%B6&limit=200"]

        def worker(i: int):
            count = 0
            while time.monotonic() < stop_at:
                client.get(mix[count % len(mix)])
                count += 1
            return count

        with concurrent.futures.ThreadPoolExecutor(conc_workers) as ex:
            t = time.perf_counter()
            done = sum(ex.map(worker, range(conc_workers)))
            wall = time.perf_counter() - t
        out["concurrency"] = {
            "workers": conc_workers, "seconds": round(wall, 1),
            "requests": done, "req_per_sec": round(done / wall, 1),
        }
        out["rss_after_mb"] = round(ps.memory_info().rss / 1e6, 1)
        out["rss_before_mb"] = round(rss_before / 1e6, 1)
        return out
    finally:
        if proc:
            proc.kill()
            proc.wait(timeout=10)


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["seed", "db", "api", "all"])
    ap.add_argument("--messages", type=int, default=50000)
    ap.add_argument("--samples", type=int, default=100)
    ap.add_argument("--conc-seconds", type=float, default=12.0)
    args = ap.parse_args()

    result: dict = {"command": args.command, "messages": args.messages}
    if args.command in ("seed", "all"):
        result["seed"] = seed(args.messages)
    if args.command in ("db", "all"):
        result["db"] = db_bench(args.messages, samples=min(args.samples, 60))
    if args.command in ("api", "all"):
        result["api"] = api_bench(args.messages, samples=args.samples,
                                  conc_seconds=args.conc_seconds)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

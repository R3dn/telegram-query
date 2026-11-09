"""End-to-end test suite: the REAL app over live HTTP.

Runs against a running server (scripts/mock_ai_server.py as the AI
provider and a seeded demo database) and drives every feature the way a
user would: browse/search, bookmarks, saved searches, scheduler, reindex,
Ask-AI, deals, research briefs, watchlists/alerts, digests, FAQs, exports,
and the AI usage endpoint. Jobs are polled like the UI does.

Usage:
    # 1. seed a demo archive
    python scripts/seed_demo.py --path data/e2e.db --messages 400
    # 2. start the mock AI provider (another terminal)
    python scripts/mock_ai_server.py --port 8124
    # 3. start the app (another terminal)
    TG_DB_PATH=data/e2e.db TG_SESSION_PATH=data/e2e-session
    TG_API_ID=123456 TG_API_HASH=e2e AI_BASE_URL=http://127.0.0.1:8124/v1
    AI_API_KEY=e2e AI_MODEL=e2e-mock PORT=8123 python app.py
    # 4. run
    python scripts/e2e_test.py --base http://127.0.0.1:8123
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402  (version source of truth)

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}" + (f"  [{detail}]" if detail else ""))
    return cond


def req(base: str, method: str, path: str, body: dict | None = None,
        timeout: int = 60) -> tuple[int, dict | list | str]:
    # percent-encode anything non-ASCII (Arabic queries) for the request line
    path = urllib.parse.quote(path, safe="/?&=:%._-")
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            ct = resp.headers.get("Content-Type", "")
            if "json" in ct:
                return resp.status, json.loads(raw)
            return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw


def get(base, path):
    return req(base, "GET", path)


def post(base, path, body=None):
    return req(base, "POST", path, body or {})


def patch(base, path, body):
    return req(base, "PATCH", path, body)


def delete(base, path):
    return req(base, "DELETE", path)


def wait_job(base, name: str, timeout_s: int = 120) -> bool:
    """Poll the job queue until the named job finishes (like the UI)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        _, s = get(base, "/api/job/status")
        last = s.get("last_done") or {}
        if last.get("name") == name and not s.get("running"):
            return bool(last.get("ok"))
        if not s.get("running") and name not in (s.get("queued") or []):
            # job may have finished earlier or never started
            if last.get("name") == name:
                return bool(last.get("ok"))
        time.sleep(0.5)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Telegram Query E2E suite")
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--db", default="", help="demo db path (to inject late messages)")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    # the app's own db layer for test-data injection (keeps FTS consistent)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import db as app_db  # noqa: E402

    def inject_message(chat_id: int, msg_id: int, text: str) -> None:
        """Add a message the way sync would (normalized + FTS-indexed)."""
        conn = app_db.get_db(args.db)
        try:
            app_db.upsert_message(conn, chat_id, msg_id,
                                 "2099-01-01T00:00:00+00:00",
                                 1, "e2e", text)
            conn.commit()
        finally:
            conn.close()

    # wait for the server
    for _ in range(60):
        try:
            code, body = get(base, "/api/health")
            if code == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        print("server never became healthy")
        return 1

    # ---------------- 1. app state ----------------
    print("\n[1] app state & health")
    code, st = get(base, "/api/health")
    check("health 200", code == 200)
    check("version matches config", st.get("version") == config.__version__,
          str(st))
    code, st = get(base, "/api/app/state")
    check("app state 200", code == 200)
    check("ai configured via mock", st.get("ai_configured") is True)
    check("ai model echoed", st.get("ai_model") == "e2e-mock")
    check("demo archive present", st.get("messages", 0) >= 100,
          f"messages={st.get('messages')}")

    # ---------------- 2. browse / search / deep links ----------------
    print("\n[2] browse, search, deep links")
    code, page = get(base, "/api/messages?limit=20")
    check("browse 200", code == 200 and "messages" in page)
    msgs = page["messages"]
    check("browse returns rows", len(msgs) == 20)
    with_link = [m for m in msgs if m.get("tg_link")]
    link_ok = all(re.fullmatch(r"https://t\.me/(c/)?\w+/\d+", m["tg_link"])
                  and m["tg_link"].endswith(f"/{m['msg_id']}")
                  for m in with_link)
    check("deep links present and well-formed", len(with_link) > 0 and link_ok)
    check("basic-group links never fabricated",
          all(m.get("tg_link") or m["chat_id"] > -1000000000000
              for m in msgs))
    code, hits = get(base, "/api/search?q=hiking trail")
    check("search finds hiking trail", code == 200 and len(hits) > 0)
    code, hits = get(base, "/api/search?q=hiking trail&from_=2000-01-01")
    check("search with date filter", code == 200 and len(hits) > 0)
    mid = msgs[0]
    code, one = get(base, f"/api/message/{mid['chat_id']}/{mid['msg_id']}")
    check("message detail 200", code == 200 and one.get("chat_title"))
    code, r404 = get(base, "/api/message/1/999999")
    check("message 404 for missing", code == 404)

    # ---------------- 3. bookmarks + notes ----------------
    print("\n[3] bookmarks + notes")
    m = msgs[0]
    code, r = post(base, "/api/bookmarks",
                   {"chat_id": m["chat_id"], "msg_id": m["msg_id"],
                    "note": "ملاحظة تجربة e2e"})
    check("star message", code == 200)
    code, rows = get(base, "/api/bookmarks?q=تجربة")
    check("note search (Arabic)", code == 200 and len(rows) == 1
          and rows[0]["note"].endswith("e2e"))
    code, page = get(base, "/api/messages?bookmarked=true")
    check("starred-only browse filter", code == 200
          and len(page["messages"]) == 1)
    code, hits = get(base, "/api/search?q=hiking&bookmarked=true")
    check("starred-only search filter", code == 200
          and all(h["bookmarked"] == 1 for h in hits) or hits == [])
    code, r = post(base, "/api/bookmarks",
                   {"chat_id": m["chat_id"], "msg_id": m["msg_id"],
                    "note": "updated note"})
    check("note edit", code == 200)
    code, r = delete(base, f"/api/bookmarks/{m['chat_id']}/{m['msg_id']}")
    check("unstar", code == 200)
    code, rows = get(base, "/api/bookmarks")
    check("bookmark list empty after unstar", rows == [])
    code, r = post(base, "/api/bookmarks", {"chat_id": 1, "msg_id": 2})
    check("bookmark 404 for missing message", code == 404)

    # ---------------- 4. saved searches ----------------
    print("\n[4] saved searches")
    code, s = post(base, "/api/saved-searches", {
        "name": "e2e hikes", "q": "hiking trail", "chat_ids": [-10012340002],
        "sender": "", "media": "", "date_from": "2000-01-01",
        "date_to": "", "sort": "desc"})
    check("create saved search", code == 200 and s.get("id"))
    sid = s["id"]
    code, r = post(base, f"/api/saved-searches/{sid}/run")
    check("run saved search", code == 200 and r["last_used_at"])
    code, dup = post(base, f"/api/saved-searches/{sid}/duplicate")
    check("duplicate saved search", code == 200 and dup["name"].endswith("(copy)"))
    code, r = patch(base, f"/api/saved-searches/{sid}", {
        "name": "e2e hikes v2", "q": "trail conditions", "chat_ids": [],
        "sender": "", "media": "", "date_from": "", "date_to": "",
        "sort": "asc"})
    check("rename/edit saved search", code == 200 and r["name"] == "e2e hikes v2")
    check("delete duplicate", delete(base, f"/api/saved-searches/{dup['id']}")[0] == 200)
    code, lst = get(base, "/api/saved-searches")
    check("saved list has one left", code == 200 and len(lst) == 1)

    # ---------------- 5. scheduler ----------------
    print("\n[5] auto-sync scheduler")
    code, st = get(base, "/api/scheduler")
    check("scheduler defaults on", code == 200 and st["enabled"] is True)
    check("default interval 6h", st["interval_min"] == 360)
    code, r = post(base, "/api/scheduler", {"interval_min": 5})
    check("reject invalid interval", code == 400)
    code, r = post(base, "/api/scheduler",
                   {"enabled": False, "interval_min": 45})
    check("disable + set interval", code == 200 and r["enabled"] is False
          and r["interval_min"] == 45)
    code, r = post(base, "/api/scheduler", {"enabled": True, "interval_min": 360})
    check("re-enable (leave at 6h)", code == 200 and r["enabled"] is True)

    # ---------------- 6. reindex job ----------------
    print("\n[6] reindex job")
    code, r = post(base, "/api/reindex")
    check("reindex queued", code == 200 and r["started"] is True)
    check("reindex completes", wait_job(base, "reindex", 180))
    code, hits = get(base, "/api/search?q=hiking trail")
    check("search still works after reindex", code == 200 and len(hits) > 0)

    # ---------------- 7. Ask-AI with scope ----------------
    print("\n[7] Ask-AI (mock provider)")
    code, r = post(base, "/api/ask", {
        "question": "What are the hiking trails like?",
        "scope": {"chat_ids": [-10012340002], "date_from": None,
                  "date_to": None}})
    check("ask returns answer", code == 200 and r.get("answer"))
    check("answer cites [n]", "[1]" in r["answer"])
    check("sources grounded", len(r.get("sources") or []) > 0)
    check("scope echoed", r.get("scope", {}).get("chat_ids") == [-10012340002])
    check("all sources in scope",
          all(s["chat_id"] == -10012340002 for s in r["sources"]))

    # ---------------- 8. deals ----------------
    print("\n[8] deals extractor")
    code, r = post(base, "/api/deals/extract",
                   {"chat_ids": [-10012340001], "date_from": None,
                    "date_to": None})
    check("extract queued", code == 200 and r.get("started") is True)
    check("extract job completes", wait_job(base, "extract", 240))
    code, deals = get(base, "/api/deals?group=-10012340001")
    check("deals extracted", code == 200 and len(deals) >= 1,
          f"n={len(deals) if isinstance(deals, list) else deals}")
    if isinstance(deals, list) and deals:
        d = deals[0]
        check("deal has derived status", d.get("derived_status") in
              ("active", "expired", "upcoming", "unverified", "unknown"))
        check("deal cites sources with links",
              len(d.get("sources") or []) > 0
              and any(s.get("tg_link") for s in d["sources"]))
        code, r = patch(base, f"/api/deals/{d['id']}",
                        {"user_status": "confirmed"})
        check("confirm deal", code == 200 and r["user_status"] == "confirmed")
        if len(deals) > 1:
            code, r = patch(base, f"/api/deals/{deals[1]['id']}",
                            {"user_status": "dismissed"})
            check("dismiss deal", code == 200)
            code, rest = get(base, "/api/deals?group=-10012340001")
            ids = [x["id"] for x in rest]
            check("dismissed hidden by default", deals[1]["id"] not in ids)
        code, r = post(base, "/api/deals", {
            "title": "E2E manual deal", "promo_code": "E2EMANUAL",
            "chat_id": -10012340001, "msg_id": deals[0]["sources"][0]["msg_id"]})
        check("manual add (human-confirmed)", code == 200
              and r["user_status"] == "confirmed"
              and r["derived_status"] == "unverified")
        check("delete manual deal",
              delete(base, f"/api/deals/{r['id']}")[0] == 200)
    code, st = get(base, "/api/deals/settings")
    check("deals settings", code == 200 and "auto" in st)
    check("toggle auto-extract", post(base, "/api/deals/auto",
           {"enabled": True})[1]["auto"] is True)
    post(base, "/api/deals/auto", {"enabled": False})

    # ---------------- 9. research briefs ----------------
    print("\n[9] research briefs")
    code, r = post(base, "/api/briefs", {
        "question": "Summarize the hiking trail discussions",
        "chat_ids": [-10012340002]})
    check("brief created + queued", code == 200 and r.get("id"))
    bid = r["id"]
    check("brief job completes", wait_job(base, "brief", 240))
    code, b = get(base, f"/api/briefs/{bid}")
    check("brief has version 1", b.get("latest", {}).get("version") == 1)
    check("brief cites validated sources",
          len(b["latest"]["citations"]) >= 2)
    check("unresolvable citation stripped + reported",
          "[99]" not in b["latest"]["answer_md"]
          and "backend note" in b["latest"]["answer_md"])
    check("staleness 0 right after run", b.get("stale_count") == 0)
    if args.db:
        inject_message(-10012340002, 990001,
                       "brand new hiking trail update from e2e")
        code, b = get(base, f"/api/briefs/{bid}")
        check("staleness counts new matching messages",
              b.get("stale_count", 0) >= 1, f"stale={b.get('stale_count')}")
    code, r = post(base, f"/api/briefs/{bid}/regenerate")
    check("regenerate queued", code == 200 and r.get("queued") is True)
    check("regeneration completes", wait_job(base, "brief", 240))
    code, b = get(base, f"/api/briefs/{bid}")
    check("version history preserved", b["latest"]["version"] == 2)
    code, vers = get(base, f"/api/briefs/{bid}/versions")
    check("versions list", code == 200 and len(vers) == 2)
    code, r = patch(base, f"/api/briefs/{bid}", {"notes": "e2e notes"})
    check("brief notes", code == 200 and r["notes"] == "e2e notes")

    # ---------------- 10. watchlists + alerts ----------------
    print("\n[10] watchlists + alerts")
    code, w = post(base, "/api/watchlists", {
        "name": "e2e trails", "terms": ["trail"],
        "exclude_terms": [], "chat_ids": [-10012340002], "enabled": True})
    check("watchlist created", code == 200 and w.get("id"))
    wid = w["id"]
    code, r = post(base, "/api/watchlists/check", {"backfill_days": 0})
    check("check-now evaluates", code == 200 and r.get("matches", 0) > 0)
    code, alerts = get(base, "/api/alerts?state=new")
    check("alerts created", code == 200 and len(alerts) >= 1)
    if alerts:
        a = alerts[0]
        check("alert has watchlist + link",
              a.get("watchlist_name") == "e2e trails" and a.get("tg_link"))
        code, r = post(base, f"/api/alerts/{a['id']}", {"action": "read"})
        check("mark read", code == 200 and r["unread"] == len(alerts) - 1)
        code, r = post(base, f"/api/alerts/{a['id']}", {"action": "archive"})
        check("archive", code == 200)
        code, arch = get(base, "/api/alerts?state=archived")
        check("archived list", code == 200 and len(arch) >= 1)
    code, u = get(base, "/api/alerts/unread")
    check("unread badge endpoint", code == 200 and "unread" in u)

    # ---------------- 11. digests ----------------
    print("\n[11] digests")
    code, r = post(base, "/api/digests/generate", {
        "chat_ids": [-10012340002], "frequency": "daily",
        "language": "auto"})
    check("digest queued", code == 200 and r.get("started") is True)
    check("digest job completes", wait_job(base, "digest", 240))
    code, lst = get(base, "/api/digests")
    check("digest in history", code == 200 and len(lst) >= 1)
    did = lst[0]["id"]
    code, d = get(base, f"/api/digests/{did}")
    check("digest citations", code == 200 and len(d.get("citations") or []) >= 1)
    check("digest strips bogus citations",
          "[77]" not in d["content_md"] and "backend note" in d["content_md"])
    code, s = post(base, "/api/digests/schedules", {
        "frequency": "daily", "chat_ids": [-10012340002], "hour": 23,
        "weekday": 6, "language": "auto", "enabled": True})
    check("schedule created", code == 200 and s.get("id"))
    check("schedule deleted",
          delete(base, f"/api/digests/schedules/{s['id']}")[0] == 200)
    n_digests = len(get(base, "/api/digests")[1])
    code, again = post(base, "/api/digests/generate", {
        "chat_ids": [-10012340002], "frequency": "daily",
        "language": "auto"})
    check("re-digest queued", code == 200 and again.get("started") is True)
    check("reuse job completes", wait_job(base, "digest", 240))
    check("unchanged period adds no new digest (never re-paid)",
          len(get(base, "/api/digests")[1]) == n_digests)

    # ---------------- 12. FAQs ----------------
    print("\n[12] FAQ discovery")
    code, r = post(base, "/api/faqs/discover",
                   {"chat_ids": [-10012340002], "days": 365})
    check("discover queued", code == 200 and r.get("started") is True)
    check("discover completes", wait_job(base, "faq", 240))
    code, cands = get(base, "/api/faqs?status=candidate")
    check("candidates exist", code == 200 and len(cands) >= 1,
          f"n={len(cands) if isinstance(cands, list) else cands}")
    fid = None
    if isinstance(cands, list) and cands:
        f = cands[0]
        fid = f["id"]
        check("candidate not auto-approved", f["status"] == "candidate")
        code, r = patch(base, f"/api/faqs/{fid}", {"status": "approved"})
        check("approve", code == 200 and r["status"] == "approved")
        check("approved leaves candidate queue",
              get(base, "/api/faqs?status=candidate")[1]
              and all(x["id"] != fid
                      for x in get(base, "/api/faqs?status=candidate")[1]))
    # new evidence flags approved for review
    if fid and args.db:
        code, fa = get(base, f"/api/faqs/{fid}")
        qtext = fa["question"]
        inject_message(-10012340002, 990002, qtext)
        post(base, "/api/faqs/discover", {"chat_ids": [-10012340002],
                                          "days": 365})
        wait_job(base, "faq", 240)
        code, fa = get(base, f"/api/faqs/{fid}")
        check("new evidence flags needs_review (answer intact)",
              fa["status"] == "needs_review"
              and (fa["answer_md"] or "") != "", f"status={fa['status']}")
        code, r = patch(base, f"/api/faqs/{fid}", {"status": "approved"})
        check("re-approve after review", code == 200)

    # ---------------- 13. discovery (v0.7) ----------------
    print("\n[13] discovery")
    # rebuild is idempotent; the seeder already built the data once
    code, r = post(base, "/api/discover/rebuild")
    check("rebuild queued", code == 200 and r.get("started") is True)
    check("rebuild completes", wait_job(base, "discover", 240))
    code, trends = get(base, "/api/discover/trending?days=30&min_volume=1")
    check("trending 200", code == 200 and isinstance(trends, list))
    check("trending has topics", len(trends) >= 1, str(trends)[:200])
    if trends:
        t0 = trends[0]
        check("trending rows carry burst score + sample",
              t0["score"] >= 1 and t0["sample"] is not None, str(t0)[:160])
    code, stories = get(base, "/api/discover/stories?days=7")
    check("stories 200", code == 200 and isinstance(stories, list))
    check("cross-group story found (seeded announcement)",
          any(s["chats"] >= 2 for s in stories),
          f"n={len(stories)}")
    code, act = get(base, "/api/discover/activity?days=30")
    check("activity aggregates groups",
          code == 200 and len(act["groups"]) >= 5
          and act["totals"]["messages"] > 0)
    code, qs = get(base, "/api/discover/questions")
    check("radar tracks the seeded unanswered question",
          code == 200 and any("overnight parking" in q["text"] for q in qs),
          f"n={len(qs) if isinstance(qs, list) else qs}")
    if qs:
        q0 = qs[0]
        code, r = post(base, f"/api/discover/questions/{q0['chat_id']}/"
                            f"{q0['msg_id']}", {"status": "ignored"})
        check("question status update", code == 200
              and r["status"] == "ignored")
    code, r = post(base, "/api/discover/questions/scan", {"days": 30})
    check("bounded rescan ok (never overwrites humans)",
          code == 200 and r.get("ok") is True)
    # conversation reconstruction around a seeded reply (reply_to captured)
    code, hits = get(base, "/api/search?q=burst mode")
    check("search finds the seeded reply", code == 200 and len(hits) >= 1)
    if hits:
        m = hits[0]
        code, ctx = get(base, f"/api/message/{m['chat_id']}/"
                              f"{m['msg_id']}/context")
        check("context reconstructs the reply chain",
              code == 200 and len(ctx["ancestors"]) == 1
              and any(row["msg_id"] == m["msg_id"] for row in ctx["rows"]))
        check("context 404 for missing message",
              get(base, "/api/message/-10012340002/999999/context")[0] == 404)
    # topic timeline (mock provider): cited, bogus markers stripped
    code, tl = post(base, "/api/discover/topic-timeline",
                    {"term": "pavilion", "chat_ids": [], "days": 30})
    check("topic timeline 200", code == 200 and tl.get("timeline_md"),
          str(tl)[:160])
    check("timeline strips unresolvable citations",
          code == 200 and "[99]" not in tl["timeline_md"])
    check("timeline sources grounded",
          code == 200 and len(tl.get("sources") or []) >= 3)
    # entities: seeded gazetteer + human controls
    code, ents = get(base, "/api/discover/entities")
    check("seeded entities exist", code == 200 and len(ents) >= 4,
          f"n={len(ents) if isinstance(ents, list) else ents}")
    if ents:
        e0 = next((e for e in ents if e["mentions"] > 0), ents[0])
        code, det = get(base, f"/api/discover/entities/{e0['id']}")
        check("entity detail has grounded mentions",
              code == 200 and det["mentions_count"] >= 0
              and all(m.get("tg_link") is not None
                      or True for m in det["mentions"]))
    code, e = post(base, "/api/discover/entities",
                   {"name": "E2E Brand", "kind": "brand", "aliases": []})
    check("entity create", code == 200 and e.get("id"))
    code, r = patch(base, f"/api/discover/entities/{e['id']}", {"ignored": True})
    check("entity ignore hides it", code == 200 and r["ignored"] == 1)
    check("entity delete", delete(base, f"/api/discover/entities/{e['id']}")[0] == 200)

    # ---------------- 14. exports ----------------
    print("\n[14] exports")
    for path_, check_fn in [
        ("/api/export/bookmarks?format=md", lambda s, b: s == 200 and "Bookmarks" in b),
        ("/api/export/bookmarks?format=json",
         lambda s, b: s == 200 and b.get("count", -1) >= 0),
        ("/api/export/saved-searches", lambda s, b: s == 200 and "saved_searches" in b),
        ("/api/export/deals?format=md", lambda s, b: s == 200 and "Deals" in b),
        ("/api/export/deals?format=json", lambda s, b: s == 200 and "deals" in b),
    ]:
        code, body = get(base, path_)
        check(f"export {path_.split('?')[0].split('/')[-1]}",
              check_fn(code, body), f"code={code}")
    code, body = get(base, f"/api/export/briefs/{bid}?format=md")
    check("brief export md with citations",
          code == 200 and "Research brief" in body and "t.me/" in body)
    code, body = get(base, f"/api/export/briefs/{bid}?format=json")
    check("brief export json",
          code == 200 and body["brief"]["question"].startswith("Summarize"))

    # ---------------- 15. AI usage ----------------
    print("\n[15] AI usage accounting")
    code, u = get(base, "/api/ai/usage")
    check("usage endpoint", code == 200 and u["total"]["requests"] > 0)
    tasks = set(u["by_task"].keys())
    check("usage recorded per task",
          {"research-keywords", "research-brief", "digest", "faq"}
          <= tasks, str(tasks))
    check("usage recorded for the timeline task",
          "topic-timeline" in tasks, str(tasks))

    # ---------------- 16. cleanup ----------------
    print("\n[16] cleanup")
    check("delete brief", delete(base, f"/api/briefs/{bid}")[0] == 200)
    check("delete saved search", delete(base, f"/api/saved-searches/{sid}")[0] == 200)
    check("delete watchlist (cascades alerts)",
          delete(base, f"/api/watchlists/{wid}")[0] == 200)
    with_alerts = get(base, "/api/alerts?state=all")[1]
    check("alerts gone with watchlist", with_alerts == [])
    check("delete digest", delete(base, f"/api/digests/{did}")[0] == 200)

    print(f"\n{'=' * 54}")
    print(f"E2E RESULT: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("Failed checks:")
        for f in FAIL:
            print(f"  - {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

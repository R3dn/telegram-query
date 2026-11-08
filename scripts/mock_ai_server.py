"""A deterministic, OpenAI-compatible mock provider for E2E testing.

Runs a tiny stdlib HTTP server that answers POST /v1/chat/completions by
inspecting the system prompt (the same prompts the app ships) and returning
scripted, schema-valid JSON per task. No network, no keys, fully
deterministic - CI never depends on a real model.

Usage:
    python scripts/mock_ai_server.py            # 127.0.0.1:8124
    python scripts/mock_ai_server.py --port 9000

Point the app at it:
    AI_BASE_URL=http://127.0.0.1:8124/v1 AI_API_KEY=e2e AI_MODEL=e2e-mock python app.py
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _chat_json(body: dict) -> str:
    return json.dumps({
        "id": "e2e", "object": "chat.completion", "created": 0,
        "model": "e2e-mock",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": body["content"]}}],
        "usage": {"prompt_tokens": body.get("pin", 10),
                  "completion_tokens": body.get("pout", 5),
                  "total_tokens": body.get("pin", 10) + body.get("pout", 5)},
    })


def _extract_deals(user_text: str) -> str:
    """Parse the numbered message excerpts and emit one deal per message
    that contains an offer + code - deterministic and grounded."""
    deals = []
    for m in re.finditer(r"\[(\d+)\] \(([^,)]*), ([\d-]+)[^)]*\): (.*)", user_text):
        idx, text = int(m.group(1)), m.group(4)
        code_m = re.search(r"code ([A-Z0-9]+)", text)
        pct_m = re.search(r"(\d+)%", text)
        vendor_m = re.match(r"([A-Za-z'& .]+?):", text)
        if not code_m and not pct_m:
            continue
        deals.append({
            "title": (vendor_m.group(1).strip() if vendor_m else text[:40]) + " offer",
            "description": text[:120],
            "category": "electronics" if "Gadget" in text or "Sleeve" in text else "other",
            "vendor": vendor_m.group(1).strip() if vendor_m else None,
            "discount_pct": float(pct_m.group(1)) if pct_m else None,
            "price": 45.0 if "$45" in text else None,
            "currency": "USD" if "$45" in text else None,
            "promo_code": code_m.group(1) if code_m else None,
            "eligibility": None,
            "geo": None,
            "valid_from": None,
            "expires": (datetime.now(timezone.utc)
                        + timedelta(days=30)).strftime("%Y-%m-%d"),
            "status": "active",
            "confidence": 0.9,
            "source_indexes": [idx],
        })
    return json.dumps({"deals": deals})


def respond(system: str, user_text: str) -> str:
    """One scripted reply per app task, selected by its system prompt."""
    if "extract search keywords for a RESEARCH question" in system:
        return json.dumps({"keywords":
                           ["hiking trail", "trail conditions", "weekend"]})
    if "propose ONE new set of alternative keywords" in system:
        return json.dumps({"keywords": ["trail conditions", "weekend hike"]})
    if "extract search keywords from a question" in system:
        return json.dumps({"keywords": ["hiking trail"],
                           "chat_titles": [], "date_from": None,
                           "date_to": None, "relative_days": None})
    if "extract structured commercial deals" in system:
        return _extract_deals(user_text)
    if "extract named entities" in system:
        # deterministic: every brand-looking word the excerpts contain
        found = []
        for name in ("Aurora Coffee", "Nimbus Hosting", "GadgetHub",
                     "Trail Mix Co"):
            if name.lower() in user_text.lower() and name not in found:
                found.append(name)
        return json.dumps({"entities": [
            {"name": n, "kind": "brand"} for n in found]})
    if "TIMELINE" in system:  # TOPIC TIMELINE task (prompt may line-wrap)
        # cite the first two excerpts; include a bogus marker the backend
        # must strip and report
        return json.dumps({"timeline_md":
            "## Timeline\n- Trail discussions started [1]\n"
            "- Conditions improved over time [2]\n"
            "- A bogus citation [99] must be stripped."})
    if "careful research analyst" in system:
        return json.dumps({"brief_md":
            "## Executive summary\nThe group discusses hiking trails and "
            "weekend plans [1]. Trail conditions vary with weather [2].\n\n"
            "## Recommendations\nArrive before 7am on weekends [2].\n\n"
            "A bogus citation [99] must be stripped by the backend."})
    if "concise research digest" in system:
        return json.dumps({"digest_md":
            "## Top discussions\nHikers shared trail conditions [1] and "
            "weekend plans [3].\nA fake claim [77] must vanish."})
    if "draft a concise FAQ answer" in system:
        return json.dumps({"answer_md":
            "Members recommend arriving before 7am on weekends because "
            "parking fills up quickly, as explained in the replies [3]."})
    if "answer questions about Telegram group messages" in system:
        return ("The groups discuss hiking trails near the north ridge [1]. "
                "Members recommend arriving before 7am on weekends [2].")
    # unknown task: honest, parseable failure so tests notice
    return json.dumps({"error": "mock provider does not know this task"})


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - stdlib naming
        if not self.path.endswith("/chat/completions"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            body = {}
        messages = body.get("messages") or []
        system = next((m["content"] for m in messages
                       if m.get("role") == "system"), "")
        user = next((m["content"] for m in messages
                     if m.get("role") == "user"), "")
        content = respond(system, user)
        payload = _chat_json({"content": content,
                              "pin": len(system) // 4,
                              "pout": len(content) // 4})
        data = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # keep test output quiet
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description="Deterministic mock AI provider")
    ap.add_argument("--port", type=int, default=8124)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"mock AI provider on http://{args.host}:{args.port}/v1/chat/completions")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

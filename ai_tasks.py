"""AI task infrastructure (v0.5): one generic provider runner for all
structured AI workflows (deal extraction, research briefs, digests, FAQ).

Principles (per product spec):
- The provider is a CAPABILITY, not the engine: every feature stays
  functional without it and fails with honest errors when it is missing.
- Never assume JSON mode / structured outputs / streaming: parse the raw
  text, validate against the app's schema, allow ONE repair attempt, and
  never silently accept malformed output or fabricate a result.
- Cache results per (task, scope, model, prompt version, source
  fingerprint): unchanged sources are never re-sent to the provider.
- Track request counts and tokens (estimated when the provider does not
  report usage) so the user can see what features cost.
- Prompts are versioned; outputs record their prompt version and model.

This module does NOT import the task-specific prompts - each feature
module owns its prompt + schema + version.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from datetime import datetime, timezone

import config
import db

__all__ = ["TaskError", "run_task", "run_json_task", "fingerprint_rows",
           "record_usage", "usage_stats", "cache_get", "cache_put",
           "requests_today"]

PROVIDER_ATTEMPTS = 3          # provider-level retries (network/5xx/429)
BACKOFF_MAX_S = 20.0


class TaskError(Exception):
    """A task could not be completed honestly (provider or model output)."""


_CITE_RE = None  # compiled lazily (avoid importing re twice at module init)


def validate_citations(text: str, n_rows: int):
    """Keep only [n] with 1 <= n <= n_rows; strip and report the rest.

    Shared by research briefs, digests, and FAQ answers: the model can never
    keep a citation that does not index a real retrieved row. Returns
    (cleaned_text, removed_numbers, cited_indexes)."""
    global _CITE_RE
    if _CITE_RE is None:
        import re
        _CITE_RE = re.compile(r"\[(\d+)\]")
    removed, cited = [], set()

    def repl(m):
        n = int(m.group(1))
        if 1 <= n <= n_rows:
            cited.add(n)
            return m.group(0)
        removed.append(n)
        return ""

    cleaned = _CITE_RE.sub(repl, text)
    return cleaned, removed, cited


# ---------------------------------------------------------------------------
# Provider access (reuses the single OpenAI-compatible client from ai.py)
# ---------------------------------------------------------------------------

def _get_client():
    import ai
    return ai.get_client()


def _chat_json(client, system, user, model):
    """One provider call returning raw text. Returns (text, usage|None)."""
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=config.settings.ai_temperature,
    )
    text = resp.choices[0].message.content
    usage = getattr(resp, "usage", None)
    return text, usage


def _tokens_of(usage):
    if usage is None:
        return None, None
    return (getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None))


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _call_with_retry(system, user, model):
    """Provider call with exponential backoff + jitter. Never fabricates."""
    import ai as ai_module
    last_exc = None
    for attempt in range(PROVIDER_ATTEMPTS):
        if attempt:
            delay = min(BACKOFF_MAX_S, (2 ** attempt) * 0.5
                        + random.uniform(0, 0.3))
            time.sleep(delay)
        try:
            with ai_module._provider_slot():
                text, usage = _chat_json(_get_client(), system, user, model)
            return text, usage
        except ai_module.AIBusyError:
            raise TaskError(
                "The AI layer is busy with other requests - try again "
                "in a moment.") from None
        except Exception as e:  # noqa: BLE001 - retried below if transient
            if _is_rate_limit(e) and attempt < PROVIDER_ATTEMPTS - 1:
                last_exc = e
                continue
            if _is_transient(e) and attempt < PROVIDER_ATTEMPTS - 1:
                last_exc = e
                continue
            raise TaskError(_friendly(e)) from e
    raise TaskError(_friendly(last_exc))


_RATE_MARKERS = ("rate", "429", "quota", "too many requests", "overloaded")
_TRANSIENT_MARKERS = ("timeout", "timed out", "connection", "temporarily",
                     "502", "503", "504", "reset by peer")


def _is_rate_limit(exc) -> bool:
    s = str(exc).lower()
    return any(m in s for m in _RATE_MARKERS)


def _is_transient(exc) -> bool:
    s = str(exc).lower()
    return any(m in s for m in _TRANSIENT_MARKERS)


def _friendly(exc) -> str:
    s = str(exc)
    if _is_rate_limit(exc):
        return "The AI provider is rate-limiting requests - try again shortly."
    if _is_transient(exc):
        return "The AI provider is unreachable right now - try again shortly."
    return f"The AI provider request failed: {s[:200]}"


# ---------------------------------------------------------------------------
# Fingerprints + caching
# ---------------------------------------------------------------------------

def fingerprint_rows(rows) -> str:
    """Stable hash of the source content: (id, edited-text) of every row."""
    h = hashlib.sha256()
    for r in rows:
        key = f"{r.get('chat_id')}:{r.get('msg_id')}:{r.get('text', '')}"
        h.update(key.encode("utf-8", "replace"))
    return h.hexdigest()


def scope_hash(task: str, payload) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(f"{task}|{blob}".encode()).hexdigest()[:32]


def cache_get(conn, task, scope, model, prompt_version, fingerprint):
    row = conn.execute(
        "SELECT result FROM ai_task_cache WHERE task=? AND scope_hash=? "
        "AND model=? AND prompt_version=? AND fingerprint=?",
        (task, scope, model, prompt_version, fingerprint)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["result"])
    except ValueError:
        return None


def cache_put(conn, task, scope, model, prompt_version, fingerprint, result):
    conn.execute(
        "INSERT OR REPLACE INTO ai_task_cache "
        "(task, scope_hash, model, prompt_version, fingerprint, result, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (task, scope, model, prompt_version, fingerprint,
         json.dumps(result, ensure_ascii=False),
         datetime.now(timezone.utc).isoformat()))


def record_usage(conn, task, requests, tokens_in, tokens_out, model=""):
    conn.execute(
        "INSERT INTO ai_usage (task, requests, tokens_in, tokens_out, model, "
        "created_at) VALUES (?,?,?,?,?,?)",
        (task, requests, tokens_in, tokens_out, model,
         datetime.now(timezone.utc).isoformat()))


def usage_stats(conn) -> dict:
    rows = conn.execute(
        "SELECT task, COUNT(*) requests, SUM(tokens_in) tin, SUM(tokens_out) tout "
        "FROM ai_usage GROUP BY task").fetchall()
    total = conn.execute(
        "SELECT COUNT(*) requests, COALESCE(SUM(tokens_in),0) tin, "
        "COALESCE(SUM(tokens_out),0) tout FROM ai_usage").fetchone()
    models = conn.execute(
        "SELECT model, COUNT(*) requests FROM ai_usage "
        "WHERE model != '' GROUP BY model ORDER BY requests DESC").fetchall()
    return {
        "by_task": {r["task"]: {"requests": r["requests"],
                                "tokens_in": r["tin"],
                                "tokens_out": r["tout"]} for r in rows},
        "by_model": {r["model"]: r["requests"] for r in models},
        "total": {"requests": total["requests"],
                  "tokens_in": total["tin"], "tokens_out": total["tout"]},
    }


# ---------------------------------------------------------------------------
# Daily budget guard (v0.7): a hard, deterministic request cap. 0 = off.
# ---------------------------------------------------------------------------

def requests_today(conn) -> int:
    start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
    return conn.execute(
        "SELECT COALESCE(SUM(requests), 0) r FROM ai_usage WHERE created_at >= ?",
        (start,)).fetchone()["r"]


def _check_daily_cap(conn):
    """Raise an honest TaskError when the daily AI request cap is reached."""
    cap = config.settings.ai_daily_cap
    if cap <= 0:
        return
    used = requests_today(conn)
    if used >= cap:
        raise TaskError(
            f"Daily AI request cap reached ({used}/{cap} today, UTC). "
            "Deterministic features keep working; raise TGQ_AI_DAILY_CAP "
            "or wait for the cap to reset at 00:00 UTC.")


# ---------------------------------------------------------------------------
# Task runner
# ---------------------------------------------------------------------------

def run_task(system: str, user: str, task: str, model_role: str = "synth") -> str:
    """Plain text task: provider call + retry + usage recording.
    ``model_role`` ('extract' | 'synth') selects the routed model."""
    if not config.settings.ai_configured:
        raise TaskError("AI is not configured - set AI_API_KEY in Settings.")
    model = config.settings.model_for(model_role)
    guard = db.get_db()
    try:
        _check_daily_cap(guard)
    finally:
        guard.close()
    text, usage = _call_with_retry(system, user, model)
    tin, tout = _tokens_of(usage)
    conn = db.get_db()
    try:
        record_usage(conn, task, 1,
                     tin if tin is not None else _estimate_tokens(system + user),
                     tout if tout is not None else _estimate_tokens(text),
                     model)
        conn.commit()
    finally:
        conn.close()
    return text


def run_json_task(system: str, user: str, task: str,
                  validate, repair_system: str | None = None,
                  cache: tuple | None = None,
                  model_role: str = "extract"):
    """Structured task: call -> parse -> validate -> ONE repair -> result or
    TaskError. ``validate`` returns (ok, error_or_None). ``cache`` is an
    optional (conn, task, scope, prompt_version, fingerprint) tuple: a hit
    skips the provider entirely; a miss stores the validated result.
    ``model_role`` ('extract' | 'synth') selects the routed model - the
    cheap/fast model for structured extraction, the general model for
    synthesis tasks."""
    if not config.settings.ai_configured:
        raise TaskError("AI is not configured - set AI_API_KEY in Settings.")

    model = config.settings.model_for(model_role)
    conn = cache[0] if cache else None
    own_conn = conn is None
    if cache and conn is not None:
        _check_daily_cap(conn)
        hit = cache_get(conn, task, cache[2], model, cache[3], cache[4])
        if hit is not None:
            return hit, True   # (result, from_cache)
    else:
        guard = db.get_db()
        try:
            _check_daily_cap(guard)
        finally:
            guard.close()

    import ai as ai_module
    requests = 0
    tokens_in = tokens_out = 0
    try:
        for attempt in (1, 2):
            text, usage = _call_with_retry(system, user, model)
            requests += 1
            tin, tout = _tokens_of(usage)
            tokens_in += tin if tin is not None else _estimate_tokens(system + user)
            tokens_out += tout if tout is not None else _estimate_tokens(text)
            parsed = ai_module._parse_json(text)   # fence-tolerant
            if parsed is not None:
                ok, err = validate(parsed)
                if ok:
                    if cache and conn is not None:
                        cache_put(conn, task, cache[2], model, cache[3],
                                  cache[4], parsed)
                    return parsed, False
            if attempt == 1 and repair_system is not None:
                # ONE repair attempt: show the model its exact mistake
                user = (f"Your previous reply was invalid.\n"
                        f"Problem: {err or 'not valid JSON'}\n"
                        f"Return ONLY the corrected JSON matching the schema.\n\n"
                        f"Previous reply (may be truncated):\n{text[:2000]}")
                system = repair_system or system
        raise TaskError(
            "The AI returned an invalid response twice (schema violation) - "
            "nothing was saved. Try again or use a stronger model.")
    finally:
        if requests:
            c2 = db.get_db() if own_conn else conn
            try:
                record_usage(c2, task, requests, tokens_in, tokens_out, model)
                c2.commit()
            finally:
                if own_conn:
                    c2.close()

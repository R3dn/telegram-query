# Security Audit — Telegram Query v1.0.1 → v1.0.2 engineering pass

Audit date: 2026-11-12 · Reviewer scope: full-repository security review
(layered on top of `SECURITY_REVIEW.md`, which remains the record for the
v0.8.1/v9 findings — nothing in it was contradicted by this pass).

Method: every input path re-reviewed line-level (all FastAPI routers,
all SQL, every file write, all subprocess/native calls), all
`dangerouslySetInnerHTML` sites traced to their sanitizer, secret
handling re-verified end-to-end, plus adversarial probes executed
against the real app via TestClient (malformed/oversized/negative
parameters, malicious message content, prompt-injection payloads).

## Threat model (unchanged)

Single trusted user on their own Windows machine; the browser is the
app's own WebView2 window. Assets: the archive DB, the Telegram session
file (bearer credential), AI/Telegram keys. Adversaries: visited web
pages (CSRF/DNS rebinding), malicious Telegram message content
(prompt injection / HTML-in-archive attempts), and accidental misuse.
Local malware is out of scope (owns the machine).

## Verified in this pass (checked, no finding)

| Area | Check | Result |
|---|---|---|
| Loopback binding | `config.HOST` default `127.0.0.1`; desktop mode forces loopback with a loud warning on override | ✅ intact |
| Host-allowlist middleware | Foreign-`Host` probe → 403; IPv6 bracket + port forms parsed correctly | ✅ intact |
| CORS | No CORS headers anywhere (grep) — same-origin only | ✅ |
| SQL injection | Every query parameterized; f-strings only build `?`-placeholder lists or fixed literals (all `api/*` re-read) | ✅ |
| Path traversal | No user-controlled filesystem paths; exports use fixed ASCII names; import validates an existing archive dir; erase deletes explicit targets only | ✅ |
| XSS in archive rendering | Message text renders as React text nodes (`{m.text}`); the only `innerHTML` surface is `mdToHtml` (7 call sites) which escapes **all** HTML before adding markup — `<script>`, `<img onerror>`, attribute-injection probes all render inert (unit-pinned) | ✅ |
| ReDoS via search queries | `highlightRegex` escapes regex metacharacters; alternation-of-literals is linear | ✅ |
| Prompt injection | System prompts frame excerpts as DATA; every `[n]` citation validated against real retrieved rows server-side; unresolvable markers stripped and reported | ✅ |
| Secrets | Keys never echoed (setup endpoints write-only), never logged, `ai_provider_host` is display-only; frontend bundle contains no secrets (verified the API client never receives them) | ✅ |
| `.env` handling | `update_env` rejects newlines (line-injection guard); strict pydantic patterns on wizard fields | ✅ |
| Temp files | Migration staging is cleaned; SQLite backup API used for consistent copies; no `tempfile` residue paths found | ✅ |
| Installer privileges | MSI is perMachine with standard Program Files ACLs; user data is per-user `%LOCALAPPDATA%`; uninstall removes only `INSTALLDIR` | ✅ |
| Dependencies | Installed set (fastapi 0.141.1, uvicorn 0.52.1, openai 3.19.2, telethon 1.45.0, httpx 0.28.1, pywebview 6.2.1, Pillow 10.x) — no published advisories found against these versions at audit time; majors-only upper bounds keep upgrades conscious | ✅ (see R-2) |

## Findings this pass

### Fixed (details in `bug-audit.md`)

| ID | Severity | Summary |
|---|---|---|
| BUG-03 | Low (security) / Medium (robustness) | Negative `limit` on 7 list endpoints became SQLite `LIMIT -1` = **unbounded** — one local request could serialize the entire archive (and `/api/messages` returned a silently empty page). Not remotely reachable (host guard), but it violated the endpoint contracts. Fixed with `max(1, min(...))` clamps everywhere + regression tests. |
| BUG-04 | Low (security-adjacent) | A requested filter (media) that was displayed as active but silently ignored violates the "honest UI" posture; invalid values now get a 400 instead of being silently dropped or coerced. |

### Accepted / documented risks (unchanged posture, re-validated)

1. **No API authentication** — by design for loopback-only, single-user
   desktop use. Controls: loopback default, desktop forces loopback,
   host guard, loud warning on unsafe bind. Any network exposure
   requires the authenticating-proxy gate in `SECURITY_REVIEW.md`.
2. **`AI_BASE_URL` is operator-controlled SSRF surface** — only the
   local operator can set it; cross-origin browser abuse is blocked by
   the host guard.
3. **Session file is a bearer credential on disk** — gitignored, never
   leaves the machine, `log_out()` deletes it; OS ACLs are the user's
   control (documented).
4. **`httpx` logs provider URLs at INFO** — noise, never the key.

## Recommendations (not implemented in this pass — change-surface kept minimal)

- **R-1:** Add `pip-audit` to CI as a scheduled/weekly job (not
  per-push) so dependency advisories surface without coupling every
  build to the advisory feed.
- **R-2:** Consider a `pip-compile` lockfile for the *packaging*
  environment (runtime bounds are already majors-only and tested
  together).
- **R-3:** The in-app "Erase all data" is correct but reachable with a
  short typed token; if multi-user machines ever become a target,
  require the same token plus the archive's message count (a
  knowledge-proof of ownership).

## Pre-exposure checklist

Unchanged from `SECURITY_REVIEW.md` §"Pre-exposure checklist" — the
app remains desktop-only; the checklist applies only if someone
chooses to put it behind a reverse proxy (explicitly out of the
product's architecture; decision 0010).

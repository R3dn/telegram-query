# Feature Development Guide — Telegram Query

How to add things to this codebase without breaking its architecture.
Every example mirrors the real structure of this app (file names,
conventions, and the reasoning behind them). The audit
(`ARCHITECTURE_AUDIT.md`) explains why the boundaries look as they do;
this guide shows how to work inside them.

## 0. Golden rules (from the codebase's own patterns)

1. **Deterministic first**: anything computable from the archive
   (SQL/Python over `text_norm`, metadata) must not call the AI. AI is
   a capability on top, never the engine (watchlists/discovery are the
   models).
2. **Watermark-incremental**: post-sync work only ever touches genuinely
   new messages (per-chat high-water mark). Never scan the whole
   archive per run — deals/decisions/discover/entities/watchlists all
   follow this.
3. **One Telegram job at a time**: everything that touches the session
   goes through `jobs.JOBS` (serialized), never the request thread.
4. **Honest AI**: schema-validate output, allow one repair, fail loudly
   (TaskError), cache by fingerprint, record usage, never save
   fabricated results (`ai_tasks`).
5. **Human gates**: machine output never silently overwrites human
   state (`user_status`, approved FAQs, question statuses).
6. **Parameterized SQL only**; no new dependencies without measurable
   justification; every schema change ships a migration.

## 1. Adding an API endpoint

Suppose: "show the longest message in a group".

`api/archive.py` (thin router — request-shape validation + SQL or a
call into `db.py`/feature module; open your own connection):

```python
@router.get("/api/messages/longest")
def longest_message(groups: str = ""):
    with open_db() as conn:
        row = conn.execute(
            """SELECT m.chat_id, m.msg_id, m.text, length(m.text) AS n
               FROM messages m JOIN chats c ON c.chat_id = m.chat_id
               WHERE c.tracked = 1 AND length(m.text) > 0
                 AND (? = '' OR m.chat_id IN (SELECT chat_id FROM chats))
               ORDER BY n DESC LIMIT 1""",
            ()).fetchone()   # real filters: build ?-placeholders
        return dict(row) if row else None
```

Conventions: sync `def` (threadpool handles it — do not add `async`
without a measured reason), `open_db()` context manager, JSON-safe
dicts, `JSONResponse({"error": ...}, status_code=...)` for user-facing
failures. Add the client method in `web/src/api/client.ts` and the type
in `web/src/api/types.ts`.

## 2. Adding a database entity + migration

Example: a `reactions` table. In `db.py`:

1. Add the `CREATE TABLE IF NOT EXISTS reactions (...)` to `SCHEMA`
   (fresh databases).
2. Bump `SCHEMA_VERSION` (9 → 10) and add a branch in `_migrate`:

```python
if current < 10:
    # v10: reactions on archived messages (created by SCHEMA for new
    # databases; existing ones get it here). No data transforms.
    current = 10
```

Rules: **additive-only, idempotent, never destructive**. If a new
index references a column that older databases don't have yet (see the
v9 comment in SCHEMA for the `reply_to` case), create it in the
migration branch **after** the branch that adds the column — not in
`SCHEMA`. Data-carrying migrations: keep them small, test them against
a fixture of the previous schema (`tests/test_migration.py` has the
pattern), and prefer "flag + background job" for large rewrites (the
reindex/discover backfill jobs are the templates).

3. Tests in `tests/test_engineering.py` style: fresh-DB has it, old-DB
   upgrade path preserves data, version recorded.

## 3. Adding a Telegram ingestion capability

Work inside `sync.py` + `jobs.py` — never call Telethon from a request
handler.

- New job kind: `jobs.JOBS.start("myjob", my_job_fn)` — add the name to
  the dedupe set in `JobRunner.start` if it should dedupe, print
  progress (it streams to the UI), honor `from sync import CANCEL`
  between batches, checkpoint to `chats`/`app_settings` so it resumes.
- Post-processing on every sync: register a hook in `app.py` lifespan
  (`jobs.POST_SYNC_HOOKS`) — zero-arg function, opens its own
  connection, **watermark-incremental**, exceptions logged never fail
  the sync (wrap in try/except like `watchlists.post_sync_hook`).
- Time-based work: `jobs.TICK_HOOKS` (runs on the scheduler's 30 s
  tick, receives a connection; must stay cheap when idle —
  `digests.enqueue_due` is the model).

## 4. Adding an AI provider / model

The provider layer is one seam: **`ai.get_client()`** returns any
OpenAI-compatible client (base_url + key from settings). To support a
new provider, no code is needed if it speaks the OpenAI chat-completions
protocol — set `AI_BASE_URL`/`AI_API_KEY` in the wizard or `.env`.
That is the design constraint: **do not add provider-specific modules**;
route through `ai_tasks`:

- Structured task: `ai_tasks.run_json_task(system, user, task="mytask",
  validate=my_validate, cache=(conn, task, scope_hash, PROMPT_VERSION,
  fingerprint), model_role="extract")` — you get retry/backoff, one
  repair, fingerprint caching, usage accounting, and the daily cap
  for free.
- Version your prompt (`PROMPT_VERSION = "myfeature-v1"`) so cached
  results invalidate when the prompt changes.
- Per-task model routing already exists: `AI_MODEL_EXTRACT` (cheap
  structured), `AI_MODEL_SYNTH` (prose), falling back to `AI_MODEL`.
- Frontend surface for failures: catch `ai_tasks.TaskError` →
  `JSONResponse({"error": str(e)}, status_code=400)`.

Adding a *non*-OpenAI-compatible provider would mean abstracting
`get_client`/`_chat` behind a tiny protocol — do it only when that
second protocol actually arrives (YAGNI guard).

## 5. Adding a frontend page

1. Create `web/src/components/MyView.tsx`. Read state from
   `useStore()` (context store) — it already carries app state, groups,
   selection, toasts, modals. Fetch via `api.*` from
   `web/src/api/client.ts`; add types in `api/types.ts`.
2. Register the route-mode in two places: the `FeedMode` union
   (`state/store.tsx`) and the render switch in `App.tsx`:
   `mode === "myview" ? <MyView /> : ...`. Add a nav entry in
   `Sidebar.tsx` (and `MobileNav` if it should be a bottom-tab).
3. States that must exist: loading skeleton, empty state, error toast
   (store's `toast`), and a `<EmptyState>` when the archive is empty.
4. For request-heavy interactions, pass an `AbortSignal` (the store's
   pattern) and keep the 3 000-row DOM cap in mind for any list view.

## 6. Adding a background job (visible or invisible)

- **Visible** (progress in the UI): `jobs.JOBS.start(name, fn)` + a
  starter endpoint in the relevant `api/` router (see
  `/api/discover/rebuild`). Print progress; the UI polls
  `/api/job/status` and shows the log.
- **Invisible maintenance**: post-sync/tick hooks (§3).
- Jobs must be idempotent + resumable: checkpoint state in the DB
  (`backfill_floor` and the JSON watermarks in `app_settings` are the
  two checkpoint idioms).

## 7. Adding a configuration option

`config.py`: field on the `Settings` dataclass + parse in
`load_settings()` (validate/clamp there — fail fast on garbage), plus a
row in the README table and `docs/configuration.md`. If the wizard
should set it, extend `api/setup.py` with a strict pydantic model and
`config.update_env` (never log the value; reject newlines). Remember
`update_env` hot-reloads `config.settings` — code that caches derived
values must re-read settings (the AI client cache in `ai.py` is the
example: it keys on the values, not the object).

## 8. Adding tests (and what must be covered)

Backend (`tests/`):

- DB-level behavior on the `conn` fixture (fresh temp DB per test).
- API behavior on the `api_client` fixture (session DB — seed via
  `db.get_db()` with no path, like the API tests do).
- AI features: monkeypatch `ai.get_client` with a fake returning canned
  JSON (see `test_discover.FakeClient` / `test_digests`); never hit a
  real provider.
- Sync logic: fake Telethon clients (see `test_sync_logic.py`, and
  `test_engineering.py` for the all-chats-fail propagation pattern).
- Anything touching migrations: old-schema fixture → upgrade → assert
  data + version (see `test_migration.py`, `test_engineering.py`).

Frontend (`web/tests/`): vitest + Testing Library, DOM-level, fake
fetch. Run everything:

```bash
ruff check . && python -m pytest
cd web && npm run typecheck && npm test && npm run build
```

E2E (journey-level, real app + mock provider + seeded archive):
`scripts/e2e_test.py` — extend it when you add a user-visible journey.

Performance-sensitive changes: `scripts/benchmark.py seed|db|api
--messages N` before and after; put the delta in the PR description.
The 500 k run takes ~5 min total and caught a 1 000× pagination
regression during v9 — treat it as a required gate for SQL/schema
changes.

## 9. Definition of done for a feature

- Deterministic core works with **no AI configured** (or the feature
  is explicitly AI-only and fails honestly without one).
- Watermarks/checkpoints: rerunning after a kill loses nothing and
  duplicates nothing.
- UI: loading/empty/error states; errors are actionable text.
- Tests at the level the feature lives (DB/API/pipeline), plus E2E if
  it's a user journey.
- Docs touched: README table (config), `docs/architecture.md` module
  map (new files), this guide if a new pattern was born.

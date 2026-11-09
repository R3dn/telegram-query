# Contributing

Thanks for helping improve Telegram Query — a local-first, privacy-first
tool. Please read [docs/privacy.md](docs/privacy.md) first: any change that
moves user data off the local machine needs a very good reason.

## Getting set up

```bash
git clone <your-fork-url> && cd Telegram_quary
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt -r requirements-dev.txt
pytest                      # backend tests (no network needed)
cd web && npm install
npm test && npm run build   # frontend tests + production build
```

Python 3.10+ and Node 20+ are required (Node only for frontend work — the
built `web/dist` is committed, so backend-only contributors can skip it).

## Ground rules

1. **Keep it local-first.** The archive, session, and credentials stay on
   the user's machine. AI calls only send the excerpts a question retrieves.
2. **Run the checks before pushing:** `ruff check .`, `pytest`, and in
   `web/`: `npm run typecheck && npm test && npm run build`.
3. **Never commit** real session files, databases, `.env`, or message data
   from a real archive. Use `python scripts/seed_demo.py` to test with
   synthetic data.
4. **No new heavy dependencies** without opening an issue first. The
   backend stays at five runtime deps on purpose.
5. **Respect the schema:** migrations are additive-only and versioned
   (`db._migrate`); never drop or silently rewrite user data.
6. For UI work, match the existing design tokens (`web/src/design/`) —
   restrained palette, one accent, small radii, no gradients.
7. **SQL/schema/perf changes need a benchmark run** —
   `python scripts/benchmark.py seed|db|api --messages 500000` before and
   after (a 500k-row run takes ~5 minutes and caught a 1,000× pagination
   regression during v9). Record the delta in the PR. See
   [docs/engineering/](docs/engineering/) for the baseline and reports.

## Useful scripts

| Script | Purpose |
|---|---|
| `scripts/seed_demo.py` | synthetic demo archive (testing, screenshots) |
| `scripts/mock_ai_server.py` | deterministic OpenAI-compatible fake for E2E |
| `scripts/e2e_test.py` | full-journey E2E against a running app + mock provider |
| `scripts/benchmark.py` | repeatable performance harness (5k/50k/500k rows) |
| `scripts/backup_db.py` | online, consistent archive snapshot |

## Screenshots for visual changes

After UI changes, regenerate the README screenshots with synthetic data only:

```bash
pip install playwright && python -m playwright install chromium
python scripts/take_screenshots.py
```

The script seeds a throwaway demo archive (ten fictional English groups via
`scripts/seed_demo.py`), boots an isolated app instance whose environment
blocks your real `.env`, and fails if any real identifier appears in a
capture. Never screenshot your real archive for the docs.

## Pull requests

- One logical change per PR; describe *why*, not just *what*.
- Add or update tests for anything behavioral. Bug fixes need a failing
  test first when practical.
- Screenshots for visual changes (synthetic data only).
- The frontend build (`web/dist`) is committed — run `npm run build` after
   frontend changes so end users without Node get the update.

## Reporting bugs

Open an issue with your OS, Python version, and the exact error. Logs are
safe to share **only if** they contain none of your real message content.

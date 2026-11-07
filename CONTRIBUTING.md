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

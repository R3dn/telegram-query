# Security Policy

## Reporting a vulnerability

Please open a private security advisory on GitHub
(**Security → Report a vulnerability**) or contact a maintainer directly.
Do not open public issues for suspected vulnerabilities.

## Security model

Telegram Query is a **single-user, local-first** application:

- The server binds to `127.0.0.1` by default. It has **no authentication
  layer** — anyone who can reach the port can read your archive and trigger
  Telegram actions. Do not expose it to a network without adding your own
  auth (reverse proxy with auth, VPN, SSH tunnel).
- A **Host-allowlist middleware** rejects requests whose Host header is not
  the local machine (blocks cross-site form POSTs and DNS rebinding from
  other websites). Extra hosts can be allowed via `TG_ALLOWED_HOSTS` —
  only if you deliberately expose the app.
- Secrets (`TG_API_HASH`, `AI_API_KEY`) live in `.env` and server memory
  only. They are never sent to the browser, echoed back by API responses,
  or written to logs. Setup endpoints reject values that could inject
  extra `.env` lines (newlines / unusual characters).
- The Telegram session file and message database stay in your data
  directory and are gitignored.
- All SQL is parameterized; message text is HTML-escaped before rendering.
- Ask-AI sends only the retrieved excerpts for the question you asked to
  the AI endpoint you configured — see [docs/privacy.md](docs/privacy.md).
  Archived messages are passed to the model strictly as data; the system
  prompt instructs the model to ignore any instructions embedded in them.

## Trust boundaries

| Component | Trust level | Notes |
|---|---|---|
| Local browser → app | Trusted (localhost) | No auth by design |
| App → Telegram | Your credentials | Via your own API ID/hash |
| App → AI provider | Your choice | Only on Ask-AI, only excerpts |

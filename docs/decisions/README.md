# Technical decisions

Numbered decision records. Each states the choice, the context, and the
consequences — including rejected alternatives. Append-only; supersede
with a new record, never edit history.

---

## 0001 — Multi-account support deferred (2026-11-08)

**Decision.** v0.10 will not implement multi-account. The supported
pattern for a second account is a second installation
(`TG_DATA_DIR` + `TG_DB_PATH` + `TG_SESSION_PATH`).

**Context.** Multi-account appeared on the v0.10 candidate list, but the
architecture treats a single Telegram session as a core invariant: the
JobRunner serializes all work because a Telethon session is one SQLite
file that corrupts under concurrent use. Chat ownership across accounts
(sessions, auth flow, per-account data ownership, UI switching) would
add real complexity and risk for a product whose persona is one person
with one personal account.

**Consequences.** No per-account UI or sync complexity; the local-first
trust posture is intact. Revisit only with a documented user need, and
then as explicit profile switching — never concurrent sessions.

## 0002 — Semantic retrieval is benchmark-gated (2026-11-08)

**Decision.** Embeddings/hybrid retrieval may ship in v0.8 only if a
benchmark on Arabic/Arabizi/mixed queries shows it measurably beats
FTS5 recall@k at realistic scale. Off by default; no vector database —
brute-force cosine at SQLite scale at most.

**Context.** Measured FTS5 performance (500k messages: 69ms browse,
344ms worst search) is sufficient, and the bilingual normalization
(dialects, Arabizi, elongation) already recovers most semantic-adjacent
matches deterministically. A vector DB/Postgres re-architecture would
break the one-pip-install moat.

**Consequences.** `AI_MODEL_EMBED` config exists but nothing uses it
until the gate passes. The benchmark harness is a v0.8 deliverable, and
its result is recorded here either way.

## 0003 — Discover is the landing view (2026-11-08)

**Decision.** v0.7 adds a "Discover" nav group (Discover, Entities) at
the top of the sidebar, and the app opens on Discover rather than the
message feed. Mobile nav leads with Discover. Browse stays one click
away.

**Context.** Discovery is the product's front door ("what's happening in
my communities") — a stronger product statement than a raw feed, and
the deterministic core means the landing view is fast and free.
Nav discipline: ≤3 groups, ≤2 new items per release.

**Consequences.** Existing muscle memory changes (one click to Browse);
e2e and store tests assert the new default mode.

## 0004 — AI model routing and daily budget cap (2026-11-08)

**Decision.** Three optional model roles over the same provider —
`AI_MODEL_EXTRACT` (structured extraction: deals, entities, keyword
extraction), `AI_MODEL_SYNTH` (answers, briefs, digests, FAQ answers,
timelines), `AI_MODEL_EMBED` (reserved) — each falling back to
`AI_MODEL`. `TGQ_AI_DAILY_CAP` caps total AI requests per UTC day with
honest errors; `ai_usage` records the serving model.

**Context.** Users run cheap and free OpenAI-compatible endpoints;
cheap models are usually good enough for schema-constrained extraction
while synthesis benefits from a stronger tier. Nothing is hardcoded to
a provider or model; the deterministic cores are never affected by caps
or provider failures.

**Consequences.** The shared task layer owns routing (no per-feature
provider code); caches are keyed by model so switching models re-runs
work once, then caches again.

## 0005 — Entities: never individual people (2026-11-08)

**Decision.** The entity gazetteer covers brands, products,
organizations, projects, services, places, and events — and the LLM
discovery prompt forbids extracting individual people's names. Group
activity is aggregate only (volume, media share, hour histogram).

**Context.** The product's privacy posture (no member analytics, no
profiling) is a differentiator, not just a constraint. Content-level
knowledge (what was said about a brand) is in scope; person-level
statistics never are.

**Consequences.** Mention rows never reference a person-as-entity;
entity merge/ignore gives humans control over the gazetteer.

## 0006 — Question radar reuses FAQ detection; human statuses are final (2026-11-08)

**Decision.** The unanswered-questions radar shares `faq.is_question`
(one bilingual interrogative definition, no duplicate heuristics), runs
incrementally above a watermark, auto-resolves a parent question when a
substantive reply arrives, and never overwrites human
answered/ignored statuses on rescans. A reply that is itself a question
is a follow-up, not an answer, and replies inside threads are not fresh
questions. Approved FAQ answers are offered as suggestions — the human
gate stays.

**Context.** Two question-detectors would drift; the FAQ pipeline
already encodes the product's conventions for threads and evidence.

**Consequences.** One question-detector definition for both features; the
FAQ pipeline's thread and evidence conventions apply everywhere.
`open_questions` rows start `open`, and auto-resolution (a substantive
reply) only touches rows still `open` — a human `answered`/`ignored` is
final and rescans never overwrite it. Approved FAQ answers reach the
radar as suggestions through the existing approval gate; there is no
second path to trusted knowledge.

## 0007 — Decisions reuse the deals contract; status is evidence-derived (2026-11-09)

**Decision.** The v0.8 decisions & commitments tracker is built on the
deals pipeline end to end: bilingual keyword net → FTS5 candidates →
near-duplicate collapse (forwards stay citations) → batched
schema-constrained extraction (one repair attempt, invalid output
discarded) → source verification against the archive → strict identity
merge (`title+owner+due_date`) → typed rows with per-row citations and
confirm/dismiss/correct gates. The model's own status judgment lives in
`status`; `derived_status` computes what the app shows: `completed`/
`cancelled` only when the message's own words say so, `overdue` for a
past due date, `unverified` without evidence — a record is never
silently "committed" forever.

**Context.** The deals pipeline already encodes the product's contract
(citations must resolve, caches keyed by fingerprint, per-chat
watermarks for incremental runs, human gates before anything counts as
knowledge). Decisions are the same shape of problem — structured
extraction over conversations with verifiable evidence — so a second
architecture would only drift. `overdue` is computed from due dates
rather than stored, so a growing backlog never requires rescans and
follow-up tracking (P0 #2) can build on the same deterministic check.

**Consequences.** One more AI surface with the same disclosure and
minimization posture (keyword-matched candidates only, cached by
fingerprint). Schema v7 adds `decisions` + `decision_sources`
(additive, idempotent). Future follow-up tracking reads
`derived_status` instead of duplicating the rule; the model's raw
judgment stays inspectable in its own column for auditing.

## 0008 — Follow-ups are keywords; evidence is reverse-citable (2026-11-09)

**Decision.** Follow-up tracking (v0.8 P0 #2) is deterministic keyword
matching, never AI: an open decision is checked for newer messages
matching at least two of its title's distinctive keywords (the shared
discovery stopword pack, one bilingual definition), searched only in
its own source chats and only above a per-chat watermark (the newest
message already in its story — citations ∪ stored follow-ups).
The Evidence Explorer (v0.8 P0 #3) is one read-only endpoint that
answers "what references this message?" by joining every citation
table — deals, decisions (source and follow-up), brief versions,
digests, alerts, FAQ clusters (question and answer side), entity
mentions — plus the message's own thread context.

**Context.** Follow-ups are exactly the class of feature this codebase
refuses to send to a provider: the signal is "people are still talking
about this," which keywords answer honestly and deterministically, and
a model would only add cost plus a new trust question. The watermark
pattern (deals/discovery/watchlists) already exists, so the check
rides the post-sync hook without a new scheduler. The Evidence
Explorer's value is trust verification: every AI feature stores
verifiable citations, but until now the only way to audit them was to
know the record first — the reverse direction makes any message prove
what was built on it.

**Consequences.** `decision_followups` (schema v8) stores matched
terms per row so every follow-up is auditable; the check is bounded
(decisions × source chats × capped FTS query) and incremental by
construction. The Evidence Explorer stays read-only — no new write
surface, no AI involvement, honest about pre-v0.5 `reply_to` gaps via
the existing conversation rules. FAQ sources are scanned in Python
over the small clustered set, keeping the query portable across
SQLite builds. Frontend focus plumbing (`evidenceFocus`) lets any
back-reference jump to its record and expand it without per-view
custom state.

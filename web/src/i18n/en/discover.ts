/** UI strings: view "discover". */
import type { Dict } from "../types";

export const dict: Dict = {
  // header
  "discover.subtitle":
    "deterministic - computed from your archive, no AI required",
  "discover.window.last": "last {n} days",
  "discover.rebuild.button": "Rebuild data",
  "discover.rebuild.title":
    "Rebuild all discovery data from the archive (visible job)",
  "discover.rebuild.queued": "Discovery rebuild queued - watch Jobs",
  "discover.rebuild.alreadyQueued": "A discovery job is already queued",

  // scope chip
  "discover.scope.label": "Scope:",
  "discover.scope.one": "{n} group",
  "discover.scope.many": "{n} groups",
  "discover.scope.clearHint": "(clear to see all groups)",

  // empty archive
  "discover.empty.title": "Nothing to discover yet",
  "discover.empty.hint":
    "Sync your groups first - trending topics, cross-group stories and " +
    "unanswered questions appear here automatically after every sync.",
  "discover.toast.openOriginalFailed": "Could not open the original message",

  // trending topics
  "discover.trending.title": "Trending topics",
  "discover.trending.note":
    "recent volume vs the prior window - click through to the messages",
  "discover.trending.empty": "No topic stood out in the last {n} days.",
  "discover.trending.openTitle": "Open matching messages in the feed",
  "discover.trending.openSample": "Open the sample message",
  "discover.trending.badgeTitle": "recent vs prior window",
  "discover.trending.new": "new",
  "discover.trending.oneMsg": "{n} msg",
  "discover.trending.msgs": "{n} msgs",
  "discover.trending.oneGroup": "{n} group",
  "discover.trending.groups": "{n} groups",

  // topic timeline
  "discover.timeline.button": "Timeline",
  "discover.timeline.badge": "topic timeline",
  "discover.timeline.analyzing": "analyzing messages…",
  "discover.timeline.sources": "Sources ({n})",
  "discover.toast.citationMissing": "Citation [{n}] has no matching message",

  // cross-group stories
  "discover.stories.title": "Cross-group stories",
  "discover.stories.note": "the same post forwarded across your communities",
  "discover.stories.empty": "No cross-group forwards in the last {n} days.",
  "discover.stories.badge": "{g} groups · {n} copies",

  // open questions
  "discover.questions.title": "Unanswered questions",
  "discover.questions.titleCount": "Unanswered questions ({n})",
  "discover.questions.note":
    "questions with no reply - answer one, or let the FAQ answer it",
  "discover.questions.scan": "Scan recent",
  "discover.questions.scanNote":
    "re-checks the last 30 days; human statuses are never overwritten",
  "discover.questions.empty": "No open questions - the communities answer fast.",
  "discover.questions.open": "Open",
  "discover.questions.markAnswered": "answered",
  "discover.questions.ignore": "ignore",
  "discover.questions.noResponse": "no response seen",
  "discover.questions.faqMatch": "an approved FAQ answer matches",
  "discover.toast.scanned": "Scanned - {n} new open question(s)",
  "discover.toast.answered": "Marked answered",
  "discover.toast.ignored": "Question ignored",

  // group activity
  "discover.activity.title": "Group activity (30 days)",
  "discover.activity.note":
    "aggregate only - no per-member analytics exists in this product",
  "discover.activity.empty": "No messages in the last 30 days.",
  "discover.activity.toggleTitle": "Toggle this group in the scope",
  "discover.activity.stats": "{n} msgs · {p}/day",
  "discover.activity.more": "+{n} more groups",
};

/** UI strings: view "watch" — watchlists + the alerts inbox. */
import type { Dict } from "../types";

export const dict: Dict = {
  // watchlists toolbar
  "watch.subtitle":
    "keyword monitors — no AI required, evaluated after every sync",
  "watch.checkNow": "Check now",
  "watch.checkNowHint": "Evaluate everything above the watermark",
  "watch.checkBackfill": "Check last 7 days",
  "watch.checkBackfillHint": "Re-scan recent days for this check only",
  "watch.newList": "New watchlist",
  "watch.checkedNew": "{n} new alerts — {u} unread",
  "watch.checkedNone": "No new matches",

  // watchlist cards
  "watch.emptyTitle": "No watchlists yet",
  "watch.emptyHint":
    "Create a keyword watchlist (e.g. kubernetes, عرض, SAVE20) and Telegram " +
    "Query will alert you when tracked groups mention it — no manual " +
    "searching, no AI calls.",
  "watch.badgeNew": "{n} new",
  "watch.paused": "paused",
  "watch.pause": "Pause",
  "watch.resume": "Resume",
  "watch.edit": "Edit",
  "watch.deleted": "Watchlist deleted",

  // watchlist editor
  "watch.editTitle": "Edit watchlist",
  "watch.modalNote":
    "Terms match like search does (Arabic normalization included). Matching " +
    "is deterministic and runs after each sync — your messages are never " +
    "sent to an AI provider for this.",
  "watch.fieldName": "Name",
  "watch.phName": "e.g. k8s jobs · عروض التقنية",
  "watch.fieldTerms": "Terms (comma-separated)",
  "watch.phTerms": "kubernetes, k8s, وظائف",
  "watch.fieldExcludes": "Exclude terms (optional)",
  "watch.phExcludes": "pricing",
  "watch.fieldScope": "Groups (empty = all)",
  "watch.needNameAndTerm": "Name and at least one term are required",
  "watch.created": "Watchlist created",
  "watch.updated": "Watchlist updated",

  // alerts inbox
  "watch.tabNew": "New",
  "watch.tabRead": "Read",
  "watch.tabArchived": "Archived",
  "watch.refresh": "Refresh",
  "watch.emptyNew": "No new alerts",
  "watch.emptyRead": "No read alerts",
  "watch.emptyArchived": "No archived alerts",
  "watch.emptyNewHint":
    "Watchlist matches land here right after each sync. Nothing new since " +
    "your last look.",
  "watch.emptyOtherHint": "Nothing here yet.",
  "watch.markRead": "Mark read",
  "watch.archive": "Archive",
  "watch.jump": "Jump",
  "watch.matchedTerm": "matched: “{term}”",
  "watch.jumpFailed": "Could not open the original message",
};

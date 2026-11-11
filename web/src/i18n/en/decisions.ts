/** UI strings: view "decisions". */
import type { Dict } from "../types";

export const dict: Dict = {
  // toolbar
  "decisions.searchPlaceholder": "Search decisions…",
  "decisions.filterStatus": "Status filter",
  "decisions.anyStatus": "Any status",
  "decisions.filterKind": "Kind filter",
  "decisions.anyKind": "Any kind",
  "decisions.filterGroup": "Group filter",
  "decisions.sort": "Sort",
  "decisions.sortDue": "Due soonest",
  "decisions.sortConfidence": "Most confident",
  "decisions.checkFollowups": "Check follow-ups",
  "decisions.checkFollowupsHint":
    "Deterministic keyword check — also runs after every sync",
  "decisions.exportMd": "Export .md",
  "decisions.exportJson": ".json",
  "decisions.exported": "Exported",
  "decisions.extract": "Extract decisions",
  "decisions.extractHint": "Analyze the archive for decisions and commitments",
  "decisions.aiNeeded": "Configure an AI provider first",

  // monitor row
  "decisions.openLabel": "open",
  "decisions.nOverdue": "{n} overdue",
  "decisions.showOverdue": "Show overdue decisions",
  "decisions.nDueSoon": "{n} due soon",
  "decisions.dueSoonHint": "Due within 7 days",
  "decisions.nWithFollowups": "{n} with follow-ups",
  "decisions.followupsHint": "Decisions with newer messages discussing them",
  "decisions.followupsNote": "follow-up checks run after every sync",

  // auto-extraction row
  "decisions.autoHint": "After each sync, analyze only the new messages",
  "decisions.autoLabel": "auto-extract new messages after each sync",
  "decisions.autoOn": "Auto-extraction on",
  "decisions.autoOff": "Auto-extraction off",
  "decisions.autoNote": "extraction sends candidate message excerpts to {host}",

  // empty states
  "decisions.noMatch": "No decisions match",
  "decisions.empty": "No decisions yet",
  "decisions.tryDifferent": "Try different filters.",
  "decisions.emptyAiHint":
    "Run “Extract decisions” to analyze your groups for decisions, " +
    "commitments, and plans. Extraction only sends candidate messages — " +
    "never your whole archive.",
  "decisions.emptyNoAiHint":
    "Configure an AI provider (Settings) to enable extraction, or add " +
    "decisions manually.",

  // decision card
  "decisions.badgeConfirmed": "Confirmed",
  "decisions.confirmed": "Confirmed",
  "decisions.followupOne": "{n} follow-up",
  "decisions.followupMany": "{n} follow-ups",
  "decisions.followupsTitle": "{n} newer message(s) discuss this decision",
  "decisions.dueSoon": "due soon",
  "decisions.sourceOne": "{n} source",
  "decisions.sourceMany": "{n} sources",
  "decisions.confidence": "{label} confidence",
  "decisions.sourcesLabel": "Sources ({n})",
  "decisions.deletedFromArchive": "[deleted from archive]",
  "decisions.followupsLabel":
    "Follow-ups ({n}) — newer messages about this decision",
  "decisions.dismiss": "Dismiss",
  "decisions.dismissed": "Dismissed",
  "decisions.markCompleted": "Mark completed",
  "decisions.markedCompleted": "Marked completed",
  "decisions.correctOwner": "Correct the owner",
  "decisions.ownerPlaceholder": "Owner…",
  "decisions.saveOwner": "Save owner",
  "decisions.ownerUpdated": "Owner updated",
  "decisions.correctDue": "Correct the due date",
  "decisions.saveDue": "Save due date",
  "decisions.dueUpdated": "Due date updated",
  "decisions.deleted": "Decision deleted",
  "decisions.followupsFound": "Found {n} new follow-up(s)",
  "decisions.noNewFollowups": "No new follow-ups",

  // extract modal
  "decisions.extractNote":
    "Analyzes messages that match decision/commitment keywords inside the " +
    "selected scope, then sends only those candidates (in batches) to " +
    "your AI provider. Existing decisions are merged by identity — never " +
    "duplicated. The job and its progress are visible in Jobs.",
  "decisions.scope": "Scope",
  "decisions.noGroups": "No tracked groups yet.",
  "decisions.dateRange": "Date range (optional)",
  "decisions.startExtract": "Start extraction",
  "decisions.extractQueued": "Extraction queued — watch Jobs for progress",
  "decisions.extractAlreadyQueued": "Extraction already queued",
};

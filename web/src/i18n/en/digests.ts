/** UI strings: view "digests" — scheduled + on-demand cited summaries. */
import type { Dict } from "../types";

export const dict: Dict = {
  // toolbar
  "digests.subtitle":
    "every item cites its sources; unchanged periods are never re-analyzed",
  "digests.newSchedule": "New schedule",
  "digests.newScheduleOption": "New schedule…",
  "digests.newDaily": "Daily digest",
  "digests.newWeekly": "Weekly digest",
  "digests.lastDay": "Digest last day",
  "digests.lastDayHint": "Summarize the last 24h",
  "digests.lastWeek": "Digest last week",
  "digests.lastWeekHint": "Summarize the last 7 days",
  "digests.aiRequired": "Configure an AI provider first",

  // on-demand scope
  "digests.scopeLabel": "On-demand scope (groups):",

  // schedule rows
  "digests.schedules": "Schedules",
  "digests.freqWeekly": "weekly",
  "digests.atHour": "at {h}:00 UTC",
  "digests.scopeGroups": "{n} groups",
  "digests.lastRun": "last: {date}",
  "digests.scheduleDeleted": "Schedule deleted",

  // history feed
  "digests.emptyTitle": "No digests yet",
  "digests.emptyHintAi":
    "Generate one on demand (last day / last week) or create a schedule — " +
    "digests run automatically and are archived with their citations.",
  "digests.emptyHintAiOff":
    "Configure an AI provider (Settings) to enable digests.",
  "digests.backAll": "All digests",
  "digests.deleted": "Digest deleted",
  "digests.citations": "Citations ({n})",
  "digests.deletedFromArchive": "[deleted from archive]",
  "digests.scheduled": "scheduled",
  "digests.onDemand": "on demand",
  "digests.queued": "Digest generation queued — watch Jobs",
  "digests.alreadyQueued": "A digest job is already queued",

  // schedule editor
  "digests.newScheduleTitle": "New digest schedule",
  "digests.schedNote":
    "The digest is generated automatically around your chosen hour (UTC) " +
    "and saved with its citations. Nothing is re-sent when the period has " +
    "not changed.",
  "digests.frequency": "Frequency",
  "digests.daily": "Daily",
  "digests.weekly": "Weekly",
  "digests.hourUtc": "Hour (UTC)",
  "digests.language": "Language",
  "digests.langAuto": "Auto-detect",
  "digests.fieldScope": "Groups (empty = all)",
  "digests.create": "Create",
  "digests.scheduleCreated": "Schedule created",
};

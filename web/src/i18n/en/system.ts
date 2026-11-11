/** UI strings: view "system". */
import type { Dict } from "../types";

export const dict: Dict = {
  // section headers
  "system.section.general": "General",
  "system.section.data": "Data",
  "system.section.appearance": "Appearance",
  "system.section.telegram": "Telegram",
  "system.section.autoSync": "Auto-sync (v0.4)",
  "system.section.normalization": "Search normalization",
  "system.section.ai": "AI provider",

  // language + theme
  "system.language": "Language",
  "system.theme": "Theme",
  "system.theme.dark": "Dark",
  "system.theme.light": "Light",

  // telegram section
  "system.account": "Account",
  "system.loggedIn": "logged in",
  "system.loggedInAs": "logged in as {user}",
  "system.notLoggedIn": "not logged in",
  "system.checking": "checking…",
  "system.apiCredentials": "API credentials",
  "system.configured": "configured",
  "system.missing": "missing",
  "system.change": "change",
  "system.saveCredentials": "Save credentials",
  "system.logoutTelegram": "Log out of Telegram",
  "system.loggedOut": "Logged out of Telegram",
  "system.credsSaved": "Credentials saved",

  // auto-sync section
  "system.autoSync": "Automatic sync",
  "system.on": "On",
  "system.off": "Off",
  "system.interval": "Interval",
  "system.sched.note":
    "The schedule is stored in your local database and survives restarts; if the app was closed past a due time, one catch-up sync runs on the next start. It never overlaps a running sync.",
  "system.sched.next": "Next:",
  "system.sched.last": "Last successful sync:",
  "system.schedSaved": "Auto-sync settings saved",

  // search normalization section
  "system.normLevel": "Normalization level",
  "system.normExtended": "extended (Arabizi · Gulf dialect · elongation)",
  "system.reindex": "Rebuild search index",
  "system.reindexTitle":
    "Rewrite the search index with the current normalization rules. Runs as a background job.",
  "system.reindexQueued": "Reindex job queued — see {jobs}",
  "system.reindexAlready": "Reindex already queued",
  "system.norm.noteA":
    "Extended normalization folds Arabic-Indic digits (٢٥ → 25), collapses chat elongation (هااااي → هاي), folds Arabizi digits inside Latin words, and maps common Gulf dialect words to standard forms — at index and query time, so both sides always match. Original message text is never modified. Set",
  "system.norm.noteB": "in .env for the v0.3 behavior, then use “{button}”.",

  // ai provider section
  "system.provider": "Provider",
  "system.aiNotConfigured": "not configured",
  "system.saveProvider": "Save provider",
  "system.aiUsage": "AI usage (this machine)",
  "system.aiUsageTitle": "Requests and estimated tokens recorded locally per AI feature",
  "system.usageBadge": "{requests} · ~{tokens} tokens",
  "system.ai.noteA":
    "AI answers send retrieved message excerpts to the configured provider endpoint. Keys stay server-side, are written to your local",
  "system.ai.noteB":
    ", and are never sent back to the browser. Everything else never leaves this machine.",

  // erase all data (Settings → Data)
  "system.eraseTitle": "Erase all data",
  "system.eraseOpen": "Erase…",
  "system.eraseConfirmHint":
    "Permanently deletes your entire archive on this machine: the database, the Telegram session, and your settings. This cannot be undone.",
  "system.eraseTypePrompt": "Type {word} to confirm",
  "system.eraseGo": "Erase everything",
  "system.eraseDone": "All data erased — reloading the app",
  "system.eraseFailed": "Erase failed",
  "system.eraseRowDb": "Database",
  "system.eraseRowSession": "Telegram session",
  "system.eraseRowConfig": "Settings & backups",

  // job center
  "system.jobs.queued": "queued",
  "system.jobs.usingSession": "The current job is using the Telegram session.",
  "system.jobs.noneRunning": "No job is running.",
  "system.jobs.runsAfter": "Runs after the current job finishes.",
  "system.jobs.stoppingSaved": "Stopping at the next checkpoint — progress is saved",
  "system.jobs.cancelledQueued": "Cancelled queued: {jobs}",
  "system.jobs.retrySync": "Retry: sync queued",
  "system.jobs.retryDialogs": "Retry: group listing queued",
  "system.jobs.retryTrack": "Open {manage} to retry tracking",
  "system.jobs.stopCurrent": "Stop current job",
  "system.jobs.cancelQueued": "Cancel {n} queued",
  "system.jobs.retryLast": "Retry last job",
  "system.refresh": "Refresh",
  "system.jobs.liveLog": "Live log",
  "system.jobs.noOutput": "(no output yet)",

  // manage groups
  "system.mm.loadingGroups": "Loading your groups from Telegram…",
  "system.mm.waitingJob": "Waiting for {job}… stop it if you need the list now",
  "system.mm.loadFailed": "Could not load the group list from Telegram",
  "system.mm.tickFirst": "Tick the groups you want to track first",
  "system.mm.trackedQueued": "Tracking {groups} — queued behind {jobs}",
  "system.mm.trackedBackfill": "Tracking {groups} — full history backfill starting",
  "system.mm.untrackedDeleted": "Untracked — messages permanently deleted",
  "system.mm.untrackedKept": "Untracked — messages kept on disk (re-track to restore)",
  "system.mm.allTracked": "All your Telegram groups are already tracked.",
  "system.mm.trackSelected": "Track selected",
  "system.mm.reloadList": "Reload Telegram list",
  "system.mm.trackedSection": "Tracked groups",
  "system.mm.othersSection": "Telegram groups not tracked yet",
  "system.mm.noneTrackedHint": "No groups tracked yet — pick some below.",
  "system.mm.untrack": "untrack",
  "system.mm.untrackArmed": "keeps messages — sure?",
  "system.mm.deleteArmed": "delete {n} msgs — sure?",
  "system.mm.untrackTitle":
    "Stop archiving this group. Messages are kept on disk and reappear if you track it again.",
  "system.mm.deleteTitle": "Permanently delete this group's messages from the archive.",
  "system.mm.fetching": "Fetching your group list from Telegram…",
  "system.mm.stoppingList": "Stopping — the list loads next",
  "system.lastMessage": "last {date}",
  "system.starting": "(starting…)",
  "system.alreadyTracking": "Already tracking those groups",
  "system.trackFailed": "Could not start tracking",

  // localized count nouns (English uses .one/.many)
  "system.pl.group.one": "{n} group",
  "system.pl.group.many": "{n} groups",
  "system.pl.job.one": "{n} job",
  "system.pl.job.many": "{n} jobs",
  "system.pl.request.one": "{n} request",
  "system.pl.request.many": "{n} requests",
};

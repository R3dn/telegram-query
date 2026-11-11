/** Shell strings: app identity, navigation, sync card, mobile nav,
 *  right panel, and actions shared across views. */
import type { Dict } from "../types";

export const dict: Dict = {
  "app.name": "Telegram Query",

  // nav groups + items
  "nav.discover": "Discover",
  "nav.entities": "Entities",
  "nav.browse": "Browse & search",
  "nav.askAi": "Ask AI",
  "nav.bookmarks": "Bookmarks",
  "nav.jobs": "Jobs",
  "nav.deals": "Deals",
  "nav.decisions": "Decisions",
  "nav.research": "Research",
  "nav.faqs": "FAQs",
  "nav.watchlists": "Watchlists",
  "nav.alerts": "Alerts",
  "nav.digests": "Digests",
  "nav.group.discover": "Discover",
  "nav.group.knowledge": "Knowledge",
  "nav.group.monitor": "Monitor",
  "nav.groups": "Groups",

  // groups section
  "groups.filterPlaceholder": "Filter groups…",
  "groups.all": "All groups",
  "groups.messagesCount": "{n} messages",
  "groups.msgs": "{n} msgs",
  "groups.noMatch": "No groups match.",
  "groups.noneTracked": "No groups tracked yet.",
  "groups.manage": "Manage groups",
  "groups.channel": "Channel",
  "groups.group": "Group",

  // saved searches
  "saved.title": "Saved searches",
  "saved.rename": "Rename",
  "saved.duplicate": "Duplicate",
  "saved.delete": "Delete",
  "saved.clickAgain": "Click again to delete",
  "saved.filtersOnly": "filters only",
  "saved.browseWith": "browse with these filters",

  // sync card
  "sync.running": "{job} running…",
  "sync.done": "{job} done",
  "sync.failed": "{job} failed",
  "sync.idle": "Idle",
  "sync.queued": "{n} queued",
  "sync.autoNext": "auto-sync {interval} · next {time}",
  "sync.configureHint": "Configure in Settings",
  "sync.lastOk": "last ok {when}",
  "sync.backfills": "{n} backfills can resume",
  "sync.now": "Sync now",
  "sync.details": "Details",
  "sync.started": "Sync started",
  "sync.alreadyQueued": "Sync is already queued",

  // footer
  "shell.setupWizard": "Setup wizard",
  "shell.settings": "Settings",

  // right panel
  "panel.askAi": "Ask AI",
  "panel.details": "Details",
  "panel.detailsHint": "Select a message to see details",
  "panel.dragResize": "Drag to resize",
  "panel.show": "Show panel",
  "panel.hide": "Hide panel",

  // shared actions / misc
  "action.clear": "clear",
  "action.close": "Close",
  "action.cancel": "Cancel",
  "action.save": "Save",
  "action.delete": "Delete",
  "action.rename": "Rename",
  "action.confirm": "Confirm",
  "action.copy": "Copy text",
  "action.copied": "Copied",
  "action.openTelegram": "Open in Telegram",
  "action.viewConversation": "View in conversation",
  "action.view": "View",
  "state.loading": "loading…",

  // short labels for the mobile bottom nav (must not duplicate the
  // sidebar's accessible button names)
  "nav.browseShort": "Browse",

  // background job names (utils/format.ts jobKey)
  "job.sync": "Sync",
  "job.track": "Group backfill",
  "job.dialogs": "Group listing",
  "job.auth": "Login",
  "job.reindex": "Reindex",
  "job.discover": "Discovery backfill",
  "job.extract": "Deals extraction",
  "job.decisions": "Decisions extraction",
  "job.brief": "Research brief",
  "job.unknown": "Job",
  "job.finished": "finished",
  "job.failed": "failed",

  // scheduler intervals (utils/format.ts intervalKey)
  "interval.everyDay": "every day",
  "interval.everyDays": "every {n} days",
  "interval.everyHours": "every {n}h",
  "interval.everyMin": "every {n} min",
};

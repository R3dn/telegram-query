/** UI strings: view "bookmarks". */
import type { Dict } from "../types";

export const dict: Dict = {
  // sticky toolbar
  "bookmarks.title": "Bookmarks",
  "bookmarks.searchPlaceholder": "Search notes and messages…",
  "bookmarks.exportMd": "Export .md",
  "bookmarks.exportJson": "Export .json",
  "bookmarks.exportDone": "Exported: {name}",

  // row actions
  "bookmarks.jump": "Jump",
  "bookmarks.telegram": "Telegram",
  "bookmarks.copyLink": "Copy link",
  "bookmarks.linkCopied": "Link copied",
  "bookmarks.copyFailed": "Copy failed",

  // empty states
  "bookmarks.emptyTitle": "No bookmarks yet",
  "bookmarks.emptyHint":
    "Star messages in the feed (or the Details panel) to keep them " +
    "here. Notes stay on this machine and are never sent to the AI.",
  "bookmarks.noMatchTitle": "No bookmarks match",
  "bookmarks.noMatchHint": "Nothing matches that search. Try a different word.",
};

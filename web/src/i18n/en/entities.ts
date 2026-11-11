/** UI strings: view "entities". */
import type { Dict } from "../types";

export const dict: Dict = {
  // header
  "entities.subtitle": "brands, products, orgs, places - never individual people",
  "entities.searchPlaceholder": "Search entities…",
  "entities.sort.recent": "Recent activity",
  "entities.sort.mentions": "Most mentioned",
  "entities.add.submit": "Add",

  // AI discovery toggle
  "entities.autoLabel":
    "AI discovery of new entities (opt-in; runs incrementally after each sync, cached by content)",
  "entities.toast.autoOn":
    "AI discovery on - new entities are found incrementally after each sync (cached, opt-out any time)",
  "entities.toast.autoOff":
    "AI discovery off - matching continues with the current gazetteer",

  // rows
  "entities.row.mention": "{n} mention",
  "entities.row.mentions": "{n} mentions",
  "entities.row.recent": "{n} this week",
  "entities.row.lastSeen": "last seen {d}",
  "entities.hideHint": "Hide from discovery (keep history)",
  "entities.toast.hidden": "Entity hidden",

  // detail
  "entities.backToList": "All entities",
  "entities.detail.stats": "{n} mentions · {g} group(s)",
  "entities.detail.groupChip": "{n} mention(s)",
  "entities.hideFromDiscovery": "hide from discovery",
  "entities.mergeInto": "Merge this entity into…",
  "entities.mergeHint": "Fold this entity's mentions and aliases into another one",
  "entities.toast.merged": "Entities merged - mentions and aliases moved over",
  "entities.toast.deleted": "Entity deleted (mentions were references only)",
  "entities.detail.mentions": "Mentions",
  "entities.detail.noMentions": "No mentions yet - they accumulate after each sync.",
  "entities.detail.older": "+{n} older mention(s)",

  // empty state + add form
  "entities.empty.title": "No entities yet",
  "entities.empty.hintSynced":
    "Add brands/products manually, seed them from your extracted deals " +
    "(Rebuild data in Discover), or turn on AI discovery to find them " +
    "incrementally after each sync.",
  "entities.empty.hintNoSync": "Sync your groups first.",
  "entities.add.title": "New entity",
  "entities.add.namePlaceholder": "Name, e.g. GadgetHub",
  "entities.add.aliasesPlaceholder": "Aliases (comma-separated)",
  "entities.toast.added": "Entity added",
};

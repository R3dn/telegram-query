/** UI strings: view "deals". */
import type { Dict } from "../types";

export const dict: Dict = {
  // toolbar
  "deals.searchPlaceholder": "Search deals…",
  "deals.filterStatus": "Status filter",
  "deals.anyStatus": "Any status",
  "deals.filterCategory": "Category filter",
  "deals.anyCategory": "Any category",
  "deals.filterGroup": "Group filter",
  "deals.sort": "Sort",
  "deals.sortDiscount": "Biggest discount",
  "deals.sortPrice": "Lowest price",
  "deals.exportMd": "Export .md",
  "deals.exportJson": ".json",
  "deals.exported": "Exported",
  "deals.extract": "Extract deals",
  "deals.extractHint": "Analyze the archive for offers",
  "deals.aiNeeded": "Configure an AI provider first",

  // auto-extraction row
  "deals.autoHint": "After each sync, analyze only the new messages",
  "deals.autoLabel": "auto-extract new messages after each sync",
  "deals.autoOn": "Auto-extraction on",
  "deals.autoOff": "Auto-extraction off",
  "deals.autoNote": "extraction sends candidate message excerpts to {host}",

  // empty states
  "deals.noMatch": "No deals match",
  "deals.empty": "No deals yet",
  "deals.tryDifferent": "Try different filters.",
  "deals.emptyAiHint":
    "Run “Extract deals” to analyze your groups for offers, or add one " +
    "manually. Extraction only sends candidate messages — never your " +
    "whole archive.",
  "deals.emptyNoAiHint":
    "Configure an AI provider (Settings) to enable extraction, or add " +
    "deals manually.",

  // deal card
  "deals.badgeConfirmed": "Confirmed",
  "deals.confirmed": "Confirmed",
  "deals.sourceOne": "{n} source",
  "deals.sourceMany": "{n} sources",
  "deals.confidence": "{label} confidence",
  "deals.who": "who: {v}",
  "deals.where": "where: {v}",
  "deals.from": "from: {v}",
  "deals.sourcesLabel": "Sources ({n})",
  "deals.deletedFromArchive": "[deleted from archive]",
  "deals.dismiss": "Dismiss",
  "deals.dismissed": "Dismissed",
  "deals.correctExpiry": "Correct the expiry date",
  "deals.saveExpiry": "Save expiry",
  "deals.expiryUpdated": "Expiry updated",
  "deals.deleted": "Deal deleted",

  // extract modal
  "deals.extractNote":
    "Analyzes messages that match deal keywords inside the selected scope, " +
    "then sends only those candidates (in batches) to your AI provider. " +
    "Existing deals are merged by identity — never duplicated. The job " +
    "and its progress are visible in Jobs.",
  "deals.scope": "Scope",
  "deals.noGroups": "No tracked groups yet.",
  "deals.dateRange": "Date range (optional)",
  "deals.startExtract": "Start extraction",
  "deals.extractQueued": "Extraction queued — watch Jobs for progress",
  "deals.extractAlreadyQueued": "Extraction already queued",
};

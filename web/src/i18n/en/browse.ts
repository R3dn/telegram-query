/** UI strings: browse workspace (search bar, filter bar, feed). */
import type { Dict } from "../types";

export const dict: Dict = {
  // search bar
  "search.placeholder": "Search messages…  (press /)",
  "search.activePlaceholder": "Search active - Enter to re-run, Esc to clear",
  "search.backToBrowse": "Back to browse",
  "search.recent": "Recent searches",

  // filter bar
  "filter.browse": "Browse",
  "filter.search": "Search",
  "filter.allTime": "All time",
  "filter.today": "Today",
  "filter.days": "{n} days",
  "filter.custom": "Custom range",
  "filter.anySender": "Any sender",
  "filter.anyType": "Any type",
  "filter.withImages": "With images",
  "filter.textOnly": "Text only",
  "filter.newestFirst": "Newest first",
  "filter.oldestFirst": "Oldest first",
  "filter.starred": "Starred",
  "filter.starredHint": "Show only bookmarked messages",
  "filter.save": "Save search",
  "filter.saveHint": "Save this search + filters under a name",
  "filter.moreOnScroll": "more on scroll",
  "filter.chip.from": "from {date}",
  "filter.chip.sender": "sender: {name}",
  "filter.chip.images": "with images",
  "filter.chip.text": "text only",
  "filter.chip.oldest": "oldest first",
  "filter.chip.starred": "starred",
  "filter.chip.groups": "{n} group(s)",
  "filter.allGroups": "all groups",
  "filter.saveTitle": "Save search",
  "filter.saveNote":
    "Saves the query, selected groups, and filters - not the result rows. " +
    "Run it any time to re-execute against the live archive.",
  "filter.savePlaceholder": "Name, e.g. أروع العروض / best deals",
  "filter.savedToast": "Saved “{name}”",

  // feed
  "feed.marked": "Bookmarked",
  "feed.unmarked": "Bookmark removed",
  "feed.markHint": "Bookmark this message",
  "feed.unmarkHint": "Remove bookmark",
  "feed.edited": "edited",
  "feed.hasImage": "has image",
  "feed.unknown": "unknown",
  "feed.noResults": "No results",
  "feed.noResultsHint":
    "Nothing matches “{q}” with the current filters. Try different " +
    "wording, fewer filters, or alternative spellings.",
  "feed.archiveEmpty": "Your archive is empty",
  "feed.archiveEmptyHint":
    "Track some groups and run your first sync to start building a " +
    "searchable archive of your Telegram messages.",
  "feed.noMatch": "No messages match",
  "feed.noMatchHint":
    "No messages match the current filters. Widen the date range or " +
    "clear a filter.",
  "feed.searchPrompt": "Search your archive",
  "feed.searchPromptHint":
    "Type above and press Enter. Separate alternative words with | - " +
    "e.g.  offer|عرض",
  "feed.loadingOlder": "loading older messages…",
  "feed.loadOlder": "Load older messages",
  "feed.showingNewest":
    "Showing the newest {n} messages — narrow the filters to explore " +
    "deeper history",
  "feed.jumpLatest": "Jump to latest",
  "feed.loadFailed": "Load failed: {msg}",
};

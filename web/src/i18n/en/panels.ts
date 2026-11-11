/** UI strings: right-panel surfaces (Details, Ask AI, conversation). */
import type { Dict } from "../types";

export const dict: Dict = {
  // details panel
  "details.emptyHint": "Select a message in the feed to see its details here.",
  "details.group": "Group",
  "details.date": "Date",
  "details.sender": "Sender",
  "details.id": "ID",
  "details.edited": "Edited",
  "details.yes": "yes",
  "details.media": "Media",
  "details.mediaNote": "image (not stored locally)",
  "details.noText": "[no text / media only]",
  "details.noteTitle": "Private note",
  "details.bookmarked": "bookmarked",
  "details.bookmark": "bookmark",
  "details.notePlaceholder":
    "Your note (Arabic/English, stays on this machine, never sent to AI)…",
  "details.noteSave": "Save note",
  "details.noteSaved": "Note saved",
  "details.noteSaving": "Saving…",
  "details.noteInBookmarks": "Shows in Bookmarks",
  "details.noteStarsHint": "Saving stars the message",
  "details.copyFailed": "Copy failed",
  "details.linkCopied": "Message link copied",
  "details.copyLink": "Copy message link",
  "details.noLinkHint":
    "Public groups and supergroups have per-message links; basic groups " +
    "don't. We never fabricate URLs.",
  "details.noLink": "no Telegram link for this chat",
  "details.bySender": "Messages from this sender",
  "details.filterBySender": "Filtering by sender",

  // evidence explorer
  "ev.title": "Evidence",
  "ev.none": "nothing references this message",
  "ev.refs": "{n} reference(s)",
  "ev.deals": "Deals ({n})",
  "ev.decisions": "Decisions ({n})",
  "ev.briefs": "Research briefs ({n})",
  "ev.digests": "Digests ({n})",
  "ev.alerts": "Alerts ({n})",
  "ev.faqs": "FAQs ({n})",
  "ev.entities": "Entities ({n})",
  "ev.asDecision": "this message states the decision",
  "ev.asFollowup": "this message is a follow-up about the decision",
  "ev.replyTo": "Reply to",
  "ev.directReplies": "Direct replies ({n})",

  // conversation block
  "conv.title": "Conversation",
  "conv.openHint": "Reply chain (where captured) + the messages around this one",
  "conv.repliesTo": "replying to {ids}",
  "conv.directReply": "direct reply",
  "conv.mediaOnly": "[media only]",
  "conv.noNeighbors": "No neighboring messages archived around this one.",
  "conv.couldNotOpen": "Could not open the message",

  // ask AI panel
  "ai.notConfigured": "Ask AI is not configured",
  "ai.notConfiguredHint":
    "Add AI_API_KEY (and optionally AI_BASE_URL / AI_MODEL) in your .env " +
    "file to enable grounded answers over your archive. Works with any " +
    "OpenAI-compatible endpoint - OpenAI, Groq, OpenRouter, Ollama, vLLM " +
    "and more. Restart the app after editing .env.",
  "ai.emptyTitle": "Ask anything about your groups",
  "ai.emptyHint":
    "Answers are grounded in your {n} archived messages, with clickable " +
    "citations. Questions in Arabic get Arabic answers.",
  "ai.thinking": "searching {scope} and thinking…",
  "ai.scope": "Scope:",
  "ai.scopeHint": "The AI only retrieves messages inside this scope",
  "ai.scopeGroupsHint": "Remove the group filter - search all tracked groups",
  "ai.scopeAllHint": "Uses the group selection in the sidebar",
  "ai.scopeGroups": "{n} group(s)",
  "ai.placeholder": "Ask a question…  (Ctrl+Enter)",
  "ai.ask": "Ask",
  "ai.disclosure":
    "Answers send retrieved message excerpts to {host} ({model}) within: " +
    "{scope}. Nothing is sent unless you ask.",
  "ai.clearHistory": "clear history",
  "ai.fallbackRecent": "No keyword hits — answer based on the most recent messages.",
  "ai.basedOn": "Based on {n} retrieved message(s).",
  "ai.exporting": "exporting…",
  "ai.export": "export .md",
  "ai.exported": "Exported: {name}",
  "ai.sources": "Sources ({n})",
  "ai.badCitation": "Citation [{n}] has no matching retrieved message",
  "ai.couldNotOpen": "Could not open the original message",
};

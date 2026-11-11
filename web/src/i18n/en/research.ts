/** UI strings: research workspace (briefs). */
import type { Dict } from "../types";

export const dict: Dict = {
  "research.needsAi": "Research needs an AI provider",
  "research.needsAiHint":
    "Configure AI_API_KEY in Settings to generate evidence-linked research " +
    "briefs. Everything stays local - only the retrieved excerpts are sent " +
    "to your provider.",
  "research.placeholder":
    "Research question… e.g. Summarize everything about kubernetes migration · " +
    "ما كل النقاشات حول الترقية؟",
  "research.dateScope": "Date scope",
  "research.scope.all": "All time",
  "research.scope.30": "Last 30 days",
  "research.scope.90": "Last 90 days",
  "research.scope.custom": "Custom…",
  "research.submit": "Research it",
  "research.working": "Working…",
  "research.queued": "Research queued - watch Jobs for progress",
  "research.briefs": "Briefs",
  "research.noBriefs": "No briefs yet - ask your first question above.",
  "research.nNew": "{n} new",
  "research.groupsInScope": "Groups in scope",
  "research.toggleGroup": "Toggle group in scope",
  "research.desk": "Your research desk",
  "research.deskHint":
    "Ask a question about your groups. The answer becomes a saved, cited " +
    "brief you can re-run weekly - it will tell you when new relevant " +
    "messages appeared since.",
  "research.generating": "Generating…",
  "research.generatingHint":
    "Your brief is being researched. Watch the Jobs panel for live " +
    "progress; this page refreshes automatically.",
  "research.rerun": "Re-run",
  "research.rerunQueued": "Re-run queued - a new version is on the way",
  "research.alreadyRunning": "Already running",
  "research.exported": "Exported",
  "research.deleted": "Brief deleted",
  "research.exportMd": "Export .md",
  "research.exportJson": ".json",
  "research.delete": "Delete",
  "research.generated": "generated {date} · {model}",
  "research.staleBadge": "{n} new message(s) since",
  "research.staleBadgeHint": "New scope-matching messages appeared after this version",
  "research.citations": "Citations ({n}) - every claim traces here",
  "research.notes": "Your notes",
  "research.notesPlaceholder": "Personal notes for this brief (stays local)…",
  "research.saveNotes": "Save notes",
  "research.notesSaved": "Notes saved",
  "research.couldNotOpen": "Could not open the original message",
};

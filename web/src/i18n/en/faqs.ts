/** UI strings: view "faqs" — recurring questions + proposed answers. */
import type { Dict } from "../types";

export const dict: Dict = {
  // toolbar + status tabs
  "faqs.discover": "Discover FAQs",
  "faqs.discoverHint": "Scan the last 90 days for recurring questions",
  "faqs.aiRequired": "Configure an AI provider first",
  "faqs.tabAll": "All",
  "faqs.st.candidate": "candidate",
  "faqs.st.approved": "approved",
  "faqs.st.needs_review": "needs review",
  "faqs.st.rejected": "rejected",
  "faqs.st.outdated": "outdated",

  // discovery scope
  "faqs.scopeLabel": "Discovery scope (groups):",

  // empty states
  "faqs.emptyAll": "No FAQs yet",
  "faqs.emptyCandidate": "No candidate FAQs",
  "faqs.emptyApproved": "No approved FAQs",
  "faqs.emptyReview": "No FAQs needing review",
  "faqs.emptyRejected": "No rejected FAQs",
  "faqs.emptyHintAi":
    "Run “Discover FAQs” to cluster the questions your groups keep asking. " +
    "Proposed answers cite real messages; nothing becomes trusted " +
    "knowledge until you approve it.",
  "faqs.emptyHintAiOff":
    "Configure an AI provider (Settings) to draft answers. Question " +
    "clustering itself is deterministic.",

  // cards
  "faqs.freq": "×{n}",
  "faqs.lastSeen": "last {date}",
  "faqs.approve": "Approve",
  "faqs.approvedToast": "Approved",
  "faqs.stillCorrect": "Still correct",
  "faqs.stillCorrectHint": "Re-approve after checking the new evidence",
  "faqs.reapproved": "Re-approved",
  "faqs.noAnswerYet": "no drafted answer yet — run discovery again",

  // detail modal
  "faqs.noDraftedAnswer": "No drafted answer yet.",
  "faqs.askedSources": "Asked {n}× — question sources",
  "faqs.deleted": "[deleted]",
  "faqs.saveAnswer": "Save answer",
  "faqs.answerSaved": "Answer saved",
  "faqs.editAnswer": "Edit answer",
  "faqs.markOutdated": "Mark outdated",
  "faqs.markedOutdated": "Marked outdated",
  "faqs.deletedToast": "FAQ deleted",
  "faqs.queued": "FAQ discovery queued — watch Jobs",
  "faqs.discoveryRunning": "Discovery already running",
};

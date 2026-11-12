/** v1.0.2 regression tests: per-record state isolation and evidence
 *  focus consumption, found in the full frontend review.
 *
 *  1. ResearchView: switching briefs must reset the notes editor -
 *     without a key on BriefDetail, brief A's notes stayed in the
 *     textarea under brief B's question and saving wrote A's notes
 *     onto B (cross-record corruption).
 *  2. The Evidence Explorer's focus is consumed by every target view,
 *     not just Deals/Decisions. */
import { useEffect } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Brief } from "../src/api/types";

const briefs = vi.hoisted(() => {
  const mk = (id: number, question: string, notes: string): Brief => ({
    id, question, chat_ids: [], date_from: null, date_to: null, notes,
    created_at: "2026-11-10T10:00:00", updated_at: "2026-11-10T10:00:00",
    stale_count: 0,
    latest: {
      version: 1, created_at: "2026-11-10T10:00:00", model: "m",
      prompt_version: "v1", answer_md: `answer for ${id}`,
      citations: [],
    },
  });
  return [mk(1, "Question A", "notes for A"),
          mk(2, "Question B", "notes for B")];
});

const mocks = vi.hoisted(() => ({
  appState: vi.fn(async () => ({
    version: "1.0.2", telegram_configured: true, authenticated: true,
    auth_user: "u", tracked_groups: 2, messages: 50,
    pending_backfills: 0, last_message: null, ai_configured: true,
    ai_provider_host: "h", ai_model: "m",
  })),
  jobStatus: vi.fn(async () => ({
    running: false, name: "", log: "", queued: [], last_done: null,
  })),
  groups: vi.fn(async () => [
    { chat_id: -1, title: "Deals", kind: "group", username: "deals",
      last_synced: null, message_count: 40, last_message: null },
  ]),
  senders: vi.fn(async () => []),
  messages: vi.fn(async () => ({ messages: [], next_cursor: null, has_more: false })),
  search: vi.fn(async () => []),
  savedList: vi.fn(async () => []),
  savedRun: vi.fn(),
  briefs: vi.fn(async () => briefs),
  briefCreate: vi.fn(async () => ({ id: 3, queued: true })),
  briefGet: vi.fn(),
  briefPatch: vi.fn(async () => ({})),
  briefRegenerate: vi.fn(async () => ({ queued: true })),
  briefDelete: vi.fn(async () => ({ ok: true })),
  briefVersions: vi.fn(async () => []),
  exportBrief: vi.fn(),
  message: vi.fn(async () => ({})),
  digests: vi.fn(async () => []),
  digestGet: vi.fn(async (id: number) => ({
    id, schedule_id: null, period_start: "2026-11-10", period_end: "2026-11-11",
    content_md: "digest", prompt_version: "v", model: "m",
    fingerprint: "f", created_at: "2026-11-11",
  })),
  digestSchedules: vi.fn(async () => []),
  entitiesList: vi.fn(async () => []),
  entitiesSettings: vi.fn(async () => ({ auto: false, ai_configured: true })),
  entityGet: vi.fn(async (id: number) => ({
    id, name: "E", norm_name: "e", kind: "brand", aliases: [], source: "manual",
    ignored: 0, created_at: "2026-11-10", updated_at: "2026-11-10",
    recent: 0, last_seen: null, groups: [], daily: [], mentions: [],
    mentions_count: 0,
  })),
  faqs: vi.fn(async () => []),
  faqPatch: vi.fn(async () => ({})),
  alerts: vi.fn(async () => []),
}));

vi.mock("../src/api/client", () => ({
  api: {
    appState: mocks.appState, jobStatus: mocks.jobStatus,
    groups: mocks.groups, senders: mocks.senders,
    messages: mocks.messages, search: mocks.search,
    savedList: mocks.savedList, savedRun: mocks.savedRun,
    briefs: mocks.briefs, briefCreate: mocks.briefCreate,
    briefGet: mocks.briefGet, briefPatch: mocks.briefPatch,
    briefRegenerate: mocks.briefRegenerate, briefDelete: mocks.briefDelete,
    briefVersions: mocks.briefVersions, exportBrief: mocks.exportBrief,
    message: mocks.message, digests: mocks.digests,
    digestGet: mocks.digestGet, digestSchedules: mocks.digestSchedules,
    entitiesList: mocks.entitiesList, entitiesSettings: mocks.entitiesSettings,
    entityGet: mocks.entityGet, faqs: mocks.faqs, faqPatch: mocks.faqPatch,
    alerts: mocks.alerts,
  },
}));

import { StoreProvider, useStore } from "../src/state/store";
import { LangProvider } from "../src/i18n";
import { ResearchView } from "../src/components/ResearchView";
import { DigestsView } from "../src/components/DigestsView";

function ui() {
  return (
    <LangProvider>
      <StoreProvider>
        <ResearchView />
      </StoreProvider>
    </LangProvider>
  );
}

/** Test-only helper: fire an Evidence-Explorer jump into the store. */
function FocusSetter({ kind, id }: { kind: string; id: number }) {
  const { setEvidenceFocus } = useStore();
  useEffect(() => {
    setEvidenceFocus({ kind, id });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

describe("v1.0.2 regressions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("switching briefs resets the notes editor (no cross-record leaks)", async () => {
    render(ui());
    // brief A is auto-selected (first in the list); its question appears
    // both in the sidebar row and in the detail header
    await waitFor(() =>
      expect(screen.getAllByText("Question A").length).toBeGreaterThan(1));

    // type unsaved notes under brief A
    const ta = await screen.findByPlaceholderText(/notes/i);
    fireEvent.change(ta, { target: { value: "unsaved A notes" } });
    expect((ta as HTMLTextAreaElement).value).toBe("unsaved A notes");

    // switch to brief B in the sidebar list (the <button> wrapper, not
    // the detail header)
    const sidebarRow = screen
      .getAllByText("Question B")
      .find((el) => el.closest("button"))!;
    fireEvent.click(sidebarRow);

    // the notes textarea must now show B's persisted notes, NOT A's
    // unsaved draft - and saving must patch B, never A.
    const ta2 = await screen.findByPlaceholderText(/notes/i);
    expect((ta2 as HTMLTextAreaElement).value).toBe("notes for B");
  });

  it("digest evidence focus opens the referenced digest", async () => {
    mocks.digestGet.mockClear();
    render(
      <LangProvider>
        <StoreProvider>
          <DigestsView />
          <FocusSetter kind="digest" id={7} />
        </StoreProvider>
      </LangProvider>,
    );
    await waitFor(() => expect(mocks.digestGet).toHaveBeenCalledWith(7));
  });
});

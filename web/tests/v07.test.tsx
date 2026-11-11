/** v0.7 features: Discover is the landing view, trending topics run a
 *  feed search, question actions hit the API, entities render, and the
 *  conversation block fetches context. */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Entity } from "../src/api/types";

const mocks = vi.hoisted(() => ({
  appState: vi.fn(async () => ({
    version: "0.7.0", telegram_configured: true, authenticated: true,
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
  discoverTrending: vi.fn(async () => [
    { term: "solar inverter", recent: 6, baseline: 0, score: 6, chats: 2,
      sample: { chat_id: -1, msg_id: 7, date: "2026-11-08T10:00:00+00:00",
                chat_title: "Deals", text: "solar inverter deal" } },
  ]),
  discoverStories: vi.fn(async () => [{
    key: "k", n: 2, chats: 2, first_date: "2026-11-07", last_date: "2026-11-07",
    sample_text: "Community meetup Saturday at the pavilion",
    chat_titles: ["Deals", "Tech"],
    occurrences: [
      { chat_id: -1, msg_id: 1, date: "2026-11-07", text: "Community meetup",
        sender_name: "a", chat_title: "Deals", tg_link: null },
    ],
  }]),
  discoverQuestions: vi.fn(async () => [{
    chat_id: -1, msg_id: 9, text: "What shutter speed for birds?",
    asked_at: "2026-11-07", replies: 0, followers: 0, status: "open",
    answered_by: null, updated_at: "2026-11-07", chat_title: "Deals",
    tg_link: null, faq: null,
  }]),
  questionSetStatus: vi.fn(async () => ({ ok: true, status: "answered" })),
  questionScan: vi.fn(async () => ({ ok: true, new_open: 0, open: 1 })),
  discoverActivity: vi.fn(async () => ({
    days: 30,
    groups: [{ chat_id: -1, title: "Deals", kind: "group",
               daily: [{ day: "2026-11-07", n: 5 }], total: 5, media: 1,
               per_day: 0.2, media_share: 0.2 }],
    hours: [{ hour: 10, n: 5 }],
    totals: { messages: 5, active_groups: 1, messages_per_day: 0.2 },
  })),
  discoverRebuild: vi.fn(async () => ({ started: true })),
  topicTimeline: vi.fn(async () => ({
    term: "solar inverter",
    timeline_md: "## 2026-11-07 - launched [1]",
    sources: [{ chat_id: -1, msg_id: 7, date: "2026-11-07",
                sender_name: "a", text: "solar inverter deal",
                chat_title: "Deals", tg_link: null }],
  })),
  entitiesList: vi.fn(async () => [
    { id: 1, name: "GadgetHub", norm_name: "gadgethub", kind: "brand",
      aliases: [], source: "manual", ignored: 0,
      created_at: "2026-11-07", updated_at: "2026-11-07",
      mentions: 4, recent: 2, last_seen: "2026-11-07" } as Entity,
  ]),
  entitiesSettings: vi.fn(async () => ({ auto: false, ai_configured: true })),
  entitiesAuto: vi.fn(async () => ({ auto: true })),
  entityGet: vi.fn(async () => ({
    id: 1, name: "GadgetHub", norm_name: "gadgethub", kind: "brand",
    aliases: ["gadget hub"], source: "manual", ignored: 0,
    created_at: "2026-11-07", updated_at: "2026-11-07", recent: 2,
    last_seen: "2026-11-07",
    groups: [{ chat_id: -1, title: "Deals", n: 4 }],
    daily: [{ day: "2026-11-07", n: 4 }],
    mentions: [{ chat_id: -1, msg_id: 7, date: "2026-11-07",
                 text: "GadgetHub deal", sender_name: "a",
                 chat_title: "Deals", tg_link: null }],
    mentions_count: 4,
  })),
  entityCreate: vi.fn(),
  entityPatch: vi.fn(),
  entityMerge: vi.fn(),
  entityDelete: vi.fn(async () => ({ ok: true })),
  message: vi.fn(async () => ({
    chat_id: -1, msg_id: 9, date: "2026-11-07T10:00:00+00:00",
    sender_name: "a", text: "hello", has_media: 0, edited: 0,
    chat_title: "Deals", tg_link: null,
  })),
  messageContext: vi.fn(async () => ({
    target: { chat_id: -1, msg_id: 9, date: "2026-11-07T10:00:00+00:00",
              sender_name: "a", text: "q?", has_media: 0, edited: 0,
              chat_title: "Deals", tg_link: null },
    ancestors: [], replies: [],
    rows: [
      { chat_id: -1, msg_id: 8, date: "2026-11-07T09:00:00+00:00",
        sender_name: "b", text: "before", has_media: 0, edited: 0,
        chat_title: "Deals", tg_link: null, is_target: 0, is_reply: 0 },
      { chat_id: -1, msg_id: 9, date: "2026-11-07T10:00:00+00:00",
        sender_name: "a", text: "q?", has_media: 0, edited: 0,
        chat_title: "Deals", tg_link: null, is_target: 1, is_reply: 0 },
    ],
  })),
  bookmarkSet: vi.fn(), bookmarkDelete: vi.fn(), bookmarks: vi.fn(async () => []),
}));

vi.mock("../src/api/client", () => ({ api: mocks }));

import { StoreProvider, useStore } from "../src/state/store";
import { LangProvider } from "../src/i18n";
import { DiscoverView } from "../src/components/DiscoverView";
import { EntityView } from "../src/components/EntityView";
import { ConversationBlock } from "../src/components/ConversationBlock";
import { Toasts } from "../src/components/Toasts";

describe("v0.7 Discover landing view", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("discover is the default mode after a fresh load", async () => {
    let store: ReturnType<typeof useStore> | null = null;
    const Probe = () => { store = useStore(); return null; };
    render(
      <LangProvider>
        <StoreProvider>
        <Probe />
        </StoreProvider>
      </LangProvider>,
    );
    await waitFor(() => expect(store).toBeTruthy());
    expect(store!.mode).toBe("discover");
  });

  it("renders all discovery sections from the API", async () => {
    render(
      <LangProvider>
        <StoreProvider>
        <DiscoverView />
        <Toasts />
        </StoreProvider>
      </LangProvider>,
    );
    // trending term + its burst badge
    expect(await screen.findByText("solar inverter")).toBeTruthy();
    expect(screen.getByText(/6×/)).toBeTruthy();
    // story + question sections
    await waitFor(() => expect(mocks.discoverStories).toHaveBeenCalled());
    expect(await screen.findByText(/Unanswered questions \(1\)/)).toBeTruthy();
    expect(screen.getByText("What shutter speed for birds?")).toBeTruthy();
    // group activity row with its total
    expect(await screen.findByText(/5 msgs/)).toBeTruthy();
  });

  it("clicking a trending term runs a feed search for it", async () => {
    let store: ReturnType<typeof useStore> | null = null;
    const Probe = () => { store = useStore(); return null; };
    render(
      <LangProvider>
        <StoreProvider>
        <DiscoverView />
        <Toasts />
        <Probe />
        </StoreProvider>
      </LangProvider>,
    );
    const term = await screen.findByRole("button", { name: "solar inverter" });
    fireEvent.click(term);
    await waitFor(() => expect(store!.mode).toBe("search"));
    expect(store!.q).toBe("solar inverter");
  });

  it("loads the AI topic timeline with clickable citations", async () => {
    render(
      <LangProvider>
        <StoreProvider>
        <DiscoverView />
        <Toasts />
        </StoreProvider>
      </LangProvider>,
    );
    fireEvent.click(await screen.findByRole("button", { name: /Timeline/ }));
    await waitFor(() => expect(mocks.topicTimeline).toHaveBeenCalled());
    expect(await screen.findByText("topic timeline")).toBeTruthy();
    expect(await screen.findByText(/launched/)).toBeTruthy();
  });

  it("marking a question answered calls the API and updates the list", async () => {
    render(
      <LangProvider>
        <StoreProvider>
        <DiscoverView />
        <Toasts />
        </StoreProvider>
      </LangProvider>,
    );
    await screen.findByText("What shutter speed for birds?");
    fireEvent.click(screen.getByRole("button", { name: "answered" }));
    await waitFor(() => expect(mocks.questionSetStatus).toHaveBeenCalledWith(-1, 9, "answered"));
    await waitFor(() => expect(mocks.discoverQuestions).toHaveBeenCalledTimes(2));
  });
});

describe("v0.7 Entities view", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("lists entities and opens a detail with mentions", async () => {
    render(
      <LangProvider>
        <StoreProvider>
        <EntityView />
        <Toasts />
        </StoreProvider>
      </LangProvider>,
    );
    fireEvent.click(await screen.findByText("GadgetHub"));
    await waitFor(() => expect(mocks.entityGet).toHaveBeenCalledWith(1, 30, 0));
    expect(await screen.findByText(/4 mentions/)).toBeTruthy();
    expect(screen.getByText("GadgetHub deal")).toBeTruthy();
  });
});

describe("v0.7 conversation block", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("fetches the conversation on demand and flags the target row", async () => {
    render(
      <LangProvider>
        <StoreProvider>
        <ConversationBlock m={{
          chat_id: -1, msg_id: 9, date: "2026-11-07T10:00:00+00:00",
          sender_name: "a", text: "q?", has_media: 0, edited: 0,
          chat_title: "Deals", tg_link: null,
        }} />
        <Toasts />
        </StoreProvider>
      </LangProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /View in conversation/ }));
    await waitFor(() => expect(mocks.messageContext).toHaveBeenCalledWith(-1, 9));
    expect(await screen.findByText("Conversation")).toBeTruthy();
    expect(screen.getByText("q?")).toBeTruthy();
    expect(screen.getByText("before")).toBeTruthy();
    expect(document.querySelector(".conv-row.target")).toBeTruthy();
  });
});

/** Full-app integration test: the real <App/> with the API layer mocked,
 *  driven through every workspace the way a user navigates. */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  appState: vi.fn(async () => ({
    version: "0.6.0", telegram_configured: true, authenticated: true,
    auth_user: "e2e", tracked_groups: 10, messages: 400,
    pending_backfills: 0, last_message: null, ai_configured: true,
    ai_provider_host: "127.0.0.1", ai_model: "e2e-mock",
  })),
  jobStatus: vi.fn(async () => ({
    running: false, name: "", log: "", queued: [], last_done: null,
  })),
  groups: vi.fn(async () => [
    { chat_id: -10012340002, title: "Weekend Hikers", kind: "group",
      username: "weekendhikers", last_synced: null, message_count: 40,
      last_message: null },
  ]),
  senders: vi.fn(async () => []),
  messages: vi.fn(async () => ({
    messages: [{
      chat_id: -10012340002, msg_id: 1000, date: "2026-11-07T10:00:00+00:00",
      sender_id: 1, sender_name: "Sara", text: "the new hiking trail is muddy",
      has_media: 0, edited: 0, chat_title: "Weekend Hikers",
      bookmarked: 0, bookmark_note: null,
      tg_link: "https://t.me/weekendhikers/1000",
    }],
    next_cursor: null, has_more: false,
  })),
  search: vi.fn(async () => []),
  message: vi.fn(async () => ({})),
  ask: vi.fn(async () => ({
    answer: "a [1]", sources: [], attempts: 1, keywords_tried: [],
    fallback: null, provider_host: "h", provider_model: "m",
    scope: { chat_ids: [], date_from: null, date_to: null },
  })),
  schedulerState: vi.fn(async () => ({
    enabled: true, interval_min: 360, next_due: "2099-01-01T00:00:00",
    last_success: null,
  })),
  alertsUnread: vi.fn(async () => ({ unread: 2 })),
  savedList: vi.fn(async () => []),
  bookmarks: vi.fn(async () => [{
    chat_id: -10012340002, msg_id: 1000, date: "2026-11-07T10:00:00+00:00",
    sender_id: 1, sender_name: "Sara", text: "the new hiking trail is muddy",
    has_media: 0, edited: 0, chat_title: "Weekend Hikers",
    note: "great trail", bookmarked_at: "t", note_updated_at: "t",
    tg_link: "https://t.me/weekendhikers/1000",
  }]),
  deals: vi.fn(async () => [{
    id: 1, title: "Trail shoes 20% off", description: "", category: "other",
    vendor: "Runner's Corner", discount_pct: 20, price: null,
    currency: "USD", promo_code: "TRAIL20", eligibility: null, geo: null,
    valid_from: null, expires: "2030-01-01", status: "active",
    user_status: null, confidence: 0.9, derived_status: "active",
    confidence_label: "high", human_added: false, last_seen: "t",
    sources: [{ chat_id: -10012340002, msg_id: 1000, text: "20% discount",
                date: "t", sender_name: "S", chat_title: "Weekend Hikers",
                tg_link: "https://t.me/weekendhikers/1000", missing: false }],
  }]),
  dealsSettings: vi.fn(async () => ({
    auto: false, categories: ["other"], vendors: [], watermark: {},
  })),
  briefs: vi.fn(async () => [{
    id: 1, question: "Summarize the hiking trail discussions",
    chat_ids: [-10012340002], date_from: null, date_to: null,
    notes: "", created_at: "t", updated_at: "t",
    latest: {
      version: 1, created_at: "t", model: "e2e-mock", prompt_version: "x",
      answer_md: "## Executive summary\nTrails are muddy [1].",
      citations: [{ idx: 1, chat_id: -10012340002, msg_id: 1000,
                    excerpt: "x", text: "trail text", date: "t",
                    sender_name: "S", chat_title: "Weekend Hikers",
                    tg_link: "https://t.me/weekendhikers/1000" }],
    },
    stale_count: 0,
  }]),
  watchlists: vi.fn(async () => [{
    id: 1, name: "e2e trails", terms: ["trail"], exclude_terms: [],
    chat_ids: [], enabled: true, created_at: "t", last_match_at: null,
    unread: 2,
  }]),
  alerts: vi.fn(async () => [{
    id: 1, watchlist_id: 1, watchlist_name: "e2e trails",
    chat_id: -10012340002, msg_id: 1000, matched_term: "trail",
    created_at: "t", read: 0, archived: 0,
    text: "trail conditions report", date: "2026-11-07T10:00:00+00:00",
    sender_name: "Sara", chat_title: "Weekend Hikers",
    tg_link: "https://t.me/weekendhikers/1000",
  }]),
  digestSchedules: vi.fn(async () => []),
  digests: vi.fn(async () => [{
    id: 1, schedule_id: null, period_start: "2026-11-06T00:00:00",
    period_end: "2026-11-07T00:00:00", content_md: "## Top discussions\nTrails [1]",
    prompt_version: "x", model: "e2e-mock", created_at: "t",
  }]),
  digestGet: vi.fn(async () => null),
  faqs: vi.fn(async () => [{
    id: 3, question: "Any recommended budget lenses for landscape shots?",
    answer_md: "Members suggest the 35mm prime [3].",
    status: "candidate", frequency: 3, first_seen: "t", last_seen: "t",
    updated_at: "t",
    source_questions: [{ chat_id: -10012340002, msg_id: 1000, date: "t",
                        text: "q", chat_title: "Weekend Hikers",
                        tg_link: "https://t.me/weekendhikers/1000" }],
  }]),
  aiUsage: vi.fn(async () => ({
    by_task: { ask: { requests: 3, tokens_in: 10, tokens_out: 5 } },
    total: { requests: 3, tokens_in: 10, tokens_out: 5 },
  })),
}));

vi.mock("../src/api/client", () => ({ api: mocks }));

import App from "../src/App";
import { StoreProvider } from "../src/state/store";

function renderApp() {
  return render(
    <StoreProvider>
      <App />
    </StoreProvider>,
  );
}

async function open(name: string | RegExp) {
  const btn = await screen.findByRole("button", { name });
  fireEvent.click(btn);
}

describe("full app: every workspace", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    // jsdom lacks matchMedia, which the app shell uses for layout checks
    Object.defineProperty(window, "matchMedia", {
      value: (query: string) => ({
        matches: false, media: query, onchange: null,
        addListener: () => {}, removeListener: () => {},
        addEventListener: () => {}, removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
      writable: true,
    });
    Element.prototype.scrollIntoView = () => {};
  });

  it("renders the feed on first load", async () => {
    renderApp();
    await waitFor(() =>
      expect(screen.getByText(/the new hiking trail is muddy/)).toBeTruthy());
    expect(screen.getByText("Browse & search")).toBeTruthy();
  });

  it("navigates to Bookmarks with content and export actions", async () => {
    renderApp();
    await open(/Bookmarks/);
    expect(await screen.findByText("Bookmarks", { selector: "h2" })).toBeTruthy();
    expect(await screen.findByText(/great trail/)).toBeTruthy();
    expect(screen.getByText("Export .md")).toBeTruthy();
    expect(screen.getByText("Export .json")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Telegram ↗/ })).toBeTruthy();
  });

  it("navigates to Deals and shows extracted rows with status", async () => {
    renderApp();
    await open(/Deals/);
    expect(await screen.findByText("Trail shoes 20% off")).toBeTruthy();
    expect(screen.getByText("TRAIL20")).toBeTruthy();
    expect(screen.getAllByText("active").length).toBeGreaterThan(0);
    // expand the card: sources + human actions appear
    fireEvent.click(screen.getByText("Trail shoes 20% off"));
    expect(await screen.findByText(/Sources \(1\)/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /✓ Confirm/ })).toBeTruthy();
    expect(mocks.deals).toHaveBeenCalled();
  });

  it("navigates to Research and renders the brief with citations", async () => {
    renderApp();
    await open(/Research/);
    expect((await screen.findAllByText(/Summarize the hiking trail/))
            .length).toBeGreaterThan(0);
    expect(await screen.findByText(/Trails are muddy/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Re-run" })).toBeTruthy();
    expect(screen.getByText(/Citations \(1\)/)).toBeTruthy();
    expect(screen.getByPlaceholderText(/Research question/)).toBeTruthy();
  });

  it("navigates to Watchlists and Alerts with the unread badge", async () => {
    renderApp();
    // sidebar badge shows the unread count
    expect(await screen.findByText("2")).toBeTruthy();
    await open(/Watchlists/);
    expect(await screen.findByText("e2e trails")).toBeTruthy();
    expect(screen.getByRole("button", { name: "+ New watchlist" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Check now" })).toBeTruthy();

    await open(/Alerts/);
    expect(await screen.findByText(/trail conditions report/)).toBeTruthy();
    expect(screen.getByText("e2e trails")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Mark read" })).toBeTruthy();
  });

  it("navigates to Digests with history and on-demand buttons", async () => {
    renderApp();
    await open(/Digests/);
    expect(await screen.findByText("Digest last day")).toBeTruthy();
    expect(await screen.findByText(/2026-11-06/)).toBeTruthy();
    fireEvent.click(screen.getByText(/2026-11-06/));
    await waitFor(() => expect(mocks.digestGet).toHaveBeenCalled());
  });

  it("navigates to FAQs and shows the human-review gate", async () => {
    renderApp();
    await open(/FAQs/);
    expect(await screen.findByText(/budget lenses/)).toBeTruthy();
    expect(screen.getAllByText(/candidate/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Approve" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Discover FAQs" })).toBeTruthy();
  });

  it("opens Settings with auto-sync and AI usage", async () => {
    renderApp();
    await open(/Browse & search/);
    fireEvent.click(await screen.findByRole("button", { name: "Settings" }));
    expect(await screen.findByText("Auto-sync (v0.4)")).toBeTruthy();
    expect(screen.getByText(/Automatic sync/)).toBeTruthy();
    expect(await screen.findByText(/AI usage \(this machine\)/)).toBeTruthy();
    expect(await screen.findByText(/3 request/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Rebuild search index/ })).toBeTruthy();
  });
});

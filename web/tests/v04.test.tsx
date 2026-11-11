/** v0.4 features: scope chips reach the API, star toggles bookmark,
 *  saved searches apply their filters to the store. */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SavedSearch } from "../src/api/types";

const mocks = vi.hoisted(() => ({
  appState: vi.fn(async () => ({
    version: "0.4.0", telegram_configured: true, authenticated: true,
    auth_user: "u", tracked_groups: 2, messages: 10,
    pending_backfills: 0, last_message: null, ai_configured: true,
    ai_provider_host: "h", ai_model: "m",
  })),
  jobStatus: vi.fn(async () => ({
    running: false, name: "", log: "", queued: [], last_done: null,
  })),
  groups: vi.fn(async () => [
    { chat_id: -1, title: "Deals", kind: "group", username: "deals",
      last_synced: null, message_count: 5, last_message: null },
    { chat_id: -2, title: "Cars", kind: "group", username: null,
      last_synced: null, message_count: 5, last_message: null },
  ]),
  senders: vi.fn(async () => []),
  messages: vi.fn(async () => ({ messages: [], next_cursor: null, has_more: false })),
  search: vi.fn(async () => []),
  savedList: vi.fn(async () => [] as SavedSearch[]),
  savedRun: vi.fn(async (id: number) => ({ id })),
  savedCreate: vi.fn(async (_s: unknown) => ({ id: 1 })),
  bookmarkSet: vi.fn(async () => ({ ok: true })),
  bookmarkDelete: vi.fn(async () => ({ ok: true })),
  bookmarks: vi.fn(async () => []),
  ask: vi.fn(async (_question: string, _scope?: unknown) => ({
    answer: "a", sources: [], attempts: 1, keywords_tried: [],
    fallback: null, provider_host: "h", provider_model: "m",
    scope: { chat_ids: [], date_from: null, date_to: null },
  })),
  schedulerState: vi.fn(async () => ({
    enabled: true, interval_min: 360, next_due: null, last_success: null,
  })),
  schedulerConfig: vi.fn(),
  exportBookmarks: vi.fn(),
  exportSaved: vi.fn(),
  exportAiAnswer: vi.fn(),
  message: vi.fn(),
}));

vi.mock("../src/api/client", () => ({ api: mocks }));

import { StoreProvider, useStore } from "../src/state/store";
import { LangProvider } from "../src/i18n";
import { AiPanel } from "../src/components/AiPanel";
import { FilterBar } from "../src/components/FilterBar";
import { Toasts } from "../src/components/Toasts";

type ScopeArg = { chat_ids: number[]; date_from: string | null; date_to: string | null };

function askScope(i = 0): ScopeArg {
  const call = mocks.ask.mock.calls[i]!;
  return call[1] as ScopeArg;
}

describe("v0.4 AI scope chips", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = () => {};
  });

  it("sends the selected group + date scope with the question", async () => {
    render(
      <LangProvider>
        <StoreProvider>
        <AiPanel />
        <Toasts />
        </StoreProvider>
      </LangProvider>,
    );

    // default: all groups, all time
    const ta = screen.getByPlaceholderText(/Ask a question/);
    fireEvent.change(ta, { target: { value: "pizza?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(mocks.ask).toHaveBeenCalled());
    expect(mocks.ask).toHaveBeenCalledWith("pizza?", {
      chat_ids: [], date_from: null, date_to: null,
    });
    mocks.ask.mockClear();

    // pick "30 days" scope
    fireEvent.click(screen.getByRole("button", { name: "30 days" }));
    fireEvent.change(ta, { target: { value: "pizza?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(mocks.ask).toHaveBeenCalledTimes(1));
    const scope = askScope();
    expect(scope.date_from).toBeTruthy();
    expect(scope.date_to).toBeTruthy();
    expect(scope.date_from! < scope.date_to!).toBe(true);
  });

  it("scope date preset persists across reloads", async () => {
    localStorage.setItem("tgq-ai-scope-days", "7d");
    render(
      <LangProvider>
        <StoreProvider>
        <AiPanel />
        </StoreProvider>
      </LangProvider>,
    );
    const ta = screen.getByPlaceholderText(/Ask a question/);
    fireEvent.change(ta, { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(mocks.ask).toHaveBeenCalled());
    expect(askScope().date_from).toBeTruthy();
  });
});

describe("v0.4 save search", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("saves the current query + filters under a name", async () => {
    render(
      <LangProvider>
        <StoreProvider>
        <FilterBar />
        <Toasts />
        </StoreProvider>
      </LangProvider>,
    );

    const save = await screen.findByRole("button", { name: /Save search/i });
    expect((save as HTMLButtonElement).disabled).toBe(true);  // nothing to save yet

    // "Today" date preset sets filters.from -> now there is something to save
    fireEvent.click(screen.getByRole("button", { name: "Today" }));
    expect((save as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(save);

    const input = screen.getByPlaceholderText(/Name, e.g\./);
    fireEvent.change(input, { target: { value: "أروع العروض" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(mocks.savedCreate).toHaveBeenCalled());
    const body = mocks.savedCreate.mock.calls[0]![0] as Record<string, unknown>;
    expect(body.name).toBe("أروع العروض");
    expect(body.date_from).toBeTruthy();   // the Today preset was captured
    // the saved definition captures groups + dates + sender + media + sort
    // (the starred feed filter is a view state, not part of a saved search)
    expect(body).toHaveProperty("chat_ids");
    expect(body).toHaveProperty("sort");
  });
});

describe("v0.4 store: applySaved", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("applies a saved search to the live store state and marks it used", async () => {
    let store: ReturnType<typeof useStore> | null = null;
    const Probe = () => {
      store = useStore();
      return null;
    };
    render(
      <LangProvider>
        <StoreProvider>
        <Probe />
        </StoreProvider>
      </LangProvider>,
    );
    await waitFor(() => expect(store).toBeTruthy());

    const saved: SavedSearch = {
      id: 7, name: "pizza", q: "pizza offer", chat_ids: [-1], sender: "sami",
      media: "1", date_from: "2026-01-01", date_to: "2026-02-01",
      sort: "asc", created_at: "2026-01-01", last_used_at: null,
    };
    store!.applySaved(saved);

    await waitFor(() => {
      expect(store!.q).toBe("pizza offer");
      expect(store!.mode).toBe("search");
      expect(store!.selection.has(-1)).toBe(true);
      expect(store!.filters.sender).toBe("sami");
      expect(store!.filters.media).toBe("1");
      expect(store!.filters.sort).toBe("asc");
      expect(store!.filters.from).toBe("2026-01-01");
    });
    expect(mocks.savedRun).toHaveBeenCalledWith(7);
  });
});

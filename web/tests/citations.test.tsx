/** Citation behavior: valid [n] opens the right message, invalid warns. */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatTurn } from "../src/utils/history";

const mocks = vi.hoisted(() => ({
  // everything StoreProvider/AiPanel touch at mount:
  appState: vi.fn(async () => ({
    version: "t", telegram_configured: true, authenticated: true,
    auth_user: "u", tracked_groups: 1, messages: 1,
    pending_backfills: 0, last_message: null, ai_configured: true,
    ai_provider_host: "h", ai_model: "m",
  })),
  jobStatus: vi.fn(async () => ({
    running: false, name: "", log: "", queued: [], last_done: null,
  })),
  groups: vi.fn(async () => []),
  senders: vi.fn(async () => []),
  messages: vi.fn(async () => ({ messages: [], next_cursor: null, has_more: false })),
  message: vi.fn(async () => ({
    chat_id: -7, msg_id: 3, date: "2026-01-03T10:00:00",
    sender_name: "s", text: "third source", has_media: 0, edited: 0,
    chat_title: "G",
  })),
  // AiPanel itself:
  ask: vi.fn(),
}));

vi.mock("../src/api/client", () => ({ api: mocks }));

import { AiPanel } from "../src/components/AiPanel";
import { Toasts } from "../src/components/Toasts";
import { StoreProvider } from "../src/state/store";
import { LangProvider } from "../src/i18n";

const TURN: ChatTurn = {
  question: "q",
  answer: "First claim [1] and a bogus one [9].",
  sources: [
    { chat_id: -7, msg_id: 3, title: "G", date: "2026-01-03",
      sender: "s", text: "third source" },
  ],
  keywords: [],
  at: 1,
};

function renderPanel(turn: ChatTurn) {
  localStorage.setItem("tgq-ai-chat", JSON.stringify([turn]));
  return render(
    <LangProvider>
      <StoreProvider>
      <AiPanel />
      <Toasts />
      </StoreProvider>
    </LangProvider>,
  );
}

describe("AiPanel citations", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    // jsdom does not implement scrolling
    Element.prototype.scrollIntoView = () => {};
  });

  it("valid citation fetches the exact source message", async () => {
    renderPanel(TURN);
    // [1] appears in both the answer and the sources list - click the answer's
    const cite = screen.getAllByText("[1]")[0];
    fireEvent.click(cite);
    await waitFor(() => expect(mocks.message).toHaveBeenCalledWith(-7, 3));
  });

  it("out-of-range citation warns instead of silently failing", async () => {
    renderPanel(TURN);
    fireEvent.click(screen.getByText("[9]"));
    await waitFor(() =>
      expect(screen.getByText(/Citation \[9\] has no matching/)).toBeTruthy());
    expect(mocks.message).not.toHaveBeenCalled();
  });
});

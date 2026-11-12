/** v1.0.3 regression: the login-success toast must show the account
 *  label from the login RESPONSE. Reading it from the render-time
 *  appState snapshot rendered the pre-login value - "Logged in as "
 *  with no name - because refreshAppState() cannot update a closure
 *  captured before the request. */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  appState: vi.fn(async () => ({
    version: "1.0.3", telegram_configured: true, authenticated: false,
    auth_user: null, tracked_groups: 0, messages: 0,
    pending_backfills: 0, last_message: null, ai_configured: false,
    ai_provider_host: "api.openai.com", ai_model: "gpt-4o-mini",
  })),
  // a successful login: the RESPONSE carries the account label
  authStart: vi.fn(async () => ({
    stage: "done", authenticated: true, user: "@tester (Test User)",
  })),
  authStatus: vi.fn(async () => ({ authenticated: false, user: null })),
  jobStatus: vi.fn(async () => ({
    running: false, name: "", log: "", queued: [], last_done: null,
  })),
  groups: vi.fn(async () => []),
  senders: vi.fn(async () => []),
  messages: vi.fn(async () => (
    { messages: [], next_cursor: null, has_more: false })),
  savedList: vi.fn(async () => []),
}));

vi.mock("../src/api/client", () => ({ api: mocks }));

import { StoreProvider, useStore } from "../src/state/store";
import { LangProvider } from "../src/i18n";
import { Onboarding } from "../src/components/Onboarding";
import { Toasts } from "../src/components/Toasts";

/** Mount the wizard only once appState has loaded - exactly how App
 * opens it (the wizard's initial step is derived from appState). */
function Harness() {
  const { appState } = useStore();
  return appState ? <Onboarding onClose={() => {}} /> : null;
}

describe("Onboarding login step", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the account name from the login response, not a stale snapshot", async () => {
    render(
      <LangProvider>
        <StoreProvider>
          <Harness />
          <Toasts />
        </StoreProvider>
      </LangProvider>,
    );

    // appState arrived with authenticated=false -> the wizard opens on
    // the login step (credentials are configured)
    const phone = await screen.findByPlaceholderText("+966501234567");
    fireEvent.change(phone, { target: { value: "+966501234567" } });
    fireEvent.click(screen.getByText("Send login code"));

    // the toast must name the account that just logged in
    await waitFor(() => {
      expect(
        screen.getByText("Logged in as @tester (Test User)"),
      ).toBeTruthy();
    });
  });
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AiProviderForm, CredsForm } from "../src/components/SetupForms";

const mocks = vi.hoisted(() => ({
  setupTelegram: vi.fn(async () => ({ telegram_configured: true })),
  setupAi: vi.fn(async () => ({ ai_configured: true })),
  testAi: vi.fn(async () => ({ ok: true, model: "m-test", reply: "OK" })),
}));

vi.mock("../src/api/client", () => ({ api: mocks }));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CredsForm", () => {
  it("saves entered credentials and calls onSaved", async () => {
    const onSaved = vi.fn();
    render(<CredsForm onSaved={onSaved} />);

    fireEvent.change(screen.getByLabelText("API ID"), { target: { value: "123456" } });
    fireEvent.change(screen.getByLabelText("API hash"), { target: { value: "h".repeat(32) } });

    const btn = screen.getByText("Save & continue");
    expect((btn as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(btn);

    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(mocks.setupTelegram).toHaveBeenCalledWith("123456", "h".repeat(32));
  });

  it("stays disabled with short values and never fires", async () => {
    const onSaved = vi.fn();
    render(<CredsForm onSaved={onSaved} />);
    const btn = screen.getByText("Save & continue") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    fireEvent.click(btn);
    expect(mocks.setupTelegram).not.toHaveBeenCalled();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("has a show/hide toggle for the secret field", () => {
    render(<CredsForm onSaved={() => {}} />);
    const hashInput = screen.getByLabelText("API hash") as HTMLInputElement;
    expect(hashInput.type).toBe("password");
    fireEvent.click(screen.getAllByText("show")[1]); // second field = api hash
    expect(hashInput.type).toBe("text");
  });
});

describe("AiProviderForm", () => {
  it("prefills the OpenAI preset", () => {
    render(<AiProviderForm onSaved={() => {}} />);
    expect(
      (screen.getByDisplayValue("https://api.openai.com/v1") as HTMLInputElement),
    ).toBeTruthy();
    expect(screen.getByDisplayValue("gpt-4o-mini")).toBeTruthy();
  });

  it("tests the connection and shows the result", async () => {
    render(<AiProviderForm onSaved={() => {}} />);
    const keyInput = screen.getByPlaceholderText("sk-…") as HTMLInputElement;
    fireEvent.change(keyInput, { target: { value: "sk-test" } });

    fireEvent.click(screen.getByText("Test connection"));
    await waitFor(() =>
      expect(screen.getByText(/connection works/)).toBeTruthy());
    expect(mocks.testAi).toHaveBeenCalledWith(
      expect.objectContaining({ api_key: "sk-test" }),
    );
  });

  it("switches presets and saves with the new values", async () => {
    const onSaved = vi.fn();
    render(<AiProviderForm onSaved={onSaved} />);

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "Ollama (local)" },
    });
    expect(
      (screen.getByDisplayValue("http://localhost:11434/v1") as HTMLInputElement),
    ).toBeTruthy();

    const keyInput = screen.getByPlaceholderText(/any non-empty value/) as HTMLInputElement;
    fireEvent.change(keyInput, { target: { value: "ollama" } });
    fireEvent.click(screen.getByText("Save & continue"));

    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(mocks.setupAi).toHaveBeenCalledWith(
      expect.objectContaining({
        base_url: "http://localhost:11434/v1",
        api_key: "ollama",
        model: "llama3",
      }),
    );
  });
});

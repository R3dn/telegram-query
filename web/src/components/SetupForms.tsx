/** Shared setup forms used by the onboarding wizard and the settings modal.
 *  Store-free by design: everything comes in via props, so tests stay easy
 *  and secrets never wander into global state. */
import { useState } from "react";
import { api } from "../api/client";

function SecretInput(props: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  numeric?: boolean;
}) {
  const [show, setShow] = useState(false);
  return (
    <label className="field" htmlFor={props.id}>
      <span>{props.label}</span>
      <span style={{ position: "relative", display: "block" }}>
        <input
          id={props.id}
          className="input"
          style={{ paddingInlineEnd: 64 }}
          type={show ? "text" : "password"}
          inputMode={props.numeric ? "numeric" : undefined}
          placeholder={props.placeholder}
          value={props.value}
          dir="ltr"
          autoComplete="off"
          onChange={(e) => props.onChange(e.target.value)}
        />
        <button
          type="button"
          className="link"
          style={{ position: "absolute", insetInlineEnd: 8, top: 7 }}
          onClick={() => setShow((s) => !s)}
          tabIndex={-1}
        >
          {show ? "hide" : "show"}
        </button>
      </span>
    </label>
  );
}

/** Telegram API credentials (my.telegram.org). */
export function CredsForm(props: {
  onSaved: () => void | Promise<void>;
  submitLabel?: string;
}) {
  const [apiId, setApiId] = useState("");
  const [apiHash, setApiHash] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.setupTelegram(apiId, apiHash);
      setApiId("");
      setApiHash("");
      await props.onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <SecretInput id="tg-api-id" label="API ID"
        placeholder="123456" value={apiId} onChange={setApiId} numeric />
      <SecretInput id="tg-api-hash" label="API hash"
        placeholder="0123456789abcdef0123456789abcdef" value={apiHash}
        onChange={setApiHash} />
      {error && <p className="ai-error">{error}</p>}
      <div className="wizard-actions">
        <button className="btn primary" disabled={busy || !apiId.trim() || apiHash.trim().length < 8}
          onClick={() => void save()}>
          {busy ? "Saving…" : props.submitLabel ?? "Save & continue"}
        </button>
      </div>
    </div>
  );
}

const PRESETS: { name: string; base?: string; model?: string }[] = [
  { name: "OpenAI", base: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  { name: "Groq", base: "https://api.groq.com/openai/v1", model: "llama-3.1-8b-instant" },
  { name: "OpenRouter", base: "https://openrouter.ai/api/v1" },
  { name: "Ollama (local)", base: "http://localhost:11434/v1", model: "llama3" },
  { name: "Custom…" },
];

/** AI provider: preset dropdown + endpoint + key + model + live test. */
export function AiProviderForm(props: {
  onSaved: () => void | Promise<void>;
  submitLabel?: string;
}) {
  const [preset, setPreset] = useState("OpenAI");
  const [baseUrl, setBaseUrl] = useState(PRESETS[0].base);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(PRESETS[0].model ?? "");
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pickPreset = (name: string) => {
    setPreset(name);
    setTestResult(null);
    const p = PRESETS.find((x) => x.name === name);
    if (p?.base) setBaseUrl(p.base);
    if (p?.model) setModel(p.model);
  };

  const test = async () => {
    if (testing || !apiKey.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const r = await api.testAi({ base_url: baseUrl, api_key: apiKey, model });
      setTestResult(r.ok ? `✓ ${r.model} replied — connection works` : `✗ ${r.error}`);
    } catch (e) {
      setTestResult(`✗ ${(e as Error).message}`);
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.setupAi({ base_url: baseUrl, api_key: apiKey, model });
      setApiKey("");
      setTestResult(null);
      await props.onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <label className="field">
        <span>Provider preset</span>
        <select className="input" value={preset} onChange={(e) => pickPreset(e.target.value)}>
          {PRESETS.map((p) => <option key={p.name}>{p.name}</option>)}
        </select>
      </label>
      <label className="field">
        <span>Endpoint (base URL)</span>
        <input className="input" dir="ltr" value={baseUrl} placeholder="https://api.openai.com/v1"
          onChange={(e) => { setBaseUrl(e.target.value); setTestResult(null); }} />
      </label>
      <SecretInput id="ai-api-key" label="API key"
        placeholder={preset === "Ollama (local)" ? "any non-empty value (e.g. ollama)" : "sk-…"}
        value={apiKey} onChange={(v) => { setApiKey(v); setTestResult(null); }} />
      <label className="field">
        <span>Model</span>
        <input className="input" dir="ltr" value={model} placeholder="gpt-4o-mini"
          onChange={(e) => { setModel(e.target.value); setTestResult(null); }} />
      </label>

      {testResult && (
        <p className="mm-note" style={{ color: testResult.startsWith("✓") ? "var(--good)" : "var(--err)" }}>
          {testResult}
        </p>
      )}
      {error && <p className="ai-error">{error}</p>}

      <div className="wizard-actions">
        <button className="btn ghost" disabled={testing || !apiKey.trim()} onClick={() => void test()}>
          {testing ? "Testing…" : "Test connection"}
        </button>
        <span style={{ flex: 1 }} />
        <button className="btn primary" disabled={busy || !apiKey.trim()}
          onClick={() => void save()}>
          {busy ? "Saving…" : props.submitLabel ?? "Save & continue"}
        </button>
      </div>
      <p className="mm-note dim">
        The key is stored in your local <code className="kbd">.env</code> file and
        is never shown again or sent back to the browser.
      </p>
    </div>
  );
}

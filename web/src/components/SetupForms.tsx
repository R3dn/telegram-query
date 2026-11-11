/** Shared setup forms used by the onboarding wizard and the settings modal.
 *  Store-free by design: everything comes in via props, so tests stay easy
 *  and secrets never wander into global state.
 *  `t` is optional: without it the English table is used directly, so the
 *  forms also render standalone (tests, zero-provider usage). */
import { useState } from "react";
import { api } from "../api/client";
import { Ic } from "../design/icons";
import { dict as EN } from "../i18n/en/onboarding";

type TFn = (key: string, vars?: Record<string, string | number>) => string;

/** English-only fallback resolver for when no `t` is passed in. */
const tEn: TFn = (key, vars) => {
  let s = EN[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replaceAll(`{${k}}`, String(v));
    }
  }
  return s;
};

function SecretInput(props: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  numeric?: boolean;
  t: TFn;
}) {
  const [show, setShow] = useState(false);
  const t = props.t;
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
          {show ? t("onboarding.form.hide") : t("onboarding.form.show")}
        </button>
      </span>
    </label>
  );
}

/** Telegram API credentials (my.telegram.org). */
export function CredsForm(props: {
  onSaved: () => void | Promise<void>;
  submitLabel?: string;
  t?: TFn;
}) {
  const t = props.t ?? tEn;
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
      <SecretInput id="tg-api-id" t={t} label={t("onboarding.form.apiId")}
        placeholder="123456" value={apiId} onChange={setApiId} numeric />
      <SecretInput id="tg-api-hash" t={t} label={t("onboarding.form.apiHash")}
        placeholder="0123456789abcdef0123456789abcdef" value={apiHash}
        onChange={setApiHash} />
      {error && <p className="ai-error">{error}</p>}
      <div className="wizard-actions">
        <button className="btn primary" disabled={busy || !apiId.trim() || apiHash.trim().length < 8}
          onClick={() => void save()}>
          {busy
            ? <><Ic.Spin size={13} className="spin" /> {t("onboarding.form.saving")}</>
            : props.submitLabel ?? t("onboarding.form.saveContinue")}
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

/** Display label for a preset (the value stays the canonical English name
 *  so preset matching and tests keep working). */
function presetLabel(t: TFn, name: string): string {
  if (name === "Ollama (local)") return t("onboarding.form.presetOllama");
  if (name === "Custom…") return t("onboarding.form.presetCustom");
  return name;
}

/** AI provider: preset dropdown + endpoint + key + model + live test. */
export function AiProviderForm(props: {
  onSaved: () => void | Promise<void>;
  submitLabel?: string;
  t?: TFn;
}) {
  const t = props.t ?? tEn;
  const [preset, setPreset] = useState("OpenAI");
  const [baseUrl, setBaseUrl] = useState(PRESETS[0].base);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(PRESETS[0].model ?? "");
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null);
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
      setTestResult(
        r.ok
          ? { ok: true, text: t("onboarding.form.testOk", { model: r.model ?? "" }) }
          : { ok: false, text: r.error ?? "" },
      );
    } catch (e) {
      setTestResult({ ok: false, text: (e as Error).message });
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
        <span>{t("onboarding.form.preset")}</span>
        <select className="input" value={preset} onChange={(e) => pickPreset(e.target.value)}>
          {PRESETS.map((p) => (
            <option key={p.name} value={p.name}>{presetLabel(t, p.name)}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>{t("onboarding.form.endpoint")}</span>
        <input className="input" dir="ltr" value={baseUrl} placeholder="https://api.openai.com/v1"
          onChange={(e) => { setBaseUrl(e.target.value); setTestResult(null); }} />
      </label>
      <SecretInput id="ai-api-key" t={t} label={t("onboarding.form.apiKey")}
        placeholder={preset === "Ollama (local)" ? t("onboarding.form.keyAny") : "sk-…"}
        value={apiKey} onChange={(v) => { setApiKey(v); setTestResult(null); }} />
      <label className="field">
        <span>{t("onboarding.form.model")}</span>
        <input className="input" dir="ltr" value={model} placeholder="gpt-4o-mini"
          onChange={(e) => { setModel(e.target.value); setTestResult(null); }} />
      </label>

      {testResult && (
        <p className={`test-result ${testResult.ok ? "ok" : "bad"}`}>
          {testResult.ok ? <Ic.CircleCheck size={14} /> : <Ic.CircleX size={14} />}
          {" "}{testResult.text}
        </p>
      )}
      {error && <p className="ai-error">{error}</p>}

      <div className="wizard-actions">
        <button className="btn ghost" disabled={testing || !apiKey.trim()} onClick={() => void test()}>
          {testing
            ? <><Ic.Spin size={13} className="spin" /> {t("onboarding.form.testing")}</>
            : t("onboarding.form.test")}
        </button>
        <span style={{ flex: 1 }} />
        <button className="btn primary" disabled={busy || !apiKey.trim()}
          onClick={() => void save()}>
          {busy
            ? <><Ic.Spin size={13} className="spin" /> {t("onboarding.form.saving")}</>
            : props.submitLabel ?? t("onboarding.form.saveContinue")}
        </button>
      </div>
      <p className="mm-note dim">
        {t("onboarding.form.keyNote.a")} <code className="kbd">.env</code>{" "}
        {t("onboarding.form.keyNote.b")}
      </p>
    </div>
  );
}

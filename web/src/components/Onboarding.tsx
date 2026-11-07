/** First-run setup wizard: credentials -> Telegram login (phone/code/2FA)
 *  -> pick groups -> optional AI -> first sync. Can be re-run from Settings.
 *  Telegram and AI credentials are entered directly here and written to .env. */
import { useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { Dialog } from "../api/types";
import { AiProviderForm, CredsForm } from "./SetupForms";

type Step = "credentials" | "login" | "groups" | "ai" | "sync" | "done";

const STEPS: { key: Step; title: string }[] = [
  { key: "credentials", title: "Telegram API credentials" },
  { key: "login", title: "Log in to Telegram" },
  { key: "groups", title: "Choose groups to track" },
  { key: "ai", title: "AI provider (optional)" },
  { key: "sync", title: "First sync" },
];

export function Onboarding({ onClose }: { onClose: () => void }) {
  const { appState, refreshAppState, refreshGroups, toast, loadFeed } = useStore();
  const [step, setStep] = useState<Step>(
    !appState?.telegram_configured ? "credentials"
      : appState?.authenticated === false ? "login"
      : appState?.tracked_groups === 0 ? "groups"
      : "done",
  );
  const [busy, setBusy] = useState(false);

  const next = async () => {
    await refreshAppState();
    setStep((s) => {
      const idx = STEPS.findIndex((x) => x.key === s);
      return STEPS[Math.min(idx + 1, STEPS.length - 1)].key;
    });
  };

  const idx = STEPS.findIndex((s) => s.key === step);

  return (
    <div className="wizard-overlay">
      <div className="wizard">
        <div className="wizard-head">
          <div className="logo">
            <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden>
              <rect width="24" height="24" rx="6" fill="var(--accent)" />
              <path d="M6 11.5 18 6l-4.5 12-2.6-4.1L6 11.5z" fill="#fff" />
            </svg>
            <span>Welcome to Telegram Query</span>
          </div>
          <button className="btn ghost sm" onClick={onClose} title="Close - you can reopen from the sidebar">✕</button>
        </div>

        <div className="wizard-steps">
          {STEPS.map((s, i) => (
            <span key={s.key} className={`wstep ${i === idx ? "on" : i < idx ? "done" : ""}`}>
              <b>{i + 1}</b> {s.title}
            </span>
          ))}
        </div>

        <div className="wizard-body">
          {step === "credentials" && (
            <CredentialsStep busy={busy} setBusy={setBusy} onDone={next} />
          )}
          {step === "login" && (
            <LoginStep busy={busy} setBusy={setBusy} onDone={next} />
          )}
          {step === "groups" && <GroupsStep onDone={next} />}
          {step === "ai" && <AiStep onDone={next} />}
          {step === "sync" && (
            <SyncStep onDone={async () => {
              await refreshGroups();
              await refreshAppState();
              void loadFeed(true);
              toast("Setup complete — your archive is building", "good");
              onClose();
            }} />
          )}
          {step === "done" && (
            <div className="wizard-done">
              <p>Everything is set up. You can close this wizard.</p>
              <button className="btn primary" onClick={onClose}>Start using Telegram Query</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------------- steps ---------------- */

function CredentialsStep({ busy, setBusy, onDone }: {
  busy: boolean; setBusy: (b: boolean) => void; onDone: () => void;
}) {
  const { refreshAppState, appState } = useStore();
  const [editing, setEditing] = useState(false);
  const configured = appState?.telegram_configured === true;

  return (
    <div>
      <h3>Connect your Telegram account</h3>
      <p className="dim">
        Telegram requires every third-party app to use its own API credentials —
        creating them takes about a minute:
      </p>
      <ol className="wizard-list">
        <li>Open <a href="https://my.telegram.org" target="_blank" rel="noreferrer">my.telegram.org</a> → <b>API development tools</b></li>
        <li>Create an app (any title; the rest can stay default)</li>
        <li>Copy <b>api_id</b> and <b>api_hash</b> and paste them below</li>
      </ol>

      {configured && !editing && (
        <div className="settings-row">
          <span>API credentials</span>
          <span>
            <span className="badge good">configured ✓</span>{" "}
            <button className="link" onClick={() => setEditing(true)}>change</button>
          </span>
        </div>
      )}
      {(!configured || editing) && (
        <CredsForm onSaved={() => void onDone()} />
      )}
      {configured && !editing && (
        <div className="wizard-actions" style={{ justifyContent: "flex-end" }}>
          <button className="btn primary" onClick={() => void onDone()}>Continue →</button>
        </div>
      )}
      {configured && !editing && (
        <p className="mm-note dim">
          Values are stored in your local <code className="kbd">.env</code> file.
          Prefer editing files? Everything is documented in
          <code className="kbd" style={{ marginInline: 4 }}>.env.example</code>.
        </p>
      )}
      {busy && <p className="mm-note dim">Checking…</p>}
      <button
        className="link" style={{ marginTop: 6, display: "block" }}
        onClick={async () => { setBusy(true); await refreshAppState(); setBusy(false); }}
      >
        I edited .env manually — check again
      </button>
    </div>
  );
}

function LoginStep({ busy, setBusy, onDone }: {
  busy: boolean; setBusy: (b: boolean) => void; onDone: () => void;
}) {
  const { appState, refreshAppState, toast } = useStore();
  const [stage, setStage] = useState<"phone" | "code" | "password">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const run = async (fn: () => Promise<{ stage: string; error?: string }>) => {
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      if (r.error) setError(r.error);
      else if (r.stage === "code") setStage("code");
      else if (r.stage === "password") setStage("password");
      else {
        await refreshAppState();
        toast(`Logged in as ${appState?.auth_user ?? ""}`, "good");
        onDone();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h3>Log in to Telegram</h3>
      {stage === "phone" && (
        <>
          <label className="field"><span>Phone number (international)</span>
            <input className="input" placeholder="+966501234567" value={phone}
              onChange={(e) => setPhone(e.target.value)} />
          </label>
          <div className="wizard-actions">
            <button className="btn primary" disabled={busy || !phone.trim()}
              onClick={() => void run(() => api.authStart(phone))}>
              {busy ? "Sending code…" : "Send login code"}
            </button>
          </div>
        </>
      )}
      {stage === "code" && (
        <>
          <p className="dim">Telegram sent a login code to your app/SMS. Enter it below.</p>
          <label className="field"><span>Login code</span>
            <input className="input" placeholder="12345" value={code} inputMode="numeric"
              onChange={(e) => setCode(e.target.value)} />
          </label>
          <div className="wizard-actions">
            <button className="btn primary" disabled={busy || !code.trim()}
              onClick={() => void run(() => api.authCode(code))}>
              {busy ? "Verifying…" : "Verify"}
            </button>
            <button className="btn ghost" disabled={busy} onClick={() => void run(() => api.authStart(phone))}>Resend</button>
          </div>
        </>
      )}
      {stage === "password" && (
        <>
          <p className="dim">Your account has two-step verification enabled. Enter your cloud password.</p>
          <label className="field"><span>Two-step verification password</span>
            <input className="input" type="password" value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </label>
          <div className="wizard-actions">
            <button className="btn primary" disabled={busy || !password}
              onClick={() => void run(() => api.authPassword(password))}>
              {busy ? "Verifying…" : "Verify"}
            </button>
          </div>
        </>
      )}
      {error && <p className="ai-error">{error}</p>}
    </div>
  );
}

function GroupsStep({ onDone }: { onDone: () => void }) {
  const { toast, refreshGroups, refreshAppState, refreshJobs } = useStore();
  const [dialogs, setDialogs] = useState<Dialog[] | null>(null);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);

  const load = async (force: boolean) => {
    setBusy(true);
    try {
      if (!force) {
        const r = await api.dialogsGet();
        if (r.ready && r.dialogs) { setDialogs(r.dialogs); setBusy(false); return; }
      }
      await api.dialogsStart();
      void refreshJobs();
      for (let i = 0; i < 45; i++) {
        await new Promise((r) => setTimeout(r, 1300));
        const r = await api.dialogsGet();
        if (r.ready && r.dialogs) { setDialogs(r.dialogs); setBusy(false); return; }
      }
      throw new Error("Timed out loading the group list");
    } catch (e) {
      toast((e as Error).message, "err");
      setBusy(false);
    }
  };

  const track = async () => {
    const ids = [...checked];
    if (!ids.length) { toast("Tick at least one group", "info"); return; }
    setBusy(true);
    try {
      const r = await api.track(ids);
      if (r.started) {
        toast(`Tracking ${ids.length} group${ids.length > 1 ? "s" : ""} — backfill starting`, "good");
        await Promise.all([refreshGroups(), refreshAppState(), refreshJobs()]);
        onDone();
      } else {
        toast(r.reason === "already_tracked" ? "Already tracking those groups" : "Could not start tracking", "info");
      }
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h3>Choose groups to track</h3>
      <p className="dim">
        Tracked groups are copied into your local archive — their full history
        is downloaded so you can search and browse them. You can change this
        anytime in “Manage groups”.
      </p>
      {dialogs === null && (
        <div className="wizard-actions" style={{ justifyContent: "center", padding: 24 }}>
          {busy
            ? <><span className="spinner" /> listing your groups…</>
            : <button className="btn primary" onClick={() => void load(false)}>Load my groups</button>}
        </div>
      )}
      {dialogs && (
        <>
          <div className="wizard-dialogs">
            {dialogs.slice(0, 200).map((d) => (
              <label key={d.chat_id} className="mm-row clickable">
                <input type="checkbox" checked={checked.has(d.chat_id)}
                  onChange={() => setChecked((s) => {
                    const n = new Set(s);
                    if (n.has(d.chat_id)) n.delete(d.chat_id); else n.add(d.chat_id);
                    return n;
                  })} />
                <span className="g-ic">{d.kind === "channel" ? "📣" : "👥"}</span>
                <span className="g-main">
                  <span className="g-title" dir="auto">{d.title}</span>
                  <span className="g-meta">{d.username ? `@${d.username}` : d.chat_id}</span>
                </span>
              </label>
            ))}
          </div>
          <div className="wizard-actions">
            <button className="btn ghost sm" onClick={() => void load(true)} disabled={busy}>↻ reload list</button>
            <span style={{ flex: 1 }} />
            <button className="btn primary" disabled={busy || checked.size === 0} onClick={() => void track()}>
              Track {checked.size > 0 ? `${checked.size} group${checked.size > 1 ? "s" : ""}` : ""}
            </button>
            <button className="btn ghost" onClick={onDone}>Skip for now</button>
          </div>
        </>
      )}
    </div>
  );
}

function AiStep({ onDone }: { onDone: () => void }) {
  const { appState, refreshAppState } = useStore();
  const [editing, setEditing] = useState(false);
  const configured = appState?.ai_configured === true;

  return (
    <div>
      <h3>AI provider <span className="badge">optional</span></h3>
      <p className="dim">
        Ask-AI answers questions about your archive using any
        OpenAI-compatible endpoint (OpenAI, Groq, OpenRouter, Ollama, LM
        Studio, vLLM…). You can verify the connection before saving.
      </p>

      {configured && !editing ? (
        <>
          <div className="settings-row">
            <span>Provider</span>
            <span>
              <span className="badge good">{appState?.ai_provider_host} · {appState?.ai_model}</span>{" "}
              <button className="link" onClick={() => setEditing(true)}>change</button>
            </span>
          </div>
          <div className="wizard-actions" style={{ justifyContent: "flex-end" }}>
            <button className="btn primary" onClick={() => void onDone()}>Continue →</button>
          </div>
        </>
      ) : (
        <AiProviderForm onSaved={() => void onDone()} />
      )}

      <div className="wizard-actions" style={{ justifyContent: "space-between" }}>
        <button className="btn ghost" onClick={() => void onDone()}>Skip for now</button>
        {configured && !editing && (
          <button className="link" onClick={() => void refreshAppState()}>re-check</button>
        )}
      </div>
      <p className="mm-note dim">
        Only retrieved message excerpts are sent to the endpoint when you ask
        a question — the rest of your archive never leaves this machine.
      </p>
    </div>
  );
}

function SyncStep({ onDone }: { onDone: () => void }) {
  const { jobs, refreshJobs } = useStore();
  const [started, setStarted] = useState(false);
  const tail = jobs?.log?.trim().split("\n").slice(-3).join("\n");

  return (
    <div>
      <h3>First sync</h3>
      <p className="dim">
        Downloading the history of your tracked groups now. Large groups can
        take a while — you can keep using the app, stop the sync, and resume
        anytime without losing progress.
      </p>
      <div className="wizard-actions" style={{ justifyContent: "center", padding: 16 }}>
        {!started ? (
          <button
            className="btn primary"
            onClick={async () => { await api.sync(); await refreshJobs(); setStarted(true); }}
          >
            Start first sync
          </button>
        ) : (
          <div className="mm-progress" style={{ width: "100%" }}>
            <span className="spinner" />
            <div style={{ flex: 1 }}>
              <div>
                {jobs?.running
                  ? `${jobs.name === "track" ? "Backfilling your group" : "Syncing"}…`
                  : jobs?.queued?.length
                    ? `Queued behind ${jobs.queued.join(", ")}…`
                    : "Sync queued — starting…"}
              </div>
              <pre className="mm-log">{tail || "(starting…)"}</pre>
              {(jobs?.running || (jobs?.queued?.length ?? 0) > 0) && (
                <button className="btn danger sm" style={{ marginTop: 8 }}
                  onClick={async () => { await api.jobStop(false); await refreshJobs(); }}>
                  ■ stop (progress is saved)
                </button>
              )}
            </div>
          </div>
        )}
      </div>
      <div className="wizard-actions" style={{ justifyContent: "flex-end" }}>
        <button className="btn primary" onClick={() => void onDone()}>Finish setup →</button>
      </div>
    </div>
  );
}

/** Settings modal: theme, account, credentials editing, AI provider,
 *  auto-sync scheduler, and search normalization (v0.4). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { SchedulerState } from "../api/types";
import { fmtLocal } from "../utils/format";
import { Modal } from "./Modal";
import { AiProviderForm, CredsForm } from "./SetupForms";

const INTERVALS = [
  { label: "Every 15 min", min: 15 },
  { label: "Every 30 min", min: 30 },
  { label: "Every hour", min: 60 },
  { label: "Every 3 hours", min: 180 },
  { label: "Every 6 hours", min: 360 },
  { label: "Every 12 hours", min: 720 },
  { label: "Every day", min: 1440 },
];

export function SettingsModal({ onClose }: { onClose: () => void }) {
  const { theme, toggleTheme, appState, setWizardOpen, toast, refreshAppState, refreshJobs } = useStore();
  const [editing, setEditing] = useState<null | "telegram" | "ai">(null);
  const [sched, setSched] = useState<SchedulerState | null>(null);
  const [schedBusy, setSchedBusy] = useState(false);

  useEffect(() => {
    api.schedulerState().then(setSched).catch(() => { /* ignore */ });
  }, []);

  const applySched = async (p: { enabled?: boolean; interval_min?: number }) => {
    setSchedBusy(true);
    try {
      setSched(await api.schedulerConfig(p));
      toast("Auto-sync settings saved", "good");
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setSchedBusy(false);
    }
  };

  const reindex = async () => {
    try {
      const r = await api.reindex();
      toast(r.started ? "Reindex job queued - see Jobs" : "Reindex already queued", "info");
      onClose();
      await refreshJobs();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const logout = async () => {
    try {
      await api.authLogout();
      toast("Logged out of Telegram", "good");
      await refreshAppState();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const credsSaved = async () => {
    toast("Credentials saved", "good");
    await refreshAppState();
    setEditing(null);
  };

  return (
    <Modal title="Settings" onClose={onClose}>
      <div className="label" style={{ marginTop: 6 }}>Appearance</div>
      <div className="settings-row">
        <span>Theme</span>
        <div className="seg">
          <button className={theme === "dark" ? "on" : ""} onClick={() => theme !== "dark" && toggleTheme()}>Dark</button>
          <button className={theme === "light" ? "on" : ""} onClick={() => theme !== "light" && toggleTheme()}>Light</button>
        </div>
      </div>

      <div className="label" style={{ marginTop: 18 }}>Telegram</div>
      <div className="settings-row">
        <span>Account</span>
        <span>
          {appState?.authenticated === true
            ? <span className="badge good">logged in{appState.auth_user ? ` as ${appState.auth_user}` : ""}</span>
            : appState?.authenticated === false
              ? <span className="badge err">not logged in</span>
              : <span className="badge">checking…</span>}
        </span>
      </div>
      <div className="settings-row">
        <span>API credentials</span>
        <span>
          {appState?.telegram_configured
            ? <span className="badge good">configured ✓</span>
            : <span className="badge warn">missing</span>}{" "}
          <button className="link" onClick={() => setEditing(editing === "telegram" ? null : "telegram")}>
            {editing === "telegram" ? "cancel" : "change"}
          </button>
        </span>
      </div>
      {editing === "telegram" && (
        <div className="settings-edit">
          <CredsForm onSaved={credsSaved} submitLabel="Save credentials" />
        </div>
      )}
      <div className="settings-actions">
        <button className="btn ghost sm" onClick={() => { onClose(); setWizardOpen(true); }}>Run setup wizard</button>
        {appState?.authenticated && <button className="btn danger sm" onClick={() => void logout()}>Log out of Telegram</button>}
      </div>

      <div className="label" style={{ marginTop: 18 }}>Auto-sync (v0.4)</div>
      <div className="settings-row">
        <span>Automatic sync</span>
        <span>
          <button
            className={`btn sm ${sched?.enabled ? "primary" : "ghost"}`}
            disabled={schedBusy || !sched}
            onClick={() => void applySched({ enabled: !sched?.enabled })}
          >
            {sched?.enabled ? "On" : "Off"}
          </button>
        </span>
      </div>
      <div className="settings-row">
        <span>Interval</span>
        <select
          className="input"
          style={{ maxWidth: 160 }}
          disabled={schedBusy || !sched}
          value={sched?.interval_min ?? 360}
          onChange={(e) => void applySched({ interval_min: Number(e.target.value) })}
        >
          {INTERVALS.map((i) => (
            <option key={i.min} value={i.min}>{i.label}</option>
          ))}
        </select>
      </div>
      {sched && (
        <p className="mm-note dim">
          The schedule is stored in your local database and survives restarts;
          if the app was closed past a due time, one catch-up sync runs on the
          next start. Never overlaps a running sync.
          {sched.next_due && <> Next: <b>{fmtLocal(sched.next_due)}</b>.</>}
          {sched.last_success && <> Last successful sync: <b>{fmtLocal(sched.last_success)}</b>.</>}
        </p>
      )}

      <div className="label" style={{ marginTop: 18 }}>Search normalization</div>
      <div className="settings-row">
        <span>Normalization level</span>
        <span className="badge good">extended (Arabizi · Gulf dialect · elongation)</span>
      </div>
      <div className="settings-actions">
        <button className="btn ghost sm" onClick={() => void reindex()}
                title="Rewrite the search index with the current normalization rules. Runs as a background job.">
          Rebuild search index
        </button>
      </div>
      <p className="mm-note dim">
        Extended normalization folds Arabic-Indic digits (٢٥ → 25), collapses
        chat elongation (هااااي → هاي), folds Arabizi digits inside Latin
        words, and maps common Gulf dialect words to standard forms - at index
        and query time, so both sides always match. Original message text is
        never modified. Set <code className="kbd" style={{ marginInline: 4 }}>NORMALIZATION=standard</code>
        in .env for the v0.3 behavior, then use “Rebuild search index”.
      </p>

      <div className="label" style={{ marginTop: 18 }}>AI provider</div>
      <div className="settings-row">
        <span>Provider</span>
        <span>
          {appState?.ai_configured
            ? <span className="badge good">{appState.ai_provider_host} · {appState.ai_model}</span>
            : <span className="badge warn">not configured</span>}{" "}
          <button className="link" onClick={() => setEditing(editing === "ai" ? null : "ai")}>
            {editing === "ai" ? "cancel" : "change"}
          </button>
        </span>
      </div>
      {editing === "ai" && (
        <div className="settings-edit">
          <AiProviderForm onSaved={credsSaved} submitLabel="Save provider" />
        </div>
      )}
      <p className="mm-note dim">
        AI answers send retrieved message excerpts to the configured provider
        endpoint. Keys stay server-side, are written to your local
        <code className="kbd" style={{ marginInline: 4 }}>.env</code>, and are
        never sent back to the browser. Everything else never leaves this machine.
      </p>
    </Modal>
  );
}

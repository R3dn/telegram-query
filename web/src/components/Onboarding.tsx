/** First-run setup wizard: credentials -> Telegram login (phone/code/2FA)
 *  -> pick groups -> optional AI -> first sync. Can be re-run from Settings.
 *  Telegram and AI credentials are entered directly here and written to .env. */
import { useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { Dialog } from "../api/types";
import { jobKey } from "../utils/format";
import { Ic } from "../design/icons";
import { AiProviderForm, CredsForm } from "./SetupForms";

type Step = "credentials" | "login" | "groups" | "ai" | "sync" | "done";

const STEPS: { key: Step; label: string }[] = [
  { key: "credentials", label: "onboarding.step.credentials" },
  { key: "login", label: "onboarding.step.login" },
  { key: "groups", label: "onboarding.step.groups" },
  { key: "ai", label: "onboarding.step.ai" },
  { key: "sync", label: "onboarding.step.sync" },
];

type TFn = (key: string, vars?: Record<string, string | number>) => string;

/** Localized count noun: Arabic picks .one/.two/.few/.many plural classes,
 *  English .one/.many. `base` is a "system.pl.*" key prefix. */
function nounT(t: TFn, lang: string, base: string, n: number): string {
  const sfx = lang === "ar"
    ? n === 1 ? "one" : n === 2 ? "two" : n <= 10 ? "few" : "many"
    : n === 1 ? "one" : "many";
  return t(`${base}.${sfx}`, { n });
}

export function Onboarding({ onClose }: { onClose: () => void }) {
  const { appState, refreshAppState, refreshGroups, toast, loadFeed } = useStore();
  const { t, lang } = useLang();
  const [step, setStep] = useState<Step>(
    !appState?.telegram_configured ? "credentials"
      : appState?.authenticated === false ? "login"
      : appState?.tracked_groups === 0 ? "groups"
      : "done",
  );
  const [busy, setBusy] = useState(false);
  const [forceCredsEdit, setForceCredsEdit] = useState(false);

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
            <span>{t("onboarding.welcome", { app: t("app.name") })}</span>
          </div>
          <button className="btn ghost sm" onClick={onClose} title={t("onboarding.closeHint")}>
            <Ic.Close size={14} />
          </button>
        </div>

        <div className="wizard-steps">
          {STEPS.map((s, i) => {
            const cls = `wstep ${i === idx ? "on" : i < idx ? "done" : ""}`;
            const canClick = i <= idx; // completed or current step
            const Tag = canClick ? "button" : "span";
            return (
              <Tag key={s.key} className={cls}
                   disabled={!canClick}
                   onClick={canClick ? () => setStep(s.key) : undefined}>
                <b>{i < idx ? <Ic.Check size={11} /> : i + 1}</b> {t(s.label)}
              </Tag>
            );
          })}
        </div>

        <div className="wizard-body">
          {step === "credentials" && (
            <CredentialsStep busy={busy} setBusy={setBusy} onDone={next} t={t}
                             startEditing={forceCredsEdit} />
          )}
          {step === "login" && (
            <LoginStep busy={busy} setBusy={setBusy} onDone={next} t={t} />
          )}
          {step === "groups" && <GroupsStep onDone={next} t={t} lang={lang} />}
          {step === "ai" && <AiStep onDone={next} t={t} />}
          {step === "sync" && (
            <SyncStep onDone={async () => {
              await refreshGroups();
              await refreshAppState();
              void loadFeed(true);
              toast(t("onboarding.setupComplete"), "good");
              onClose();
            }} t={t} />
          )}
          {step === "done" && (
            <div className="wizard-done">
              <Ic.CircleCheck size={30} />
              <p>{t("onboarding.allSet")}</p>
              <button className="btn primary" onClick={onClose}>
                {t("onboarding.startUsing", { app: t("app.name") })}
              </button>
              <button
                className="link"
                onClick={() => { setForceCredsEdit(true); setStep("credentials"); }}
              >
                {t("onboarding.editCreds")}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------------- steps ---------------- */

function CredentialsStep({ busy, setBusy, onDone, t, startEditing }: {
  busy: boolean; setBusy: (b: boolean) => void; onDone: () => void; t: TFn;
  startEditing?: boolean;
}) {
  const { refreshAppState, appState } = useStore();
  const [editing, setEditing] = useState(startEditing === true);
  const configured = appState?.telegram_configured === true;

  return (
    <div>
      <h3>{t("onboarding.creds.title")}</h3>
      <p className="dim">{t("onboarding.creds.intro")}</p>
      <ol className="wizard-list">
        <li>
          {t("onboarding.creds.step1.open")}{" "}
          <a href="https://my.telegram.org" target="_blank" rel="noreferrer">my.telegram.org</a>{" "}
          <Ic.ArrowRight size={11} className="li-arrow" />{" "}
          <b>{t("onboarding.creds.step1.tools")}</b>
        </li>
        <li>{t("onboarding.creds.step2")}</li>
        <li>
          {t("onboarding.creds.step3.copy")} <code className="kbd">api_id</code>{" "}
          {t("onboarding.creds.step3.and")} <code className="kbd">api_hash</code>{" "}
          {t("onboarding.creds.step3.paste")}
        </li>
      </ol>

      {configured && !editing && (
        <div className="settings-row">
          <span>{t("system.apiCredentials")}</span>
          <span>
            <span className="badge good"><Ic.Check size={11} /> {t("system.configured")}</span>{" "}
            <button className="link" onClick={() => setEditing(true)}>{t("system.change")}</button>
          </span>
        </div>
      )}
      {(!configured || editing) && (
        <CredsForm t={t} onSaved={() => void onDone()} />
      )}
      {configured && !editing && (
        <div className="wizard-actions" style={{ justifyContent: "flex-end" }}>
          <button className="btn primary" onClick={() => void onDone()}>
            {t("onboarding.continue")} <Ic.ArrowRight size={13} />
          </button>
        </div>
      )}
      {configured && !editing && (
        <p className="mm-note dim">
          {t("onboarding.creds.envNote.a")} <code className="kbd">.env</code>{" "}
          {t("onboarding.creds.envNote.b")}{" "}
          <code className="kbd" style={{ marginInline: 4 }}>.env.example</code>.
        </p>
      )}
      {busy && <p className="mm-note dim">{t("onboarding.checking")}</p>}
      <button
        className="link" style={{ marginTop: 6, display: "block" }}
        onClick={async () => { setBusy(true); await refreshAppState(); setBusy(false); }}
      >
        {t("onboarding.recheckEnv")}
      </button>
    </div>
  );
}

function LoginStep({ busy, setBusy, onDone, t }: {
  busy: boolean; setBusy: (b: boolean) => void; onDone: () => void; t: TFn;
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
        toast(t("onboarding.login.loggedInAs", { user: appState?.auth_user ?? "" }), "good");
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
      <h3>{t("onboarding.step.login")}</h3>
      {stage === "phone" && (
        <>
          <label className="field"><span>{t("onboarding.login.phone")}</span>
            <input className="input" placeholder="+966501234567" value={phone} dir="ltr"
              onChange={(e) => setPhone(e.target.value)} />
          </label>
          <div className="wizard-actions">
            <button className="btn primary" disabled={busy || !phone.trim()}
              onClick={() => void run(() => api.authStart(phone))}>
              {busy
                ? <><Ic.Spin size={13} className="spin" /> {t("onboarding.login.sending")}</>
                : t("onboarding.login.send")}
            </button>
          </div>
        </>
      )}
      {stage === "code" && (
        <>
          <p className="dim">{t("onboarding.login.codeSent")}</p>
          <label className="field"><span>{t("onboarding.login.code")}</span>
            <input className="input" placeholder="12345" value={code} inputMode="numeric" dir="ltr"
              onChange={(e) => setCode(e.target.value)} />
          </label>
          <div className="wizard-actions">
            <button className="btn primary" disabled={busy || !code.trim()}
              onClick={() => void run(() => api.authCode(code))}>
              {busy
                ? <><Ic.Spin size={13} className="spin" /> {t("onboarding.login.verifying")}</>
                : t("onboarding.login.verify")}
            </button>
            <button className="btn ghost" disabled={busy} onClick={() => void run(() => api.authStart(phone))}>
              {t("onboarding.login.resend")}
            </button>
          </div>
        </>
      )}
      {stage === "password" && (
        <>
          <p className="dim">{t("onboarding.login.2faIntro")}</p>
          <label className="field"><span>{t("onboarding.login.2faPassword")}</span>
            <input className="input" type="password" value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </label>
          <div className="wizard-actions">
            <button className="btn primary" disabled={busy || !password}
              onClick={() => void run(() => api.authPassword(password))}>
              {busy
                ? <><Ic.Spin size={13} className="spin" /> {t("onboarding.login.verifying")}</>
                : t("onboarding.login.verify")}
            </button>
          </div>
        </>
      )}
      {error && <p className="ai-error">{error}</p>}
    </div>
  );
}

function GroupsStep({ onDone, t, lang }: {
  onDone: () => void; t: TFn; lang: string;
}) {
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
      throw new Error(t("onboarding.groups.loadTimeout"));
    } catch (e) {
      toast((e as Error).message, "err");
      setBusy(false);
    }
  };

  const track = async () => {
    const ids = [...checked];
    if (!ids.length) { toast(t("onboarding.groups.pickAtLeastOne"), "info"); return; }
    setBusy(true);
    try {
      const r = await api.track(ids);
      if (r.started) {
        toast(t("system.mm.trackedBackfill", {
          groups: nounT(t, lang, "system.pl.group", ids.length),
        }), "good");
        await Promise.all([refreshGroups(), refreshAppState(), refreshJobs()]);
        onDone();
      } else {
        toast(r.reason === "already_tracked" ? t("system.alreadyTracking") : t("system.trackFailed"), "info");
      }
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h3>{t("onboarding.step.groups")}</h3>
      <p className="dim">
        {t("onboarding.groups.intro", { manage: t("groups.manage") })}
      </p>
      {dialogs === null && (
        <div className="wizard-actions" style={{ justifyContent: "center", padding: 24 }}>
          {busy
            ? <><Ic.Spin size={13} className="spin" /> {t("onboarding.groups.listing")}</>
            : <button className="btn primary" onClick={() => void load(false)}>{t("onboarding.groups.load")}</button>}
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
                <span className="g-ic">
                  {d.kind === "channel" ? <Ic.Radio size={14} /> : <Ic.Users size={14} />}
                </span>
                <span className="g-main">
                  <span className="g-title" dir="auto">{d.title}</span>
                  <span className="g-meta">{d.username ? `@${d.username}` : d.chat_id}</span>
                </span>
              </label>
            ))}
          </div>
          <div className="wizard-actions">
            <button className="btn ghost sm" onClick={() => void load(true)} disabled={busy}>
              <Ic.RotateCcw size={13} /> {t("onboarding.groups.reload")}
            </button>
            <span style={{ flex: 1 }} />
            <button className="btn primary" disabled={busy || checked.size === 0} onClick={() => void track()}>
              {t("onboarding.groups.track")}
              {checked.size > 0 ? ` ${nounT(t, lang, "system.pl.group", checked.size)}` : ""}
            </button>
            <button className="btn ghost" onClick={onDone}>{t("onboarding.skip")}</button>
          </div>
        </>
      )}
    </div>
  );
}

function AiStep({ onDone, t }: { onDone: () => void; t: TFn }) {
  const { appState, refreshAppState } = useStore();
  const [editing, setEditing] = useState(false);
  const configured = appState?.ai_configured === true;

  return (
    <div>
      <h3>
        {t("system.section.ai")} <span className="badge">{t("onboarding.ai.optional")}</span>
      </h3>
      <p className="dim">{t("onboarding.ai.intro")}</p>

      {configured && !editing ? (
        <>
          <div className="settings-row">
            <span>{t("system.provider")}</span>
            <span>
              <span className="badge good" dir="ltr">{appState?.ai_provider_host} · {appState?.ai_model}</span>{" "}
              <button className="link" onClick={() => setEditing(true)}>{t("system.change")}</button>
            </span>
          </div>
          <div className="wizard-actions" style={{ justifyContent: "flex-end" }}>
            <button className="btn primary" onClick={() => void onDone()}>
              {t("onboarding.continue")} <Ic.ArrowRight size={13} />
            </button>
          </div>
        </>
      ) : (
        <AiProviderForm t={t} onSaved={() => void onDone()} />
      )}

      <div className="wizard-actions" style={{ justifyContent: "space-between" }}>
        <button className="btn ghost" onClick={() => void onDone()}>{t("onboarding.skip")}</button>
        {configured && !editing && (
          <button className="link" onClick={() => void refreshAppState()}>{t("onboarding.ai.recheck")}</button>
        )}
      </div>
      <p className="mm-note dim">{t("onboarding.ai.privacyNote")}</p>
    </div>
  );
}

function SyncStep({ onDone, t }: { onDone: () => void; t: TFn }) {
  const { jobs, refreshJobs } = useStore();
  const [started, setStarted] = useState(false);
  const tail = jobs?.log?.trim().split("\n").slice(-3).join("\n");

  return (
    <div>
      <h3>{t("onboarding.step.sync")}</h3>
      <p className="dim">{t("onboarding.sync.intro")}</p>
      <div className="wizard-actions" style={{ justifyContent: "center", padding: 16 }}>
        {!started ? (
          <button
            className="btn primary"
            onClick={async () => { await api.sync(); await refreshJobs(); setStarted(true); }}
          >
            {t("onboarding.sync.start")}
          </button>
        ) : (
          <div className="mm-progress" style={{ width: "100%" }}>
            <Ic.Spin size={13} className="spin" />
            <div style={{ flex: 1 }}>
              <div>
                {jobs?.running
                  ? (jobs.name === "track"
                    ? t("onboarding.sync.backfilling")
                    : t("onboarding.sync.syncing"))
                  : jobs?.queued?.length
                    ? t("onboarding.sync.queuedBehind", {
                      jobs: jobs.queued.map((n) => t(jobKey(n))).join(", "),
                    })
                    : t("onboarding.sync.queuedStarting")}
              </div>
              <pre className="mm-log">{tail || t("onboarding.sync.starting")}</pre>
              {(jobs?.running || (jobs?.queued?.length ?? 0) > 0) && (
                <button className="btn danger sm" style={{ marginTop: 8 }}
                  onClick={async () => { await api.jobStop(false); await refreshJobs(); }}>
                  <Ic.CircleOff size={13} /> {t("onboarding.sync.stop")}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
      <div className="wizard-actions" style={{ justifyContent: "flex-end" }}>
        <button className="btn primary" onClick={() => void onDone()}>
          {t("onboarding.sync.finish")} <Ic.ArrowRight size={13} />
        </button>
      </div>
    </div>
  );
}

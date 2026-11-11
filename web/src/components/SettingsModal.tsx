/** Settings modal: language, theme, account, credentials editing, AI
 *  provider, auto-sync scheduler, search normalization (v0.4), and the
 *  explicit erase-all-data action (Settings "Data" section). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { AiUsage, SchedulerState } from "../api/types";
import { fmtLocal, intervalKey, intervalN, nfmt } from "../utils/format";
import { Ic } from "../design/icons";
import { Modal } from "./Modal";
import { AiProviderForm, CredsForm } from "./SetupForms";

const INTERVALS = [15, 30, 60, 180, 360, 720, 1440];

/** The exact confirmation token required by api/data.py (case-sensitive). */
const ERASE_WORD = "ERASE";

type TFn = (key: string, vars?: Record<string, string | number>) => string;

type DataStatus = Awaited<ReturnType<typeof api.dataStatus>>;

/** Localized count noun: Arabic picks .one/.two/.few/.many plural classes,
 *  English .one/.many. `base` is a "system.pl.*" key prefix. */
function nounT(t: TFn, lang: string, base: string, n: number): string {
  const sfx = lang === "ar"
    ? n === 1 ? "one" : n === 2 ? "two" : n <= 10 ? "few" : "many"
    : n === 1 ? "one" : "many";
  return t(`${base}.${sfx}`, { n });
}

/** Human file size for the data-overview badge. */
function fmtBytes(n: number): string {
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${i === 0 || v >= 100 ? Math.round(v) : Math.round(v * 10) / 10} ${units[i]}`;
}

export function SettingsModal({ onClose }: { onClose: () => void }) {
  const { theme, toggleTheme, appState, setWizardOpen, toast, refreshAppState, refreshJobs } = useStore();
  const { t, lang, setLang } = useLang();
  const [editing, setEditing] = useState<null | "telegram" | "ai">(null);
  const [sched, setSched] = useState<SchedulerState | null>(null);
  const [schedBusy, setSchedBusy] = useState(false);
  const [usage, setUsage] = useState<AiUsage | null>(null);

  // erase-all-data flow (inline confirm panel; see api/data.py)
  const [eraseOpen, setEraseOpen] = useState(false);
  const [eraseData, setEraseData] = useState<DataStatus | null>(null);
  const [eraseText, setEraseText] = useState("");
  const [erasing, setErasing] = useState(false);

  useEffect(() => {
    api.schedulerState().then(setSched).catch(() => { /* ignore */ });
    api.aiUsage().then(setUsage).catch(() => { /* ignore */ });
  }, []);

  const applySched = async (p: { enabled?: boolean; interval_min?: number }) => {
    setSchedBusy(true);
    try {
      setSched(await api.schedulerConfig(p));
      toast(t("system.schedSaved"), "good");
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setSchedBusy(false);
    }
  };

  const reindex = async () => {
    try {
      const r = await api.reindex();
      toast(r.started ? t("system.reindexQueued", { jobs: t("nav.jobs") }) : t("system.reindexAlready"), "info");
      onClose();
      await refreshJobs();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const logout = async () => {
    try {
      await api.authLogout();
      toast(t("system.loggedOut"), "good");
      await refreshAppState();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const credsSaved = async () => {
    toast(t("system.credsSaved"), "good");
    await refreshAppState();
    setEditing(null);
  };

  const openErase = () => {
    setEraseOpen(true);
    setEraseText("");
    setEraseData(null);
    api.dataStatus().then(setEraseData).catch(() => { /* panel still usable */ });
  };

  const doErase = async () => {
    if (eraseText !== ERASE_WORD || erasing) return;
    setErasing(true);
    try {
      await api.dataErase(eraseText);
      toast(t("system.eraseDone"), "good");
      setTimeout(() => window.location.reload(), 1500);
    } catch (e) {
      setErasing(false);
      toast(`${t("system.eraseFailed")}: ${(e as Error).message}`, "err");
    }
  };

  return (
    <Modal title={t("shell.settings")} onClose={onClose}>
      {/* General: language */}
      <div className="label" style={{ marginTop: 6 }}>{t("system.section.general")}</div>
      <div className="settings-row">
        <span>{t("system.language")}</span>
        <div className="seg">
          <button className={lang === "en" ? "on" : ""} onClick={() => lang !== "en" && setLang("en")}>English</button>
          <button className={lang === "ar" ? "on" : ""} onClick={() => lang !== "ar" && setLang("ar")}>العربية</button>
        </div>
      </div>

      {/* Data: explicit erase-all action */}
      <div className="label" style={{ marginTop: 18 }}>{t("system.section.data")}</div>
      <div className="settings-row">
        <span>{t("system.eraseTitle")}</span>
        <span>
          <button className="btn danger sm" disabled={erasing} onClick={openErase}>
            <Ic.Trash size={13} /> {t("system.eraseOpen")}
          </button>
        </span>
      </div>
      {eraseOpen && (
        <div className="settings-edit">
          <p className="mm-note dim erase-warn">
            <Ic.CircleAlert size={14} /> {t("system.eraseConfirmHint")}
          </p>
          {eraseData ? (
            <ul className="erase-list">
              <li>
                <Ic.Database size={14} />
                <span>
                  <b>{t("system.eraseRowDb")}</b> — <span dir="ltr">{eraseData.db_path}</span>
                  {eraseData.db_size > 0 ? ` (~${fmtBytes(eraseData.db_size)})` : ""}
                </span>
              </li>
              <li>
                <Ic.KeyRound size={14} />
                <span>
                  <b>{t("system.eraseRowSession")}</b> — <span dir="ltr">{eraseData.session_path}</span>
                </span>
              </li>
              <li>
                <Ic.Sliders size={14} />
                <span>
                  <b>{t("system.eraseRowConfig")}</b> — <span dir="ltr">{eraseData.data_dir}</span>
                </span>
              </li>
            </ul>
          ) : (
            <div className="mm-note dim">
              <Ic.Spin size={13} className="spin" /> {t("state.loading")}
            </div>
          )}
          <label className="field">
            <span>{t("system.eraseTypePrompt", { word: ERASE_WORD })}</span>
            <input
              className="input"
              dir="ltr"
              autoComplete="off"
              spellCheck={false}
              placeholder={ERASE_WORD}
              value={eraseText}
              onChange={(e) => setEraseText(e.target.value)}
            />
          </label>
          <div className="settings-actions">
            <button className="btn ghost sm" disabled={erasing} onClick={() => setEraseOpen(false)}>
              {t("action.cancel")}
            </button>
            <button
              className="btn danger sm"
              disabled={eraseText !== ERASE_WORD || erasing}
              onClick={() => void doErase()}
            >
              {erasing ? <Ic.Spin size={13} className="spin" /> : <Ic.Trash size={13} />}{" "}
              {t("system.eraseGo")}
            </button>
          </div>
        </div>
      )}

      {/* Appearance: theme */}
      <div className="label" style={{ marginTop: 18 }}>{t("system.section.appearance")}</div>
      <div className="settings-row">
        <span>{t("system.theme")}</span>
        <div className="seg">
          <button className={theme === "dark" ? "on" : ""} onClick={() => theme !== "dark" && toggleTheme()}>{t("system.theme.dark")}</button>
          <button className={theme === "light" ? "on" : ""} onClick={() => theme !== "light" && toggleTheme()}>{t("system.theme.light")}</button>
        </div>
      </div>

      {/* Telegram */}
      <div className="label" style={{ marginTop: 18 }}>{t("system.section.telegram")}</div>
      <div className="settings-row">
        <span>{t("system.account")}</span>
        <span>
          {appState?.authenticated === true
            ? <span className="badge good">
                <Ic.CircleCheck size={11} />{" "}
                {appState.auth_user
                  ? t("system.loggedInAs", { user: appState.auth_user })
                  : t("system.loggedIn")}
              </span>
            : appState?.authenticated === false
              ? <span className="badge err">{t("system.notLoggedIn")}</span>
              : <span className="badge">{t("system.checking")}</span>}
        </span>
      </div>
      <div className="settings-row">
        <span>{t("system.apiCredentials")}</span>
        <span>
          {appState?.telegram_configured
            ? <span className="badge good"><Ic.Check size={11} /> {t("system.configured")}</span>
            : <span className="badge warn">{t("system.missing")}</span>}{" "}
          <button className="link" onClick={() => setEditing(editing === "telegram" ? null : "telegram")}>
            {editing === "telegram" ? t("action.cancel") : t("system.change")}
          </button>
        </span>
      </div>
      {editing === "telegram" && (
        <div className="settings-edit">
          <CredsForm t={t} onSaved={credsSaved} submitLabel={t("system.saveCredentials")} />
        </div>
      )}
      <div className="settings-actions">
        <button className="btn ghost sm" onClick={() => { onClose(); setWizardOpen(true); }}>{t("shell.setupWizard")}</button>
        {appState?.authenticated && <button className="btn danger sm" onClick={() => void logout()}>{t("system.logoutTelegram")}</button>}
      </div>

      {/* Auto-sync */}
      <div className="label" style={{ marginTop: 18 }}>{t("system.section.autoSync")}</div>
      <div className="settings-row">
        <span>{t("system.autoSync")}</span>
        <span>
          <button
            className={`btn sm ${sched?.enabled ? "primary" : "ghost"}`}
            disabled={schedBusy || !sched}
            onClick={() => void applySched({ enabled: !sched?.enabled })}
          >
            {sched?.enabled ? t("system.on") : t("system.off")}
          </button>
        </span>
      </div>
      <div className="settings-row">
        <span>{t("system.interval")}</span>
        <select
          className="input"
          style={{ maxWidth: 160 }}
          disabled={schedBusy || !sched}
          value={sched?.interval_min ?? 360}
          onChange={(e) => void applySched({ interval_min: Number(e.target.value) })}
        >
          {INTERVALS.map((min) => (
            <option key={min} value={min}>
              {t(intervalKey(min), { n: intervalN(min) })}
            </option>
          ))}
        </select>
      </div>
      {sched && (
        <p className="mm-note dim">
          {t("system.sched.note")}
          {sched.next_due && <> {t("system.sched.next")} <b>{fmtLocal(sched.next_due)}</b>.</>}
          {sched.last_success && <> {t("system.sched.last")} <b>{fmtLocal(sched.last_success)}</b>.</>}
        </p>
      )}

      {/* Search normalization */}
      <div className="label" style={{ marginTop: 18 }}>{t("system.section.normalization")}</div>
      <div className="settings-row">
        <span>{t("system.normLevel")}</span>
        <span className="badge good">{t("system.normExtended")}</span>
      </div>
      <div className="settings-actions">
        <button className="btn ghost sm" onClick={() => void reindex()} title={t("system.reindexTitle")}>
          {t("system.reindex")}
        </button>
      </div>
      <p className="mm-note dim">
        {t("system.norm.noteA")}{" "}
        <code className="kbd" style={{ marginInline: 4 }}>NORMALIZATION=standard</code>{" "}
        {t("system.norm.noteB", { button: t("system.reindex") })}
      </p>

      {/* AI provider */}
      <div className="label" style={{ marginTop: 18 }}>{t("system.section.ai")}</div>
      <div className="settings-row">
        <span>{t("system.provider")}</span>
        <span>
          {appState?.ai_configured
            ? <span className="badge good" dir="ltr">{appState.ai_provider_host} · {appState.ai_model}</span>
            : <span className="badge warn">{t("system.aiNotConfigured")}</span>}{" "}
          <button className="link" onClick={() => setEditing(editing === "ai" ? null : "ai")}>
            {editing === "ai" ? t("action.cancel") : t("system.change")}
          </button>
        </span>
      </div>
      {editing === "ai" && (
        <div className="settings-edit">
          <AiProviderForm t={t} onSaved={credsSaved} submitLabel={t("system.saveProvider")} />
        </div>
      )}
      <div className="settings-row">
        <span>{t("system.aiUsage")}</span>
        <span className="badge" title={t("system.aiUsageTitle")}>
          {usage
            ? t("system.usageBadge", {
              requests: nounT(t, lang, "system.pl.request", usage.total.requests),
              tokens: nfmt((usage.total.tokens_in ?? 0) + (usage.total.tokens_out ?? 0)),
            })
            : "…"}
        </span>
      </div>
      {usage && Object.keys(usage.by_task).length > 0 && (
        <p className="mm-note dim">
          {Object.entries(usage.by_task).map(([task, u]) =>
            `${task}: ${u.requests}`).join(" · ")}
        </p>
      )}
      <p className="mm-note dim">
        {t("system.ai.noteA")} <code className="kbd" style={{ marginInline: 4 }}>.env</code>{" "}
        {t("system.ai.noteB")}
      </p>
    </Modal>
  );
}

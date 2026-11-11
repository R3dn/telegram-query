/** Left sidebar: identity, navigation, group selection, saved searches,
 *  sync status + auto-sync schedule. */
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { SchedulerState } from "../api/types";
import { fmtDate, intervalKey, intervalN, jobKey, nfmt } from "../utils/format";
import { Ic } from "../design/icons";

export function Sidebar() {
  const store = useStore();
  const { t, lang, setLang } = useLang();
  const {
    groups, selection, toggleGroup, clearSelection,
    jobs, appState, setModal, setWizardOpen, setRightTab, setRightOpen, setMode,
    savedSearches, mode, theme, toggleTheme,
  } = store;
  const [filter, setFilter] = useState("");
  const [sched, setSched] = useState<SchedulerState | null>(null);
  const [alertsUnread, setAlertsUnread] = useState(0);

  const shown = useMemo(
    () => groups.filter((g) => !filter || g.title.toLowerCase().includes(filter.toLowerCase())),
    [groups, filter],
  );

  useEffect(() => {
    let dead = false;
    const load = async () => {
      try {
        const s = await api.schedulerState();
        if (!dead) setSched(s);
      } catch { /* ignore */ }
      try {
        const u = await api.alertsUnread();
        if (!dead) setAlertsUnread(u.unread);
      } catch { /* ignore */ }
    };
    void load();
    const timer = window.setInterval(load, 60_000);
    return () => { dead = true; clearInterval(timer); };
  }, [jobs?.last_done]);

  const running = jobs?.running;
  const queued = jobs?.queued?.length ?? 0;
  const lastDone = jobs?.last_done;
  const pendingBackfills = appState?.pending_backfills ?? 0;

  const syncNow = async () => {
    try {
      const r = await api.sync();
      if (r.started) store.toast(t("sync.started"), "good");
      else store.toast(t("sync.alreadyQueued"), "info");
      void store.refreshJobs();   // kick off live polling for the new job
    } catch (e) {
      store.toast((e as Error).message, "err");
    }
  };

  const askAi = () => {
    setRightTab("ai");
    setRightOpen(true);
    if (window.matchMedia("(max-width: 1100px)").matches) {
      document.body.classList.add("tgq-right-open");
    }
  };

  const nav = (active: boolean, onClick: () => void, icon: React.ReactNode, label: string, extra?: React.ReactNode) => (
    <button className={`nav-item ${active ? "on" : ""}`} onClick={onClick}>
      <span className="nav-ic">{icon}</span> {label}
      {extra}
    </button>
  );

  return (
    <aside className="sidebar">
      <div className="side-top">
        <div className="logo" title={t("app.name")}>
          <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden>
            <defs>
              <linearGradient id="logo-g" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#5b8def" />
                <stop offset="1" stopColor="#3e6fc9" />
              </linearGradient>
            </defs>
            <rect width="24" height="24" rx="7" fill="url(#logo-g)" />
            <path d="M6 11.5 18 6l-4.5 12-2.6-4.1L6 11.5z" fill="#fff" />
          </svg>
          <span>{t("app.name")}</span>
        </div>
      </div>

      <nav className="side-nav">
        <div className="side-nav-group" style={{ padding: 0 }}>
          <span className="label">{t("nav.group.discover")}</span>
          {nav(mode === "discover", () => setMode("discover"), <Ic.TrendingUp size={16} />, t("nav.discover"))}
          {nav(mode === "entities", () => setMode("entities"), <Ic.MapPin size={16} />, t("nav.entities"))}
        </div>
        <div style={{ height: 2 }} />
        {nav(mode === "browse" || mode === "search", () => setMode("browse"), <Ic.Search size={16} />, t("nav.browse"))}
        {nav(false, askAi, <Ic.Sparkles size={16} />, t("nav.askAi"))}
        {nav(mode === "bookmarks", () => setMode("bookmarks"), <Ic.Bookmark size={16} />, t("nav.bookmarks"))}
        {nav(false, () => setModal("jobs"), <Ic.RefreshCw size={16} />, t("nav.jobs"),
          running
            ? <span className="spinner" style={{ marginInlineStart: "auto" }} />
            : !running && queued > 0
              ? <span className="badge warn" style={{ marginInlineStart: "auto" }}>{queued}</span>
              : undefined)}
      </nav>

      <div className="side-nav side-nav-group">
        <span className="label">{t("nav.group.knowledge")}</span>
        {nav(mode === "deals", () => setMode("deals"), <Ic.Tag size={16} />, t("nav.deals"))}
        {nav(mode === "decisions", () => setMode("decisions"), <Ic.Scale size={16} />, t("nav.decisions"))}
        {nav(mode === "research", () => setMode("research"), <Ic.BookOpen size={16} />, t("nav.research"))}
        {nav(mode === "faqs", () => setMode("faqs"), <Ic.HelpCircle size={16} />, t("nav.faqs"))}
      </div>

      <div className="side-nav side-nav-group">
        <span className="label">{t("nav.group.monitor")}</span>
        {nav(mode === "watchlists", () => setMode("watchlists"), <Ic.Eye size={16} />, t("nav.watchlists"))}
        {nav(mode === "alerts", () => setMode("alerts"), <Ic.Bell size={16} />, t("nav.alerts"),
          alertsUnread > 0 && <span className="badge warn" style={{ marginInlineStart: "auto" }}>{alertsUnread}</span>)}
        {nav(mode === "digests", () => setMode("digests"), <Ic.Newspaper size={16} />, t("nav.digests"))}
      </div>

      <div className="side-section">
        <div className="side-head">
          <span className="label">{t("nav.groups")}</span>
          {selection.size > 0 && (
            <button className="link" onClick={clearSelection}>{t("action.clear")}</button>
          )}
        </div>
        <input
          className="input"
          style={{ marginBottom: 6 }}
          placeholder={t("groups.filterPlaceholder")}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <div className="group-list">
          <button className={`group-row ${selection.size === 0 ? "on" : ""}`} onClick={clearSelection}>
            <span className="g-ic"><Ic.Globe size={14} /></span>
            <span className="g-main">
              <span className="g-title">{t("groups.all")}</span>
              <span className="g-meta">{t("groups.messagesCount", { n: nfmt(appState?.messages ?? 0) })}</span>
            </span>
          </button>
          {shown.map((g) => (
            <button
              key={g.chat_id}
              className={`group-row ${selection.has(g.chat_id) ? "on" : ""}`}
              onClick={() => toggleGroup(g.chat_id)}
              title={g.title}
            >
              <span className="g-ic">
                {g.kind === "channel" ? <Ic.Radio size={14} /> : <Ic.Users size={14} />}
              </span>
              <span className="g-main">
                <span className="g-title" dir="auto">{g.title}</span>
                <span className="g-meta">
                  {t("groups.msgs", { n: nfmt(g.message_count) })}
                  {g.last_message ? ` · ${fmtDate(g.last_message)}` : ""}
                </span>
              </span>
            </button>
          ))}
          {shown.length === 0 && groups.length > 0 && <div className="side-note">{t("groups.noMatch")}</div>}
          {groups.length === 0 && <div className="side-note">{t("groups.noneTracked")}</div>}
        </div>
        <button className="btn ghost sm" style={{ width: "100%", marginTop: 8 }} onClick={() => setModal("manage")}>
          <Ic.Settings size={13} /> {t("groups.manage")}
        </button>
      </div>

      {savedSearches.length > 0 && (
        <div className="side-section saved-section">
          <div className="side-head">
            <span className="label">{t("saved.title")}</span>
          </div>
          <div className="saved-list">
            {savedSearches.map((s) => (
              <SavedRow key={s.id} id={s.id} />
            ))}
          </div>
        </div>
      )}

      <div className="side-bottom">
        <div className="sync-card">
          <div className="sync-row">
            {running ? (
              <><span className="spinner" /> <span>{t("sync.running", { job: t(jobKey(jobs?.name)) })}</span></>
            ) : lastDone ? (
              <>
                <span className={`dot ${lastDone.ok ? "good" : "err"}`} />
                <span>{t("sync." + (lastDone.ok ? "done" : "failed"), { job: t(jobKey(lastDone.name)) })}</span>
              </>
            ) : (
              <><span className="dot" /> <span>{t("sync.idle")}</span></>
            )}
            {queued > 0 && <span className="badge warn">{t("sync.queued", { n: queued })}</span>}
          </div>
          {sched?.enabled && sched.next_due && !running && (
            <div className="sync-row dim" title={t("sync.configureHint")}>
              {t("sync.autoNext", {
                interval: t(intervalKey(sched.interval_min), { n: intervalN(sched.interval_min) }),
                time: new Date(sched.next_due).toLocaleTimeString(undefined, {
                  hour: "2-digit", minute: "2-digit",
                }),
              })}
            </div>
          )}
          {sched?.last_success && (
            <div className="sync-row dim">
              {t("sync.lastOk", {
                when: new Date(sched.last_success).toLocaleString(undefined, {
                  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                }),
              })}
            </div>
          )}
          {pendingBackfills > 0 && (
            <div className="sync-row dim">{t("sync.backfills", { n: pendingBackfills })}</div>
          )}
          <div className="sync-actions">
            <button className="btn primary sm" disabled={!!running || queued > 0} onClick={syncNow}>
              <Ic.RefreshCw size={13} /> {t("sync.now")}
            </button>
            <button className="btn ghost sm" onClick={() => setModal("jobs")}>{t("sync.details")}</button>
          </div>
        </div>
        <div className="side-foot">
          <button
            className="link"
            title={lang === "ar" ? "English" : "العربية"}
            onClick={() => setLang(lang === "ar" ? "en" : "ar")}
          >
            {lang === "ar" ? "EN" : "ع"}
          </button>
          <span>·</span>
          <button
            className="link"
            title={theme === "dark" ? "Light theme" : "Dark theme"}
            onClick={toggleTheme}
          >
            {theme === "dark" ? <Ic.Sun size={12} /> : <Ic.Moon size={12} />}
          </button>
          <span>·</span>
          <button className="link" onClick={() => setWizardOpen(true)}>{t("shell.setupWizard")}</button>
          <span>·</span>
          <button className="link" onClick={() => setModal("settings")}>{t("shell.settings")}</button>
        </div>
      </div>
    </aside>
  );
}

/** One saved-search row: run by clicking, rename/duplicate/delete inline. */
function SavedRow({ id }: { id: number }) {
  const { savedSearches, applySaved, refreshSaved, toast } = useStore();
  const { t } = useLang();
  const s = savedSearches.find((x) => x.id === id);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(s?.name ?? "");
  const [confirming, setConfirming] = useState(false);

  if (!s) return null;

  const save = async () => {
    const n = name.trim();
    if (!n) return;
    try {
      await api.savedUpdate(s.id, {
        name: n, q: s.q, chat_ids: s.chat_ids, sender: s.sender,
        media: s.media, date_from: s.date_from, date_to: s.date_to, sort: s.sort,
      });
      setEditing(false);
      await refreshSaved();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const duplicate = async () => {
    try {
      await api.savedDuplicate(s.id);
      await refreshSaved();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const remove = async () => {
    try {
      await api.savedDelete(s.id);
      setConfirming(false);
      await refreshSaved();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  if (editing) {
    return (
      <div className="saved-row editing">
        <input
          className="input"
          value={name}
          dir="auto"
          autoFocus
          maxLength={100}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void save();
            if (e.key === "Escape") setEditing(false);
          }}
        />
        <button className="btn primary sm" onClick={() => void save()}><Ic.Check size={13} /></button>
        <button className="btn ghost sm" onClick={() => { setEditing(false); setName(s.name); }}><Ic.Close size={13} /></button>
      </div>
    );
  }

  return (
    <div className="saved-row">
      <button className="saved-main" onClick={() => applySaved(s)} title={s.q || t("saved.browseWith")}>
        <span className="g-title" dir="auto">{s.name}</span>
        <span className="g-meta" dir="auto">{s.q || t("saved.filtersOnly")}</span>
      </button>
      <button className="saved-act" title={t("saved.rename")} onClick={() => { setName(s.name); setEditing(true); }}>
        <Ic.Pencil size={13} />
      </button>
      <button className="saved-act" title={t("saved.duplicate")} onClick={() => void duplicate()}>
        <Ic.Layers size={13} />
      </button>
      <button
        className={`saved-act ${confirming ? "danger" : ""}`}
        title={confirming ? t("saved.clickAgain") : t("saved.delete")}
        onClick={() => {
          if (confirming) void remove();
          else {
            setConfirming(true);
            setTimeout(() => setConfirming(false), 3000);
          }
        }}
      >
        {confirming ? <Ic.CircleAlert size={13} /> : <Ic.Trash size={13} />}
      </button>
    </div>
  );
}

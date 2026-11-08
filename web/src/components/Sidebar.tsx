/** Left sidebar: identity, navigation, group selection, saved searches,
 *  sync status + auto-sync schedule (v0.4). */
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { SchedulerState } from "../api/types";
import { fmtDate, intervalLabel, jobLabel, nfmt } from "../utils/format";

export function Sidebar() {
  const store = useStore();
  const {
    groups, selection, toggleGroup, clearSelection,
    jobs, appState, setModal, setWizardOpen, setRightTab, setMode,
    savedSearches, mode,
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
    const t = window.setInterval(load, 60_000);
    return () => { dead = true; clearInterval(t); };
  }, [jobs?.last_done]);

  const running = jobs?.running;
  const queued = jobs?.queued?.length ?? 0;
  const lastDone = jobs?.last_done;
  const pendingBackfills = appState?.pending_backfills ?? 0;

  const syncNow = async () => {
    try {
      const r = await api.sync();
      if (r.started) store.toast("Sync started", "good");
      else store.toast("Sync is already queued", "info");
      void store.refreshJobs();   // kick off live polling for the new job
    } catch (e) {
      store.toast((e as Error).message, "err");
    }
  };

  const askAi = () => {
    setRightTab("ai");
    if (window.matchMedia("(max-width: 1100px)").matches) {
      document.body.classList.add("tgq-right-open");
    }
  };

  return (
    <aside className="sidebar">
      <div className="side-top">
        <div className="logo" title="Telegram Query">
          <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden>
            <rect width="24" height="24" rx="6" fill="var(--accent)" />
            <path d="M6 11.5 18 6l-4.5 12-2.6-4.1L6 11.5z" fill="#fff" />
          </svg>
          <span>Telegram Query</span>
        </div>
      </div>

      <nav className="side-nav">
        <div className="side-nav-group" style={{ padding: 0 }}>
          <span className="label">Discover</span>
          <button className={`nav-item ${mode === "discover" ? "on" : ""}`} onClick={() => setMode("discover")}>
            <span className="nav-ic">📈</span> Discover
          </button>
          <button className={`nav-item ${mode === "entities" ? "on" : ""}`} onClick={() => setMode("entities")}>
            <span className="nav-ic">📌</span> Entities
          </button>
        </div>
        <div style={{ height: 6 }} />
        <button className={`nav-item ${mode === "browse" || mode === "search" ? "on" : ""}`} onClick={() => setMode("browse")}>
          <span className="nav-ic">🔍</span> Browse &amp; search
        </button>
        <button className="nav-item" onClick={askAi}>
          <span className="nav-ic">✦</span> Ask AI
        </button>
        <button className={`nav-item ${mode === "bookmarks" ? "on" : ""}`} onClick={() => setMode("bookmarks")}>
          <span className="nav-ic">⭐</span> Bookmarks
        </button>
        <button className="nav-item" onClick={() => setModal("jobs")}>
          <span className="nav-ic">⇄</span> Jobs
          {running && <span className="spinner" style={{ marginInlineStart: "auto" }} />}
          {!running && queued > 0 && <span className="badge warn" style={{ marginInlineStart: "auto" }}>{queued}</span>}
        </button>
      </nav>

      <div className="side-nav side-nav-group">
        <span className="label">Knowledge</span>
        <button className={`nav-item ${mode === "deals" ? "on" : ""}`} onClick={() => setMode("deals")}>
          <span className="nav-ic">🏷</span> Deals
        </button>
        <button className={`nav-item ${mode === "research" ? "on" : ""}`} onClick={() => setMode("research")}>
          <span className="nav-ic">🔬</span> Research
        </button>
        <button className={`nav-item ${mode === "faqs" ? "on" : ""}`} onClick={() => setMode("faqs")}>
          <span className="nav-ic">❓</span> FAQs
        </button>
      </div>

      <div className="side-nav side-nav-group">
        <span className="label">Monitor</span>
        <button className={`nav-item ${mode === "watchlists" ? "on" : ""}`} onClick={() => setMode("watchlists")}>
          <span className="nav-ic">👁</span> Watchlists
        </button>
        <button className={`nav-item ${mode === "alerts" ? "on" : ""}`} onClick={() => setMode("alerts")}>
          <span className="nav-ic">🔔</span> Alerts
          {alertsUnread > 0 && <span className="badge warn" style={{ marginInlineStart: "auto" }}>{alertsUnread}</span>}
        </button>
        <button className={`nav-item ${mode === "digests" ? "on" : ""}`} onClick={() => setMode("digests")}>
          <span className="nav-ic">📰</span> Digests
        </button>
      </div>

      <div className="side-section">
        <div className="side-head">
          <span className="label">Groups</span>
          {selection.size > 0 && (
            <button className="link" onClick={clearSelection}>clear</button>
          )}
        </div>
        <input
          className="input"
          style={{ marginBottom: 6 }}
          placeholder="Filter groups…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <div className="group-list">
          <button className={`group-row ${selection.size === 0 ? "on" : ""}`} onClick={clearSelection}>
            <span className="g-ic">🌐</span>
            <span className="g-main">
              <span className="g-title">All groups</span>
              <span className="g-meta">{nfmt(appState?.messages ?? 0)} messages</span>
            </span>
          </button>
          {shown.map((g) => (
            <button
              key={g.chat_id}
              className={`group-row ${selection.has(g.chat_id) ? "on" : ""}`}
              onClick={() => toggleGroup(g.chat_id)}
              title={g.title}
            >
              <span className="g-ic">{g.kind === "channel" ? "📣" : "👥"}</span>
              <span className="g-main">
                <span className="g-title" dir="auto">{g.title}</span>
                <span className="g-meta">
                  {nfmt(g.message_count)} msgs{g.last_message ? ` · ${fmtDate(g.last_message)}` : ""}
                </span>
              </span>
            </button>
          ))}
          {shown.length === 0 && groups.length > 0 && <div className="side-note">No groups match.</div>}
          {groups.length === 0 && <div className="side-note">No groups tracked yet.</div>}
        </div>
        <button className="btn ghost sm" style={{ width: "100%", marginTop: 8 }} onClick={() => setModal("manage")}>
          Manage groups
        </button>
      </div>

      {savedSearches.length > 0 && (
        <div className="side-section saved-section">
          <div className="side-head">
            <span className="label">Saved searches</span>
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
              <><span className="spinner" /> <span>{jobLabel(jobs?.name)} running…</span></>
            ) : lastDone ? (
              <><span className={`dot ${lastDone.ok ? "good" : "err"}`} /> <span>{jobLabel(lastDone.name)} {lastDone.ok ? "done" : "failed"}</span></>
            ) : (
              <><span className="dot" /> <span>Idle</span></>
            )}
            {queued > 0 && <span className="badge warn">{queued} queued</span>}
          </div>
          {sched?.enabled && sched.next_due && !running && (
            <div className="sync-row dim" title="Configure in Settings">
              auto-sync {intervalLabel(sched.interval_min)} · next{" "}
              {new Date(sched.next_due).toLocaleTimeString(undefined, {
                hour: "2-digit", minute: "2-digit",
              })}
            </div>
          )}
          {sched?.last_success && (
            <div className="sync-row dim">
              last ok {new Date(sched.last_success).toLocaleString(undefined, {
                month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
              })}
            </div>
          )}
          {pendingBackfills > 0 && (
            <div className="sync-row dim">{pendingBackfills} backfill{pendingBackfills > 1 ? "s" : ""} can resume</div>
          )}
          <div className="sync-actions">
            <button className="btn primary sm" disabled={!!running || queued > 0} onClick={syncNow}>Sync now</button>
            <button className="btn ghost sm" onClick={() => setModal("jobs")}>Details</button>
          </div>
        </div>
        <div className="side-foot">
          <button className="link" onClick={() => setWizardOpen(true)}>Setup wizard</button>
          <span>·</span>
          <button className="link" onClick={() => setModal("settings")}>Settings</button>
        </div>
      </div>
    </aside>
  );
}

/** One saved-search row: run by clicking, rename/duplicate/delete inline. */
function SavedRow({ id }: { id: number }) {
  const { savedSearches, applySaved, refreshSaved, toast } = useStore();
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
        <button className="btn primary sm" onClick={() => void save()}>✓</button>
        <button className="btn ghost sm" onClick={() => { setEditing(false); setName(s.name); }}>✕</button>
      </div>
    );
  }

  return (
    <div className="saved-row">
      <button className="saved-main" onClick={() => applySaved(s)} title={s.q || "browse with these filters"}>
        <span className="g-title" dir="auto">{s.name}</span>
        <span className="g-meta" dir="auto">{s.q || "filters only"}</span>
      </button>
      <button className="saved-act" title="Rename" onClick={() => { setName(s.name); setEditing(true); }}>✎</button>
      <button className="saved-act" title="Duplicate" onClick={() => void duplicate()}>⧉</button>
      <button
        className={`saved-act ${confirming ? "danger" : ""}`}
        title={confirming ? "Click again to delete" : "Delete"}
        onClick={() => {
          if (confirming) void remove();
          else {
            setConfirming(true);
            setTimeout(() => setConfirming(false), 3000);
          }
        }}
      >
        {confirming ? "؟" : "✕"}
      </button>
    </div>
  );
}

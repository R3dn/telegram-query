/** Left sidebar: identity, navigation, group selection, sync status. */
import { useMemo, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { fmtDate, jobLabel, nfmt } from "../utils/format";

export function Sidebar() {
  const store = useStore();
  const {
    groups, selection, toggleGroup, clearSelection,
    jobs, appState, setModal, setWizardOpen, setRightTab, setMode,
  } = store;
  const [filter, setFilter] = useState("");

  const shown = useMemo(
    () => groups.filter((g) => !filter || g.title.toLowerCase().includes(filter.toLowerCase())),
    [groups, filter],
  );

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
        <button className={`nav-item ${store.mode === "browse" ? "on" : ""}`} onClick={() => setMode("browse")}>
          <span className="nav-ic">🔍</span> Browse &amp; search
        </button>
        <button className="nav-item" onClick={askAi}>
          <span className="nav-ic">✦</span> Ask AI
        </button>
        <button className="nav-item" onClick={() => setModal("jobs")}>
          <span className="nav-ic">⇄</span> Jobs
          {running && <span className="spinner" style={{ marginInlineStart: "auto" }} />}
          {!running && queued > 0 && <span className="badge warn" style={{ marginInlineStart: "auto" }}>{queued}</span>}
        </button>
      </nav>

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

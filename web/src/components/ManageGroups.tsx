/** Manage groups: tracked list (untrack with confirm), Telegram discovery
 *  with live progress, track-with-backfill queueing. */
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Dialog } from "../api/types";
import { useStore } from "../state/store";
import { fmtDate, nfmt } from "../utils/format";
import { Modal } from "./Modal";

type Listing =
  | { state: "idle" }
  | { state: "waiting"; note: string }
  | { state: "listing" };

async function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export function ManageGroups({ onClose }: { onClose: () => void }) {
  const { groups, refreshGroups, refreshAppState, jobs, refreshJobs, toast, loadFeed } = useStore();
  const [dialogs, setDialogs] = useState<Dialog[] | null>(null);
  const [listing, setListing] = useState<Listing>({ state: "idle" });
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [armed, setArmed] = useState<{ id: number; mode: "untrack" | "delete" } | null>(null);
  const armTimer = useRef<number | null>(null);

  // tracked-set helpers
  const trackedIds = new Set(groups.map((g) => g.chat_id));

  useEffect(() => {
    if (dialogs === null) void loadDialogs(false);
    return () => { if (armTimer.current) clearTimeout(armTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshDialogs = () => void loadDialogs(true);

  async function loadDialogs(force: boolean) {
    try {
      if (!force) {
        const r = await api.dialogsGet();
        if (r.ready && r.dialogs) {
          setDialogs(r.dialogs);
          return;
        }
      }
      setListing({ state: "waiting", note: "Loading your groups from Telegram…" });
      let tries = 0;
      while (true) {
        const status = await api.jobStatus();
        if (status.running || status.queued.length > 0) {
          setListing({
            state: "waiting",
            note: `Waiting for ${status.name || status.queued[0]}… stop it if you need the list now`,
          });
          await sleep(1300);
          continue;
        }
        const r0 = await api.dialogsGet();
        if (r0.ready && r0.dialogs) {
          setDialogs(r0.dialogs);
          break;
        }
        if (++tries > 3) {
          toast("Could not load the group list from Telegram", "err");
          break;
        }
        await api.dialogsStart();
        void refreshJobs();
        setListing({ state: "listing" });
        await sleep(1300);
      }
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setListing({ state: "idle" });
    }
  }

  const trackChecked = async () => {
    const ids = [...checked].filter((id) => !trackedIds.has(id));
    if (!ids.length) {
      toast("Tick the groups you want to track first", "info");
      return;
    }
    try {
      const r = await api.track(ids);
      if (r.started === false) {
        toast(r.reason === "already_tracked" ? "Already tracking those groups" : "Could not start tracking", "info");
        return;
      }
      const behind = r.queued_behind?.length ?? 0;
      toast(
        behind > 0
          ? `Tracking ${ids.length} group${ids.length > 1 ? "s" : ""} — queued behind ${behind} job${behind > 1 ? "s" : ""}`
          : `Tracking ${ids.length} group${ids.length > 1 ? "s" : ""} — full history backfill starting`,
        "good",
      );
      setChecked(new Set());
      await refreshGroups();
      void refreshJobs();   // kick off live polling for the backfill
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const doUntrack = async (id: number, del: boolean) => {
    try {
      await api.untrack([id], del);
      toast(
        del ? "Untracked — messages permanently deleted"
            : "Untracked — messages kept on disk (re-track to restore)",
        del ? "good" : "info",
      );
      await Promise.all([refreshGroups(), refreshAppState()]);
      void loadFeed(true);
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const arm = (id: number, mode: "untrack" | "delete") => {
    if (armed?.id === id && armed.mode === mode) {
      setArmed(null);
      void doUntrack(id, mode === "delete");
      return;
    }
    setArmed({ id, mode });
    if (armTimer.current) clearTimeout(armTimer.current);
    armTimer.current = window.setTimeout(() => setArmed(null), 4000);
  };

  const busy = listing.state !== "idle";

  const renderOthers = () => {
    if (!dialogs) return null;
    const others = dialogs.filter((d) => !trackedIds.has(d.chat_id));
    if (!others.length) {
      return <p className="mm-note dim">All your Telegram groups are already tracked.</p>;
    }
    return others.map((d) => (
      <label key={d.chat_id} className="mm-row clickable">
        <input
          type="checkbox"
          checked={checked.has(d.chat_id)}
          onChange={() => setChecked((s) => {
            const n = new Set(s);
            if (n.has(d.chat_id)) n.delete(d.chat_id);
            else n.add(d.chat_id);
            return n;
          })}
        />
        <span className="g-ic">{d.kind === "channel" ? "📣" : "👥"}</span>
        <span className="g-main">
          <span className="g-title" dir="auto">{d.title}</span>
          <span className="g-meta">{d.chat_id}{d.username ? ` · @${d.username}` : ""}</span>
        </span>
      </label>
    ));
  };

  return (
    <Modal
      title="Manage groups"
      wide
      onClose={onClose}
      footer={
        <>
          <button className="btn primary" disabled={busy} onClick={() => void trackChecked()}>
            Track selected {checked.size > 0 ? `(${checked.size})` : ""}
          </button>
          <button className="btn ghost" onClick={refreshDialogs} disabled={busy}>Reload Telegram list</button>
        </>
      }
    >
      <div className="label" style={{ marginTop: 6 }}>Tracked groups</div>
      {groups.length === 0 && <p className="mm-note dim">No groups tracked yet — pick some below.</p>}
      {groups.map((g) => (
        <div key={g.chat_id} className="mm-row">
          <span className="g-ic">{g.kind === "channel" ? "📣" : "👥"}</span>
          <span className="g-main">
            <span className="g-title" dir="auto">{g.title}</span>
            <span className="g-meta">
              {nfmt(g.message_count)} msgs
              {g.last_message ? ` · last ${fmtDate(g.last_message)}` : ""}
            </span>
          </span>
          <span className="row-actions">
            <button
              className={`btn ghost sm ${armed?.id === g.chat_id && armed.mode === "untrack" ? "armed" : ""}`}
              title="Stop archiving this group. Messages are kept on disk and reappear if you track it again."
              onClick={() => arm(g.chat_id, "untrack")}
            >
              {armed?.id === g.chat_id && armed.mode === "untrack"
                ? "keeps msgs — sure?" : "✕ untrack"}
            </button>
            <button
              className={`btn danger sm ${armed?.id === g.chat_id && armed.mode === "delete" ? "armed" : ""}`}
              title="Permanently delete this group's messages from the archive."
              onClick={() => arm(g.chat_id, "delete")}
            >
              {armed?.id === g.chat_id && armed.mode === "delete"
                ? `delete ${nfmt(g.message_count)} msgs — sure?` : "🗑 delete"}
            </button>
          </span>
        </div>
      ))}

      <div className="label" style={{ marginTop: 16 }}>Telegram groups not tracked yet</div>

      {busy && (
        <div className="mm-progress">
          <span className="spinner" />
          <div>
            <div>{listing.state === "waiting" ? listing.note : "Fetching your group list from Telegram…"}</div>
            <pre className="mm-log">{jobs?.log?.split("\n").slice(-4).join("\n") || "(starting…)"}</pre>
            {jobs?.running && (
              <button className="btn danger sm" style={{ marginTop: 8 }}
                onClick={async () => { await api.jobStop(false); toast("Stopping — list loads next", "info"); }}>
                ■ stop current job
              </button>
            )}
          </div>
        </div>
      )}

      {!busy && dialogs === null && (
        <div className="mm-note dim">Loading…</div>
      )}
      {!busy && dialogs !== null && renderOthers()}
    </Modal>
  );
}

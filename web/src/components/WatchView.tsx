/** Watchlists workspace (v0.6): keyword monitors + the alerts inbox.

Watchlists are DETERMINISTIC: matching runs on the same normalized text as
search, right after each sync - the AI provider is never involved, so
monitoring works (and costs nothing) even without one. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { Alert, Watchlist } from "../api/types";
import { fmtDateTime } from "../utils/format";
import { EmptyState } from "./EmptyState";
import { Modal } from "./Modal";

export function WatchView() {
  const { groups, toast } = useStore();
  const [rows, setRows] = useState<Watchlist[] | null>(null);
  const [editing, setEditing] = useState<Watchlist | null>(null);
  const [creating, setCreating] = useState(false);

  const load = async () => {
    try {
      setRows(await api.watchlists());
    } catch (e) {
      toast((e as Error).message, "err");
      setRows([]);
    }
  };
  useEffect(() => { void load(); }, []);

  const checkNow = async (backfill = 0) => {
    try {
      const r = await api.watchCheck(backfill);
      toast(r.matches > 0
        ? `${r.matches} new alert(s) - ${r.unread} unread`
        : "No new matches", r.matches > 0 ? "good" : "info");
      await load();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">Watchlists</h2>
        <span className="dim" style={{ fontSize: 12 }}>
          keyword monitors - no AI required, evaluated after every sync
        </span>
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" title="Evaluate everything above the watermark"
                onClick={() => void checkNow(0)}>Check now</button>
        <button className="btn ghost sm" title="Re-scan recent days for this check only"
                onClick={() => void checkNow(7)}>Check last 7 days</button>
        <button className="btn primary sm" onClick={() => setCreating(true)}>
          + New watchlist
        </button>
      </div>

      <div className="feed">
        {rows === null && <div className="side-note">loading…</div>}
        {rows !== null && rows.length === 0 && (
          <EmptyState icon="👁" title="No watchlists yet"
            hint="Create a keyword watchlist (e.g. kubernetes, عرض,SAVE20) and Telegram Query will alert you when tracked groups mention it - no manual searching, no AI calls." />
        )}
        {rows?.map((w) => (
          <div key={w.id} className="bm-card">
            <div className="bm-head">
              <span className="bm-grp" dir="auto">{w.name}</span>
              {w.unread > 0 && <span className="badge warn">{w.unread} new</span>}
              {!w.enabled && <span className="badge">paused</span>}
              <span className="dim" style={{ fontSize: 12 }} dir="auto">
                {w.terms.join(" · ")}
                {w.exclude_terms.length > 0 && `  (− ${w.exclude_terms.join(", ")})`}
              </span>
              <span style={{ flex: 1 }} />
              <button className="btn ghost sm"
                      onClick={() => void (async () => {
                        try {
                          await api.watchUpdate(w.id, {
                            name: w.name, terms: w.terms,
                            exclude_terms: w.exclude_terms,
                            chat_ids: w.chat_ids, enabled: !w.enabled,
                          });
                          await load();
                        } catch (e) { toast((e as Error).message, "err"); }
                      })()}>
                {w.enabled ? "Pause" : "Resume"}
              </button>
              <button className="btn ghost sm" onClick={() => setEditing(w)}>Edit</button>
              <button className="btn danger sm"
                      onClick={() => void (async () => {
                        try {
                          await api.watchDelete(w.id);
                          toast("Watchlist deleted", "info");
                          await load();
                        } catch (e) { toast((e as Error).message, "err"); }
                      })()}>Delete</button>
            </div>
          </div>
        ))}
      </div>

      {(creating || editing) && (
        <WatchModal w={editing} groups={groups}
                    onClose={() => { setCreating(false); setEditing(null); }}
                    onSaved={() => { setCreating(false); setEditing(null); void load(); }} />
      )}
    </div>
  );
}

function WatchModal({ w, groups, onClose, onSaved }: {
  w: Watchlist | null;
  groups: { chat_id: number; title: string }[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { toast } = useStore();
  const [name, setName] = useState(w?.name ?? "");
  const [terms, setTerms] = useState((w?.terms ?? []).join(", "));
  const [excludes, setExcludes] = useState((w?.exclude_terms ?? []).join(", "));
  const [scope, setScope] = useState<Set<number>>(new Set(w?.chat_ids ?? []));

  const save = async () => {
    const body = {
      name: name.trim(),
      terms: terms.split(",").map((t) => t.trim()).filter(Boolean),
      exclude_terms: excludes.split(",").map((t) => t.trim()).filter(Boolean),
      chat_ids: [...scope],
      enabled: true,
    };
    if (!body.name || body.terms.length === 0) {
      toast("Name and at least one term are required", "err");
      return;
    }
    try {
      if (w) await api.watchUpdate(w.id, body);
      else await api.watchCreate(body);
      toast(w ? "Watchlist updated" : "Watchlist created", "good");
      onSaved();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <Modal title={w ? "Edit watchlist" : "New watchlist"} onClose={onClose}
           footer={
             <>
               <button className="btn ghost sm" onClick={onClose}>Cancel</button>
               <button className="btn primary sm" onClick={() => void save()}>Save</button>
             </>
           }>
      <p className="mm-note dim">
        Terms match like search does (Arabic normalization included). Matching
        is deterministic and runs after each sync - your messages are never
        sent to an AI provider for this.
      </p>
      <label className="field"><span>Name</span>
        <input className="input" value={name} dir="auto" maxLength={100}
               placeholder="e.g. k8s jobs · عروض التقنية"
               onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="field"><span>Terms (comma-separated)</span>
        <input className="input" value={terms} dir="auto"
               placeholder="kubernetes, k8s, وظائف"
               onChange={(e) => setTerms(e.target.value)} />
      </label>
      <label className="field"><span>Exclude terms (optional)</span>
        <input className="input" value={excludes} dir="auto"
               placeholder="pricing"
               onChange={(e) => setExcludes(e.target.value)} />
      </label>
      <div className="field"><span>Groups (empty = all)</span>
        <div className="chips" style={{ marginTop: 4, flexWrap: "wrap" }}>
          {groups.map((g) => (
            <button key={g.chat_id}
                    className={`chip ${scope.has(g.chat_id) ? "on" : ""}`}
                    dir="auto"
                    onClick={() => setScope((s) => {
                      const n = new Set(s);
                      if (n.has(g.chat_id)) n.delete(g.chat_id);
                      else n.add(g.chat_id);
                      return n;
                    })}>
              {g.title}
            </button>
          ))}
        </div>
      </div>
    </Modal>
  );
}

export function AlertsView() {
  const { toast, select, setRightTab, jobs } = useStore();
  const [state, setState] = useState<"new" | "read" | "archived">("new");
  const [rows, setRows] = useState<Alert[] | null>(null);

  const load = async (s = state) => {
    try {
      setRows(await api.alerts({ state: s }));
    } catch (e) {
      toast((e as Error).message, "err");
      setRows([]);
    }
  };
  useEffect(() => { void load(state); }, [state]);

  const lastDone = jobs?.last_done;
  useEffect(() => {
    if (lastDone?.name === "sync") void load(state);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastDone?.finished_at]);

  const act = async (id: number, action: "read" | "archive") => {
    try {
      await api.alertAction(id, action);
      await load();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const jump = (a: Alert) => {
    void (async () => {
      try {
        const m = await api.message(a.chat_id, a.msg_id);
        select(m);
        setRightTab("details");
      } catch {
        toast("Could not open the original message", "err");
      }
    })();
  };

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">Alerts</h2>
        <div className="seg">
          {(["new", "read", "archived"] as const).map((s) => (
            <button key={s} className={state === s ? "on" : ""}
                    onClick={() => setState(s)}>{s}</button>
          ))}
        </div>
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" onClick={() => void load()}>Refresh</button>
      </div>

      <div className="feed">
        {rows === null && <div className="side-note">loading…</div>}
        {rows !== null && rows.length === 0 && (
          <EmptyState icon="🔔" title={`No ${state} alerts`}
            hint={state === "new"
              ? "Watchlist matches land here right after each sync. Nothing new since your last look."
              : "Nothing here yet."} />
        )}
        {rows?.map((a) => (
          <div key={a.id} className={`bm-card ${a.read ? "dim" : ""}`}>
            <div className="bm-head">
              <span className="badge">{a.watchlist_name}</span>
              <span className="bm-grp" dir="auto">{a.chat_title}</span>
              <span className="bm-date">{fmtDateTime(a.date)} UTC</span>
              <span className="bm-sender" dir="auto">{a.sender_name ?? ""}</span>
              <span style={{ flex: 1 }} />
              {!a.read && <button className="btn ghost sm" onClick={() => void act(a.id, "read")}>Mark read</button>}
              {!a.archived && <button className="btn ghost sm" onClick={() => void act(a.id, "archive")}>Archive</button>}
              <button className="btn ghost sm" onClick={() => jump(a)}>Jump</button>
              {a.tg_link && (
                <button className="btn ghost sm"
                        onClick={() => window.open(a.tg_link!, "_blank", "noopener")}>
                  Telegram ↗
                </button>
              )}
            </div>
            <div className="bm-text" dir="auto">{a.text}</div>
            {a.matched_term && (
              <div className="bm-note" dir="auto">matched: “{a.matched_term}”</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

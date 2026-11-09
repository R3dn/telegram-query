/** Decisions workspace (v0.8): extracted decisions & commitments with
 *  filters, citations, human confirm/correct controls, extraction jobs,
 *  and exports.
 *
 *  Every row cites its original messages; sources are verified against the
 *  archive at extraction time - a decision without resolvable sources is
 *  never stored. Status shows evidence-derived states (overdue for past
 *  due dates); confidence shows as an honest qualitative label. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { Decision, DecisionsSettings, DecisionsMonitor } from "../api/types";
import { statusTone } from "../utils/format";
import { EmptyState } from "./EmptyState";
import { Modal } from "./Modal";

const STATUSES = ["proposed", "committed", "completed", "cancelled",
  "overdue", "unverified", "unknown"];
const KINDS = ["decision", "commitment", "plan"];

export function DecisionsView() {
  const { appState, toast, jobs, groups, evidenceFocus, setEvidenceFocus }
    = useStore();
  const [rows, setRows] = useState<Decision[] | null>(null);
  const [settings, setSettings] = useState<DecisionsSettings | null>(null);
  const [monitor, setMonitor] = useState<DecisionsMonitor | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [group, setGroup] = useState("");
  const [sort, setSort] = useState("recent");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [extractOpen, setExtractOpen] = useState(false);

  const load = async () => {
    try {
      const list = await api.decisions({
        q: q || undefined, status: status || undefined,
        kind: kind || undefined, group: group || undefined,
        sort,
      });
      setRows(list);
    } catch (e) {
      toast((e as Error).message, "err");
      setRows([]);
    }
  };

  const loadMonitor = () => {
    api.decisionsMonitor().then(setMonitor).catch(() => { /* ignore */ });
  };

  useEffect(() => {
    const t = setTimeout(() => void load(), q ? 250 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, status, kind, group, sort]);

  useEffect(() => {
    api.decisionsSettings().then(setSettings).catch(() => { /* ignore */ });
    loadMonitor();
  }, []);

  // refresh when the decisions job finishes (any job completion re-checks)
  const lastDone = jobs?.last_done;
  useEffect(() => {
    if (lastDone?.name === "decisions") void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastDone?.finished_at]);

  // Evidence Explorer: arriving with a focus -> expand that decision
  useEffect(() => {
    if (evidenceFocus?.kind === "decision") {
      setExpanded(evidenceFocus.id);
      setEvidenceFocus(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evidenceFocus]);

  const act = async (fn: () => Promise<unknown>, msg: string) => {
    try {
      await fn();
      toast(msg, "good");
      await load();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const checkFollowups = async () => {
    try {
      const s = await api.decisionsCheckFollowups();
      toast(s.new_followups > 0
        ? `Found ${s.new_followups} new follow-up(s)`
        : "No new follow-ups", s.new_followups > 0 ? "good" : "info");
      await load();
      loadMonitor();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const startExtract = async (chatIds: number[], from?: string, to?: string) => {
    try {
      const r = await api.decisionsExtract({
        chat_ids: chatIds, date_from: from || null, date_to: to || null,
      });
      toast(r.started ? "Extraction queued - watch Jobs for progress" : "Extraction already queued", "info");
      setExtractOpen(false);
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const aiOn = appState?.ai_configured;

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">Decisions</h2>
        <input className="input" style={{ maxWidth: 220 }}
               placeholder="Search decisions…" value={q} dir="auto"
               onChange={(e) => setQ(e.target.value)} />
        <select className="input" style={{ maxWidth: 130 }} value={status}
                title="Status filter"
                onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input" style={{ maxWidth: 130 }} value={kind}
                title="Kind filter"
                onChange={(e) => setKind(e.target.value)}>
          <option value="">Any kind</option>
          {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <select className="input" style={{ maxWidth: 150 }} value={group}
                title="Group filter"
                onChange={(e) => setGroup(e.target.value)}>
          <option value="">All groups</option>
          {groups.map((g) => <option key={g.chat_id} value={g.chat_id}>{g.title}</option>)}
        </select>
        <select className="input" style={{ maxWidth: 130 }} value={sort}
                title="Sort" onChange={(e) => setSort(e.target.value)}>
          <option value="recent">Newest</option>
          <option value="due">Due soonest</option>
          <option value="confidence">Most confident</option>
        </select>
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" title="Deterministic keyword check - also runs after every sync"
                onClick={() => void checkFollowups()}>Check follow-ups</button>
        <button className="btn ghost sm" onClick={() => void act(() => api.exportDecisions("md"), "Exported")}>Export .md</button>
        <button className="btn ghost sm" onClick={() => void act(() => api.exportDecisions("json"), "Exported")}>.json</button>
        <button className="btn primary sm" disabled={!aiOn}
                title={aiOn ? "Analyze the archive for decisions and commitments" : "Configure an AI provider first"}
                onClick={() => setExtractOpen(true)}>Extract decisions</button>
      </div>

      {monitor && monitor.open > 0 && (
        <div className="deal-auto-row">
          <span className="dim" style={{ fontSize: 12 }}>
            <b>{monitor.open}</b> open
          </span>
          {monitor.overdue > 0 && (
            <button className="badge err" title="Show overdue decisions"
                    onClick={() => setStatus("overdue")}>
              {monitor.overdue} overdue
            </button>
          )}
          {monitor.due_soon > 0 && (
            <span className="badge warn" title="Due within 7 days">
              {monitor.due_soon} due soon
            </span>
          )}
          {monitor.with_followups > 0 && (
            <span className="badge" title="Decisions with newer messages discussing them">
              {monitor.with_followups} with follow-ups
            </span>
          )}
          <span className="dim" style={{ fontSize: 12 }}>
            follow-up checks run after every sync
          </span>
        </div>
      )}

      {settings && (
        <div className="deal-auto-row">
          <label className="chip static" title="After each sync, analyze only the new messages">
            <input type="checkbox" checked={settings.auto}
                   onChange={(e) => void (async () => {
                     try {
                       const r = await api.decisionsAuto(e.target.checked);
                       setSettings({ ...settings, auto: r.auto });
                       toast(r.auto ? "Auto-extraction on" : "Auto-extraction off", "info");
                     } catch (err) { toast((err as Error).message, "err"); }
                   })()} />
            auto-extract new messages after each sync
          </label>
          <span className="dim" style={{ fontSize: 12 }}>
            extraction sends candidate message excerpts to {appState?.ai_provider_host}
          </span>
        </div>
      )}

      <div className="feed">
        {rows === null && (
          <div className="feed-skeleton">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="skel-msg">
                <div className="skel l1" /><div className="skel l2" /><div className="skel l3" />
              </div>
            ))}
          </div>
        )}
        {rows !== null && rows.length === 0 && (
          <EmptyState
            icon="⚖"
            title={q || status || kind ? "No decisions match" : "No decisions yet"}
            hint={q || status || kind
              ? "Try different filters."
              : aiOn
                ? "Run \"Extract decisions\" to analyze your groups for decisions, commitments, and plans. Extraction only sends candidate messages - never your whole archive."
                : "Configure an AI provider (Settings) to enable extraction, or add decisions manually."}
          />
        )}
        {rows !== null && rows.map((d) => (
          <DecisionCard key={d.id} d={d} open={expanded === d.id}
                        onToggle={() => setExpanded(expanded === d.id ? null : d.id)}
                        onChanged={() => void load()} />
        ))}
      </div>

      {extractOpen && (
        <ExtractModal onClose={() => setExtractOpen(false)}
                      groups={groups} onStart={startExtract} />
      )}
    </div>
  );
}

function DecisionCard({ d, open, onToggle, onChanged }: {
  d: Decision; open: boolean; onToggle: () => void; onChanged: () => void;
}) {
  const { toast } = useStore();
  const [owner, setOwner] = useState(d.owner ?? "");
  const [due, setDue] = useState(d.due_date ?? "");

  const patch = async (p: Record<string, unknown>, msg: string) => {
    try {
      await api.decisionPatch(d.id, p);
      toast(msg, "good");
      onChanged();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className={`deal-card ${open ? "open" : ""}`}>
      <div className="deal-row" onClick={onToggle}>
        <div className="deal-main">
          <div className="deal-title" dir="auto">
            {d.title}
            {d.user_status === "confirmed" && <span className="badge good" style={{ marginInlineStart: 6 }}>✓ confirmed</span>}
            {d.followup_count > 0 && (
              <span className="badge" style={{ marginInlineStart: 6 }}
                    title={`${d.followup_count} newer message(s) discuss this decision`}>
                ⇢ {d.followup_count} follow-up{d.followup_count === 1 ? "" : "s"}
              </span>
            )}
          </div>
          <div className="deal-meta" dir="auto">
            {d.kind && <span className="dim">{d.kind}</span>}
            {d.owner && <span>👤 {d.owner}</span>}
            {d.due_date && <span>↳ {d.due_date}</span>}
            {d.due_soon && <span className="badge warn">due soon</span>}
            <span className="dim">· {d.sources.length} source{d.sources.length === 1 ? "" : "s"}</span>
            <span className="dim">· {d.confidence_label} confidence</span>
          </div>
        </div>
        <span className={`badge ${statusTone(d.derived_status)}`}>{d.derived_status}</span>
      </div>

      {open && (
        <div className="deal-detail">
          {d.detail && <p className="deal-desc" dir="auto">{d.detail}</p>}
          <div className="deal-sources">
            <span className="label">Sources ({d.sources.length})</span>
            {d.sources.map((s, i) => (
              <div key={i} className="src-row" dir="auto">
                <span className="src-title">{s.chat_title ?? "?"}</span>
                <span className="src-date">{(s.date ?? "").slice(0, 10)}</span>
                <span className="src-text">{(s.text ?? "[deleted from archive]").slice(0, 120)}</span>
                {s.tg_link && (
                  <button className="link" onClick={() => window.open(s.tg_link!, "_blank", "noopener")}>
                    Telegram ↗
                  </button>
                )}
              </div>
            ))}
          </div>
          {d.followups.length > 0 && (
            <div className="deal-sources">
              <span className="label">
                Follow-ups ({d.followup_count}) — newer messages about this
                decision
              </span>
              {d.followups.map((f, i) => (
                <div key={`fu${i}`} className="src-row" dir="auto">
                  <span className="src-title">{f.chat_title ?? "?"}</span>
                  <span className="src-date">{(f.date ?? "").slice(0, 10)}</span>
                  <span className="src-text">{(f.text ?? "[deleted from archive]").slice(0, 120)}</span>
                  {f.tg_link && (
                    <button className="link" onClick={() => window.open(f.tg_link!, "_blank", "noopener")}>
                      Telegram ↗
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
          <div className="deal-actions">
            {d.user_status !== "confirmed" && (
              <button className="btn primary sm"
                      onClick={() => void patch({ user_status: "confirmed" }, "Confirmed ✓")}>
                ✓ Confirm
              </button>
            )}
            <button className="btn ghost sm"
                    onClick={() => void patch({ user_status: "dismissed" }, "Dismissed")}>
              Dismiss
            </button>
            {d.status !== "completed" && (
              <button className="btn ghost sm"
                      onClick={() => void patch({ status: "completed" }, "Marked completed")}>
                Mark completed
              </button>
            )}
            <span className="date-range" title="Correct the owner">
              <input className="input" style={{ width: 130 }} dir="auto"
                     placeholder="Owner…" value={owner}
                     onChange={(e) => setOwner(e.target.value)} />
              <button className="btn ghost sm"
                      onClick={() => void patch({ owner: owner || null }, "Owner updated")}>
                Save owner
              </button>
            </span>
            <span className="date-range" title="Correct the due date">
              <input type="date" className="input" style={{ width: 140 }}
                     value={due}
                     onChange={(e) => setDue(e.target.value)} />
              <button className="btn ghost sm"
                      onClick={() => void patch({ due_date: due || null }, "Due date updated")}>
                Save due date
              </button>
            </span>
            <span style={{ flex: 1 }} />
            <button className="btn danger sm"
                    onClick={() => void (async () => {
                      try {
                        await api.decisionDelete(d.id);
                        toast("Decision deleted", "info");
                        onChanged();
                      } catch (e) { toast((e as Error).message, "err"); }
                    })()}>
              Delete
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ExtractModal({ onClose, groups, onStart }: {
  onClose: () => void;
  groups: { chat_id: number; title: string }[];
  onStart: (chatIds: number[], from?: string, to?: string) => void;
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  return (
    <Modal title="Extract decisions" onClose={onClose}
           footer={
             <>
               <button className="btn ghost sm" onClick={onClose}>Cancel</button>
               <button className="btn primary sm"
                       onClick={() => onStart([...selected], from || undefined, to || undefined)}>
                 Start extraction
               </button>
             </>
           }>
      <p className="mm-note dim">
        Analyzes messages that match decision/commitment keywords inside the
        selected scope, then sends only those candidates (in batches) to your
        AI provider. Existing decisions are merged by identity - never
        duplicated. The job and its progress are visible in Jobs.
      </p>
      <div className="label">Scope</div>
      <div className="chips" style={{ margin: "6px 0 10px" }}>
        {groups.map((g) => (
          <button key={g.chat_id}
                  className={`chip ${selected.has(g.chat_id) ? "on" : ""}`}
                  dir="auto"
                  onClick={() => setSelected((s) => {
                    const n = new Set(s);
                    if (n.has(g.chat_id)) n.delete(g.chat_id); else n.add(g.chat_id);
                    return n;
                  })}>
            {g.title}
          </button>
        ))}
        {groups.length === 0 && <span className="dim">No tracked groups yet.</span>}
      </div>
      <div className="label">Date range (optional)</div>
      <div className="date-range" style={{ marginTop: 6 }}>
        <input type="date" className="input" style={{ width: 140 }} value={from}
               onChange={(e) => setFrom(e.target.value)} />
        <span>→</span>
        <input type="date" className="input" style={{ width: 140 }} value={to}
               onChange={(e) => setTo(e.target.value)} />
      </div>
    </Modal>
  );
}

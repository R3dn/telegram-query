/** Deals workspace (v0.5): extracted offers with filters, citations,
 *  human confirm/correct controls, extraction jobs, and exports.
 *
 *  Every row cites its original messages; sources are verified against the
 *  archive at extraction time - a deal without resolvable sources is never
 *  stored. Confidence shows as an honest qualitative label. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { Deal, DealsSettings } from "../api/types";
import { statusTone } from "../utils/format";
import { EmptyState } from "./EmptyState";
import { Modal } from "./Modal";

const STATUSES = ["active", "upcoming", "expired", "unverified", "unknown"];

export function DealsView() {
  const { appState, toast, jobs, groups, evidenceFocus, setEvidenceFocus } = useStore();
  const [rows, setRows] = useState<Deal[] | null>(null);
  const [settings, setSettings] = useState<DealsSettings | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [group, setGroup] = useState("");
  const [sort, setSort] = useState("recent");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [extractOpen, setExtractOpen] = useState(false);

  // Evidence Explorer: arriving with a focus -> expand that deal
  useEffect(() => {
    if (evidenceFocus?.kind === "deal") {
      setExpanded(evidenceFocus.id);
      setEvidenceFocus(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evidenceFocus]);

  const load = async () => {
    try {
      const list = await api.deals({
        q: q || undefined, status: status || undefined,
        category: category || undefined, group: group || undefined,
        sort,
      });
      setRows(list);
    } catch (e) {
      toast((e as Error).message, "err");
      setRows([]);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => void load(), q ? 250 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, status, category, group, sort]);

  useEffect(() => {
    api.dealsSettings().then(setSettings).catch(() => { /* ignore */ });
  }, []);

  // refresh when the extract job finishes (any job completion re-checks)
  const lastDone = jobs?.last_done;
  useEffect(() => {
    if (lastDone?.name === "extract") void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastDone?.finished_at]);

  const act = async (fn: () => Promise<unknown>, msg: string) => {
    try {
      await fn();
      toast(msg, "good");
      await load();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const startExtract = async (chatIds: number[], from?: string, to?: string) => {
    try {
      const r = await api.dealsExtract({
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
        <h2 className="bm-title">Deals</h2>
        <input className="input" style={{ maxWidth: 220 }}
               placeholder="Search deals…" value={q} dir="auto"
               onChange={(e) => setQ(e.target.value)} />
        <select className="input" style={{ maxWidth: 130 }} value={status}
                title="Status filter"
                onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input" style={{ maxWidth: 130 }} value={category}
                title="Category filter"
                onChange={(e) => setCategory(e.target.value)}>
          <option value="">Any category</option>
          {(settings?.categories ?? []).map((c) =>
            <option key={c} value={c}>{c}</option>)}
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
          <option value="discount">Biggest discount</option>
          <option value="price">Lowest price</option>
        </select>
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" onClick={() => void act(() => api.exportDeals("md"), "Exported")}>Export .md</button>
        <button className="btn ghost sm" onClick={() => void act(() => api.exportDeals("json"), "Exported")}>.json</button>
        <button className="btn primary sm" disabled={!aiOn}
                title={aiOn ? "Analyze the archive for offers" : "Configure an AI provider first"}
                onClick={() => setExtractOpen(true)}>Extract deals</button>
      </div>

      {settings && (
        <div className="deal-auto-row">
          <label className="chip static" title="After each sync, analyze only the new messages">
            <input type="checkbox" checked={settings.auto}
                   onChange={(e) => void (async () => {
                     try {
                       const r = await api.dealsAuto(e.target.checked);
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
            icon="🏷"
            title={q || status || category ? "No deals match" : "No deals yet"}
            hint={q || status || category
              ? "Try different filters."
              : aiOn
                ? "Run \"Extract deals\" to analyze your groups for offers, or add one manually. Extraction only sends candidate messages - never your whole archive."
                : "Configure an AI provider (Settings) to enable extraction, or add deals manually."}
          />
        )}
        {rows !== null && rows.map((d) => (
          <DealCard key={d.id} d={d} open={expanded === d.id}
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

function DealCard({ d, open, onToggle, onChanged }: {
  d: Deal; open: boolean; onToggle: () => void; onChanged: () => void;
}) {
  const { toast } = useStore();
  const [expires, setExpires] = useState(d.expires ?? "");

  const patch = async (p: Record<string, unknown>, msg: string) => {
    try {
      await api.dealPatch(d.id, p);
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
          </div>
          <div className="deal-meta" dir="auto">
            {d.vendor && <span>{d.vendor}</span>}
            {d.promo_code && <span className="code-chip">{d.promo_code}</span>}
            {d.discount_pct != null && <span>−{d.discount_pct}%</span>}
            {d.price != null && <span>{d.price} {d.currency ?? ""}</span>}
            {d.expires && <span>↳ {d.expires}</span>}
            <span className="dim">· {d.sources.length} source{d.sources.length === 1 ? "" : "s"}</span>
            <span className="dim">· {d.confidence_label} confidence</span>
          </div>
        </div>
        <span className={`badge ${statusTone(d.derived_status)}`}>{d.derived_status}</span>
      </div>

      {open && (
        <div className="deal-detail">
          {d.description && <p className="deal-desc" dir="auto">{d.description}</p>}
          {(d.eligibility || d.geo || d.valid_from) && (
            <div className="deal-meta dim" dir="auto">
              {d.eligibility && <span>who: {d.eligibility}</span>}
              {d.geo && <span>where: {d.geo}</span>}
              {d.valid_from && <span>from: {d.valid_from}</span>}
            </div>
          )}
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
            <span className="date-range" title="Correct the expiry date">
              <input type="date" className="input" style={{ width: 140 }}
                     value={expires}
                     onChange={(e) => setExpires(e.target.value)} />
              <button className="btn ghost sm"
                      onClick={() => void patch({ expires: expires || null }, "Expiry updated")}>
                Save expiry
              </button>
            </span>
            <span style={{ flex: 1 }} />
            <button className="btn danger sm"
                    onClick={() => void (async () => {
                      try {
                        await api.dealDelete(d.id);
                        toast("Deal deleted", "info");
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
    <Modal title="Extract deals" onClose={onClose}
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
        Analyzes messages that match deal keywords inside the selected scope,
        then sends only those candidates (in batches) to your AI provider.
        Existing deals are merged by identity - never duplicated. The job and
        its progress are visible in Jobs.
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

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
import { useLang } from "../i18n";
import type { Decision, DecisionsSettings, DecisionsMonitor } from "../api/types";
import { statusTone } from "../utils/format";
import { Ic } from "../design/icons";
import { EmptyState } from "./EmptyState";
import { Modal } from "./Modal";

const STATUSES = ["proposed", "committed", "completed", "cancelled",
  "overdue", "unverified", "unknown"];
const KINDS = ["decision", "commitment", "plan"];

type T = ReturnType<typeof useLang>["t"];

export function DecisionsView() {
  const { appState, toast, jobs, groups, evidenceFocus, setEvidenceFocus }
    = useStore();
  const { t } = useLang();
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
        ? t("decisions.followupsFound", { n: s.new_followups })
        : t("decisions.noNewFollowups"), s.new_followups > 0 ? "good" : "info");
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
      toast(r.started ? t("decisions.extractQueued") : t("decisions.extractAlreadyQueued"),
            "info");
      setExtractOpen(false);
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const aiOn = appState?.ai_configured;

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">{t("nav.decisions")}</h2>
        <input className="input" style={{ maxWidth: 220 }}
               placeholder={t("decisions.searchPlaceholder")} value={q} dir="auto"
               onChange={(e) => setQ(e.target.value)} />
        <select className="input" style={{ maxWidth: 130 }} value={status}
                title={t("decisions.filterStatus")}
                onChange={(e) => setStatus(e.target.value)}>
          <option value="">{t("decisions.anyStatus")}</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input" style={{ maxWidth: 130 }} value={kind}
                title={t("decisions.filterKind")}
                onChange={(e) => setKind(e.target.value)}>
          <option value="">{t("decisions.anyKind")}</option>
          {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <select className="input" style={{ maxWidth: 150 }} value={group}
                title={t("decisions.filterGroup")}
                onChange={(e) => setGroup(e.target.value)}>
          <option value="">{t("filter.allGroups")}</option>
          {groups.map((g) => <option key={g.chat_id} value={g.chat_id}>{g.title}</option>)}
        </select>
        <select className="input" style={{ maxWidth: 130 }} value={sort}
                title={t("decisions.sort")} onChange={(e) => setSort(e.target.value)}>
          <option value="recent">{t("filter.newestFirst")}</option>
          <option value="due">{t("decisions.sortDue")}</option>
          <option value="confidence">{t("decisions.sortConfidence")}</option>
        </select>
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" title={t("decisions.checkFollowupsHint")}
                onClick={() => void checkFollowups()}>
          <Ic.RefreshCw size={13} /> {t("decisions.checkFollowups")}
        </button>
        <button className="btn ghost sm"
                onClick={() => void act(() => api.exportDecisions("md"), t("decisions.exported"))}>
          <Ic.FileDown size={13} /> {t("decisions.exportMd")}
        </button>
        <button className="btn ghost sm"
                onClick={() => void act(() => api.exportDecisions("json"), t("decisions.exported"))}>
          <Ic.FileDown size={13} /> {t("decisions.exportJson")}
        </button>
        <button className="btn primary sm" disabled={!aiOn}
                title={aiOn ? t("decisions.extractHint") : t("decisions.aiNeeded")}
                onClick={() => setExtractOpen(true)}>
          <Ic.Sparkles size={13} /> {t("decisions.extract")}
        </button>
      </div>

      {monitor && monitor.open > 0 && (
        <div className="deal-auto-row">
          <span className="dim" style={{ fontSize: 12 }}>
            <b>{monitor.open}</b> {t("decisions.openLabel")}
          </span>
          {monitor.overdue > 0 && (
            <button className="badge err" title={t("decisions.showOverdue")}
                    onClick={() => setStatus("overdue")}>
              <Ic.CircleAlert size={10} /> {t("decisions.nOverdue", { n: monitor.overdue })}
            </button>
          )}
          {monitor.due_soon > 0 && (
            <span className="badge warn" title={t("decisions.dueSoonHint")}>
              <Ic.Clock size={10} /> {t("decisions.nDueSoon", { n: monitor.due_soon })}
            </span>
          )}
          {monitor.with_followups > 0 && (
            <span className="badge" title={t("decisions.followupsHint")}>
              <Ic.MessageSquare size={10} />
              {t("decisions.nWithFollowups", { n: monitor.with_followups })}
            </span>
          )}
          <span className="dim" style={{ fontSize: 12 }}>
            {t("decisions.followupsNote")}
          </span>
        </div>
      )}

      {settings && (
        <div className="deal-auto-row">
          <label className="chip static" title={t("decisions.autoHint")}>
            <input type="checkbox" checked={settings.auto}
                   onChange={(e) => void (async () => {
                     try {
                       const r = await api.decisionsAuto(e.target.checked);
                       setSettings({ ...settings, auto: r.auto });
                       toast(r.auto ? t("decisions.autoOn") : t("decisions.autoOff"), "info");
                     } catch (err) { toast((err as Error).message, "err"); }
                   })()} />
            {t("decisions.autoLabel")}
          </label>
          <span className="dim" style={{ fontSize: 12 }}>
            {t("decisions.autoNote", { host: appState?.ai_provider_host ?? "" })}
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
            icon="Scale"
            title={q || status || kind ? t("decisions.noMatch") : t("decisions.empty")}
            hint={q || status || kind
              ? t("decisions.tryDifferent")
              : aiOn
                ? t("decisions.emptyAiHint")
                : t("decisions.emptyNoAiHint")}
          />
        )}
        {rows !== null && rows.map((d) => (
          <DecisionCard key={d.id} d={d} open={expanded === d.id} t={t}
                        onToggle={() => setExpanded(expanded === d.id ? null : d.id)}
                        onChanged={() => void load()} />
        ))}
      </div>

      {extractOpen && (
        <ExtractModal onClose={() => setExtractOpen(false)} t={t}
                      groups={groups} onStart={startExtract} />
      )}
    </div>
  );
}

function DecisionCard({ d, open, onToggle, onChanged, t }: {
  d: Decision; open: boolean; onToggle: () => void; onChanged: () => void;
  t: T;
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
            {d.user_status === "confirmed" && (
              <span className="badge good" style={{ marginInlineStart: 6 }}>
                <Ic.Check size={10} /> {t("decisions.badgeConfirmed")}
              </span>
            )}
            {d.followup_count > 0 && (
              <span className="badge" style={{ marginInlineStart: 6 }}
                    title={t("decisions.followupsTitle", { n: d.followup_count })}>
                <Ic.MessageSquare size={10} /> {t(d.followup_count === 1
                  ? "decisions.followupOne" : "decisions.followupMany",
                  { n: d.followup_count })}
              </span>
            )}
          </div>
          <div className="deal-meta" dir="auto">
            {d.kind && <span className="dim">{d.kind}</span>}
            {d.owner && (
              <span className="meta-ic">
                <Ic.User size={11} /> {d.owner}
              </span>
            )}
            {d.due_date && (
              <span className="meta-ic">
                <Ic.CornerUpLeft size={11} /> {d.due_date}
              </span>
            )}
            {d.due_soon && <span className="badge warn">{t("decisions.dueSoon")}</span>}
            <span className="dim">
              · {t(d.sources.length === 1 ? "decisions.sourceOne" : "decisions.sourceMany",
                    { n: d.sources.length })}
            </span>
            <span className="dim">
              · {t("decisions.confidence", { label: d.confidence_label })}
            </span>
          </div>
        </div>
        <span className={`badge ${statusTone(d.derived_status)}`}>{d.derived_status}</span>
        <span className="row-chev"><Ic.ChevronDown size={14} /></span>
      </div>

      {open && (
        <div className="deal-detail">
          {d.detail && <p className="deal-desc" dir="auto">{d.detail}</p>}
          <div className="deal-sources">
            <span className="label">{t("decisions.sourcesLabel", { n: d.sources.length })}</span>
            {d.sources.map((s, i) => (
              <div key={i} className="src-row" dir="auto">
                <span className="src-title">{s.chat_title ?? "?"}</span>
                <span className="src-date">{(s.date ?? "").slice(0, 10)}</span>
                <span className="src-text">
                  {(s.text ?? t("decisions.deletedFromArchive")).slice(0, 120)}
                </span>
                {s.tg_link && (
                  <button className="link"
                          onClick={() => window.open(s.tg_link!, "_blank", "noopener")}>
                    <Ic.ExternalLink size={11} /> {t("action.openTelegram")}
                  </button>
                )}
              </div>
            ))}
          </div>
          {d.followups.length > 0 && (
            <div className="deal-sources">
              <span className="label">
                {t("decisions.followupsLabel", { n: d.followup_count })}
              </span>
              {d.followups.map((f, i) => (
                <div key={`fu${i}`} className="src-row" dir="auto">
                  <span className="src-title">{f.chat_title ?? "?"}</span>
                  <span className="src-date">{(f.date ?? "").slice(0, 10)}</span>
                  <span className="src-text">
                    {(f.text ?? t("decisions.deletedFromArchive")).slice(0, 120)}
                  </span>
                  {f.tg_link && (
                    <button className="link"
                            onClick={() => window.open(f.tg_link!, "_blank", "noopener")}>
                      <Ic.ExternalLink size={11} /> {t("action.openTelegram")}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
          <div className="deal-actions">
            {d.user_status !== "confirmed" && (
              <button className="btn primary sm"
                      onClick={() => void patch({ user_status: "confirmed" }, t("decisions.confirmed"))}>
                <Ic.Check size={13} /> {t("action.confirm")}
              </button>
            )}
            <button className="btn ghost sm"
                    onClick={() => void patch({ user_status: "dismissed" }, t("decisions.dismissed"))}>
              {t("decisions.dismiss")}
            </button>
            {d.status !== "completed" && (
              <button className="btn ghost sm"
                      onClick={() => void patch({ status: "completed" }, t("decisions.markedCompleted"))}>
                <Ic.CircleCheck size={13} /> {t("decisions.markCompleted")}
              </button>
            )}
            <span className="date-range" title={t("decisions.correctOwner")}>
              <input className="input" style={{ width: 130 }} dir="auto"
                     placeholder={t("decisions.ownerPlaceholder")} value={owner}
                     onChange={(e) => setOwner(e.target.value)} />
              <button className="btn ghost sm"
                      onClick={() => void patch({ owner: owner || null }, t("decisions.ownerUpdated"))}>
                <Ic.Save size={13} /> {t("decisions.saveOwner")}
              </button>
            </span>
            <span className="date-range" title={t("decisions.correctDue")}>
              <input type="date" className="input" style={{ width: 140 }}
                     value={due}
                     onChange={(e) => setDue(e.target.value)} />
              <button className="btn ghost sm"
                      onClick={() => void patch({ due_date: due || null }, t("decisions.dueUpdated"))}>
                <Ic.Save size={13} /> {t("decisions.saveDue")}
              </button>
            </span>
            <span style={{ flex: 1 }} />
            <button className="btn danger sm"
                    onClick={() => void (async () => {
                      try {
                        await api.decisionDelete(d.id);
                        toast(t("decisions.deleted"), "info");
                        onChanged();
                      } catch (e) { toast((e as Error).message, "err"); }
                    })()}>
              <Ic.Trash size={13} /> {t("action.delete")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ExtractModal({ onClose, groups, onStart, t }: {
  onClose: () => void;
  groups: { chat_id: number; title: string }[];
  onStart: (chatIds: number[], from?: string, to?: string) => void;
  t: T;
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  return (
    <Modal title={t("decisions.extract")} onClose={onClose}
           footer={
             <>
               <button className="btn ghost sm" onClick={onClose}>{t("action.cancel")}</button>
               <button className="btn primary sm"
                       onClick={() => onStart([...selected], from || undefined, to || undefined)}>
                 <Ic.Play size={13} /> {t("decisions.startExtract")}
               </button>
             </>
           }>
      <p className="mm-note dim">{t("decisions.extractNote")}</p>
      <div className="label">{t("decisions.scope")}</div>
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
        {groups.length === 0 && <span className="dim">{t("decisions.noGroups")}</span>}
      </div>
      <div className="label">{t("decisions.dateRange")}</div>
      <div className="date-range" style={{ marginTop: 6 }}>
        <input type="date" className="input" style={{ width: 140 }} value={from}
               onChange={(e) => setFrom(e.target.value)} />
        <span><Ic.ArrowRight size={13} /></span>
        <input type="date" className="input" style={{ width: 140 }} value={to}
               onChange={(e) => setTo(e.target.value)} />
      </div>
    </Modal>
  );
}

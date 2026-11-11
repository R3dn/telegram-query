/** Deals workspace (v0.5): extracted offers with filters, citations,
 *  human confirm/correct controls, extraction jobs, and exports.
 *
 *  Every row cites its original messages; sources are verified against the
 *  archive at extraction time - a deal without resolvable sources is never
 *  stored. Confidence shows as an honest qualitative label. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { Deal, DealsSettings } from "../api/types";
import { statusTone } from "../utils/format";
import { Ic } from "../design/icons";
import { EmptyState } from "./EmptyState";
import { Modal } from "./Modal";

const STATUSES = ["active", "upcoming", "expired", "unverified", "unknown"];

type T = ReturnType<typeof useLang>["t"];

export function DealsView() {
  const { appState, toast, jobs, groups, evidenceFocus, setEvidenceFocus } = useStore();
  const { t } = useLang();
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
      toast(r.started ? t("deals.extractQueued") : t("deals.extractAlreadyQueued"),
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
        <h2 className="bm-title">{t("nav.deals")}</h2>
        <input className="input" style={{ maxWidth: 220 }}
               placeholder={t("deals.searchPlaceholder")} value={q} dir="auto"
               onChange={(e) => setQ(e.target.value)} />
        <select className="input" style={{ maxWidth: 130 }} value={status}
                title={t("deals.filterStatus")}
                onChange={(e) => setStatus(e.target.value)}>
          <option value="">{t("deals.anyStatus")}</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input" style={{ maxWidth: 130 }} value={category}
                title={t("deals.filterCategory")}
                onChange={(e) => setCategory(e.target.value)}>
          <option value="">{t("deals.anyCategory")}</option>
          {(settings?.categories ?? []).map((c) =>
            <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="input" style={{ maxWidth: 150 }} value={group}
                title={t("deals.filterGroup")}
                onChange={(e) => setGroup(e.target.value)}>
          <option value="">{t("filter.allGroups")}</option>
          {groups.map((g) => <option key={g.chat_id} value={g.chat_id}>{g.title}</option>)}
        </select>
        <select className="input" style={{ maxWidth: 130 }} value={sort}
                title={t("deals.sort")} onChange={(e) => setSort(e.target.value)}>
          <option value="recent">{t("filter.newestFirst")}</option>
          <option value="discount">{t("deals.sortDiscount")}</option>
          <option value="price">{t("deals.sortPrice")}</option>
        </select>
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm"
                onClick={() => void act(() => api.exportDeals("md"), t("deals.exported"))}>
          <Ic.FileDown size={13} /> {t("deals.exportMd")}
        </button>
        <button className="btn ghost sm"
                onClick={() => void act(() => api.exportDeals("json"), t("deals.exported"))}>
          <Ic.FileDown size={13} /> {t("deals.exportJson")}
        </button>
        <button className="btn primary sm" disabled={!aiOn}
                title={aiOn ? t("deals.extractHint") : t("deals.aiNeeded")}
                onClick={() => setExtractOpen(true)}>
          <Ic.Sparkles size={13} /> {t("deals.extract")}
        </button>
      </div>

      {settings && (
        <div className="deal-auto-row">
          <label className="chip static" title={t("deals.autoHint")}>
            <input type="checkbox" checked={settings.auto}
                   onChange={(e) => void (async () => {
                     try {
                       const r = await api.dealsAuto(e.target.checked);
                       setSettings({ ...settings, auto: r.auto });
                       toast(r.auto ? t("deals.autoOn") : t("deals.autoOff"), "info");
                     } catch (err) { toast((err as Error).message, "err"); }
                   })()} />
            {t("deals.autoLabel")}
          </label>
          <span className="dim" style={{ fontSize: 12 }}>
            {t("deals.autoNote", { host: appState?.ai_provider_host ?? "" })}
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
            icon="Tag"
            title={q || status || category ? t("deals.noMatch") : t("deals.empty")}
            hint={q || status || category
              ? t("deals.tryDifferent")
              : aiOn
                ? t("deals.emptyAiHint")
                : t("deals.emptyNoAiHint")}
          />
        )}
        {rows !== null && rows.map((d) => (
          <DealCard key={d.id} d={d} open={expanded === d.id} t={t}
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

function DealCard({ d, open, onToggle, onChanged, t }: {
  d: Deal; open: boolean; onToggle: () => void; onChanged: () => void;
  t: T;
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
            {d.user_status === "confirmed" && (
              <span className="badge good" style={{ marginInlineStart: 6 }}>
                <Ic.Check size={10} /> {t("deals.badgeConfirmed")}
              </span>
            )}
          </div>
          <div className="deal-meta" dir="auto">
            {d.vendor && <span>{d.vendor}</span>}
            {d.promo_code && <span className="code-chip">{d.promo_code}</span>}
            {d.discount_pct != null && <span>−{d.discount_pct}%</span>}
            {d.price != null && <span>{d.price} {d.currency ?? ""}</span>}
            {d.expires && (
              <span className="meta-ic">
                <Ic.CornerUpLeft size={11} /> {d.expires}
              </span>
            )}
            <span className="dim">
              · {t(d.sources.length === 1 ? "deals.sourceOne" : "deals.sourceMany",
                    { n: d.sources.length })}
            </span>
            <span className="dim">
              · {t("deals.confidence", { label: d.confidence_label })}
            </span>
          </div>
        </div>
        <span className={`badge ${statusTone(d.derived_status)}`}>{d.derived_status}</span>
        <span className="row-chev"><Ic.ChevronDown size={14} /></span>
      </div>

      {open && (
        <div className="deal-detail">
          {d.description && <p className="deal-desc" dir="auto">{d.description}</p>}
          {(d.eligibility || d.geo || d.valid_from) && (
            <div className="deal-meta dim" dir="auto">
              {d.eligibility && <span>{t("deals.who", { v: d.eligibility })}</span>}
              {d.geo && <span>{t("deals.where", { v: d.geo })}</span>}
              {d.valid_from && <span>{t("deals.from", { v: d.valid_from })}</span>}
            </div>
          )}
          <div className="deal-sources">
            <span className="label">{t("deals.sourcesLabel", { n: d.sources.length })}</span>
            {d.sources.map((s, i) => (
              <div key={i} className="src-row" dir="auto">
                <span className="src-title">{s.chat_title ?? "?"}</span>
                <span className="src-date">{(s.date ?? "").slice(0, 10)}</span>
                <span className="src-text">
                  {(s.text ?? t("deals.deletedFromArchive")).slice(0, 120)}
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
          <div className="deal-actions">
            {d.user_status !== "confirmed" && (
              <button className="btn primary sm"
                      onClick={() => void patch({ user_status: "confirmed" }, t("deals.confirmed"))}>
                <Ic.Check size={13} /> {t("action.confirm")}
              </button>
            )}
            <button className="btn ghost sm"
                    onClick={() => void patch({ user_status: "dismissed" }, t("deals.dismissed"))}>
              {t("deals.dismiss")}
            </button>
            <span className="date-range" title={t("deals.correctExpiry")}>
              <input type="date" className="input" style={{ width: 140 }}
                     value={expires}
                     onChange={(e) => setExpires(e.target.value)} />
              <button className="btn ghost sm"
                      onClick={() => void patch({ expires: expires || null }, t("deals.expiryUpdated"))}>
                <Ic.Save size={13} /> {t("deals.saveExpiry")}
              </button>
            </span>
            <span style={{ flex: 1 }} />
            <button className="btn danger sm"
                    onClick={() => void (async () => {
                      try {
                        await api.dealDelete(d.id);
                        toast(t("deals.deleted"), "info");
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
    <Modal title={t("deals.extract")} onClose={onClose}
           footer={
             <>
               <button className="btn ghost sm" onClick={onClose}>{t("action.cancel")}</button>
               <button className="btn primary sm"
                       onClick={() => onStart([...selected], from || undefined, to || undefined)}>
                 <Ic.Play size={13} /> {t("deals.startExtract")}
               </button>
             </>
           }>
      <p className="mm-note dim">{t("deals.extractNote")}</p>
      <div className="label">{t("deals.scope")}</div>
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
        {groups.length === 0 && <span className="dim">{t("deals.noGroups")}</span>}
      </div>
      <div className="label">{t("deals.dateRange")}</div>
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

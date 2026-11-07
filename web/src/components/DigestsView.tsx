/** Digests workspace (v0.6): scheduled + on-demand cited summaries.

Every factual item in a digest cites archived messages; empty sections are
dropped by prompt contract and unresolvable citations are stripped on the
backend. Unchanged periods are never re-sent to the provider. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { Digest, DigestSchedule } from "../api/types";
import { mdToHtml } from "../utils/markdown";
import { EmptyState } from "./EmptyState";
import { Modal } from "./Modal";

export function DigestsView() {
  const { groups, toast, appState, jobs, selection, toggleGroup } = useStore();
  const [schedules, setSchedules] = useState<DigestSchedule[]>([]);
  const [digests, setDigests] = useState<Digest[] | null>(null);
  const [open, setOpen] = useState<Digest | null>(null);
  const [schedOpen, setSchedOpen] = useState(false);

  const load = async () => {
    try {
      const [s, d] = await Promise.all([
        api.digestSchedules(), api.digests(),
      ]);
      setSchedules(s);
      setDigests(d);
    } catch (e) {
      toast((e as Error).message, "err");
      setDigests([]);
    }
  };
  useEffect(() => { void load(); }, []);

  const lastDone = jobs?.last_done;
  useEffect(() => {
    if (lastDone?.name === "digest") void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastDone?.finished_at]);

  const generate = async (frequency: "daily" | "weekly") => {
    try {
      const r = await api.digestGenerate({
        chat_ids: [...selection], frequency, language: "auto",
      });
      toast(r.started
        ? "Digest generation queued - watch Jobs"
        : "A digest job is already queued", "info");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const openDigest = async (id: number) => {
    try {
      setOpen(await api.digestGet(id));
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const aiOn = appState?.ai_configured;

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">Digests</h2>
        <span className="dim" style={{ fontSize: 12 }}>
          every item cites its sources; unchanged periods are never re-analyzed
        </span>
        <span style={{ flex: 1 }} />
        <select className="input" style={{ maxWidth: 190 }} value=""
                title="New schedule"
                onChange={(e) => { if (e.target.value) setSchedOpen(true); }}>
          <option value="">+ New schedule…</option>
          <option value="daily">Daily digest</option>
          <option value="weekly">Weekly digest</option>
        </select>
        <button className="btn ghost sm" disabled={!aiOn}
                title={aiOn ? "Summarize the last 24h" : "Configure an AI provider first"}
                onClick={() => void generate("daily")}>Digest last day</button>
        <button className="btn ghost sm" disabled={!aiOn}
                title={aiOn ? "Summarize the last 7 days" : "Configure an AI provider first"}
                onClick={() => void generate("weekly")}>Digest last week</button>
      </div>

      <div className="digest-groups">
        <span className="label">On-demand scope (groups):</span>
        <div className="chips" style={{ flexWrap: "wrap" }}>
          {groups.map((g) => (
            <button key={g.chat_id}
                    className={`chip ${selection.has(g.chat_id) ? "on" : ""}`}
                    dir="auto" onClick={() => toggleGroup(g.chat_id)}>
              {g.title.length > 18 ? g.title.slice(0, 18) + "…" : g.title}
            </button>
          ))}
        </div>
      </div>

      {schedules.length > 0 && (
        <div className="bm-bar" style={{ borderBottom: "none", paddingBottom: 0 }}>
          <span className="label">Schedules</span>
        </div>
      )}
      {schedules.map((s) => (
        <div key={s.id} className="bm-card" style={{ margin: "6px 18px" }}>
          <div className="bm-head">
            <span className="badge">{s.frequency === "daily" ? "every day" : "weekly"}</span>
            <span className="dim" style={{ fontSize: 12 }}>
              at {String(s.hour).padStart(2, "0")}:00 UTC ·{" "}
              {s.chat_ids.length ? `${s.chat_ids.length} group(s)` : "all groups"}
              {s.last_run && ` · last: ${s.last_run.slice(0, 10)}`}
            </span>
            <span style={{ flex: 1 }} />
            <button className="btn danger sm"
                    onClick={() => void (async () => {
                      try {
                        await api.digestScheduleDelete(s.id);
                        toast("Schedule deleted", "info");
                        await load();
                      } catch (e) { toast((e as Error).message, "err"); }
                    })()}>Delete</button>
          </div>
        </div>
      ))}

      <div className="feed">
        {digests === null && <div className="side-note">loading…</div>}
        {digests !== null && digests.length === 0 && !open && (
          <EmptyState icon="📰" title="No digests yet"
            hint={aiOn
              ? "Generate one on demand (last day / last week) or create a schedule - digests run automatically and are archived with their citations."
              : "Configure an AI provider (Settings) to enable digests."} />
        )}
        {open ? (
          <div className="brief-detail" style={{ margin: "8px 18px" }}>
            <div className="brief-head">
              <div className="brief-meta">
                <span className="badge">
                  {open.period_start.slice(0, 10)} → {open.period_end.slice(0, 10)}
                </span>
                <span className="dim">{open.model}</span>
                <span style={{ flex: 1 }} />
                <button className="btn ghost sm" onClick={() => setOpen(null)}>← All digests</button>
                <button className="btn danger sm"
                        onClick={() => void (async () => {
                          try {
                            await api.digestDelete(open.id);
                            toast("Digest deleted", "info");
                            setOpen(null);
                            await load();
                          } catch (e) { toast((e as Error).message, "err"); }
                        })()}>Delete</button>
              </div>
            </div>
            <div className="brief-md" dir="auto"
                 dangerouslySetInnerHTML={{ __html: mdToHtml(open.content_md) }} />
            {open.citations && open.citations.length > 0 && (
              <details className="ai-sources" open>
                <summary>Citations ({open.citations.length})</summary>
                {open.citations.map((c) => (
                  <div key={c.idx} className="src-row" dir="auto">
                    <span className="num">[{c.idx}]</span>
                    <span className="src-title">{c.chat_title ?? "?"}</span>
                    <span className="src-date">{(c.date ?? "").slice(0, 10)}</span>
                    <span className="src-text">
                      {(c.text ?? "[deleted from archive]").slice(0, 110)}
                    </span>
                    {c.tg_link && (
                      <button className="link"
                              onClick={() => window.open(c.tg_link!, "_blank", "noopener")}>
                        Telegram ↗
                      </button>
                    )}
                  </div>
                ))}
              </details>
            )}
          </div>
        ) : digests?.map((d) => (
          <div key={d.id} className="bm-card" style={{ cursor: "pointer" }}
               onClick={() => void openDigest(d.id)}>
            <div className="bm-head">
              <span className="bm-grp">
                {d.period_start.slice(0, 10)} → {d.period_end.slice(0, 10)}
              </span>
              <span className="bm-date">{d.created_at.slice(0, 10)}</span>
              <span className="dim" style={{ fontSize: 12 }}>
                {d.schedule_id ? "scheduled" : "on demand"} · {d.model}
              </span>
            </div>
            <div className="bm-text dim" dir="auto">{d.content_md}</div>
          </div>
        ))}
      </div>

      {schedOpen && (
        <SchedModal groups={groups} onClose={() => setSchedOpen(false)}
                    onSaved={() => { setSchedOpen(false); void load(); }} />
      )}
    </div>
  );
}

function SchedModal({ groups, onClose, onSaved }: {
  groups: { chat_id: number; title: string }[];
  onClose: () => void; onSaved: () => void;
}) {
  const { toast } = useStore();
  const [frequency, setFrequency] = useState<"daily" | "weekly">("daily");
  const [hour, setHour] = useState(9);
  const [language, setLanguage] = useState("auto");
  const [scope, setScope] = useState<Set<number>>(new Set());

  return (
    <Modal title="New digest schedule" onClose={onClose}
           footer={
             <>
               <button className="btn ghost sm" onClick={onClose}>Cancel</button>
               <button className="btn primary sm"
                       onClick={() => void (async () => {
                         try {
                           await api.digestScheduleCreate({
                             frequency, chat_ids: [...scope], hour, language,
                             enabled: true,
                           });
                           toast("Schedule created", "good");
                           onSaved();
                         } catch (e) { toast((e as Error).message, "err"); }
                       })()}>Create</button>
             </>
           }>
      <p className="mm-note dim">
        The digest is generated automatically around your chosen hour (UTC)
        and saved with its citations. Nothing is re-sent when the period has
        not changed.
      </p>
      <div className="label">Frequency</div>
      <div className="seg" style={{ margin: "6px 0 12px" }}>
        <button className={frequency === "daily" ? "on" : ""}
                onClick={() => setFrequency("daily")}>Daily</button>
        <button className={frequency === "weekly" ? "on" : ""}
                onClick={() => setFrequency("weekly")}>Weekly</button>
      </div>
      <div className="label">Hour (UTC)</div>
      <input type="number" min={0} max={23} className="input" value={hour}
             style={{ width: 90, margin: "6px 0 12px" }}
             onChange={(e) => setHour(Number(e.target.value))} />
      <div className="label">Language</div>
      <select className="input" style={{ margin: "6px 0 12px", maxWidth: 140 }}
              value={language} onChange={(e) => setLanguage(e.target.value)}>
        <option value="auto">Auto-detect</option>
        <option value="en">English</option>
        <option value="ar">العربية</option>
      </select>
      <div className="label">Groups (empty = all)</div>
      <div className="chips" style={{ marginTop: 6, flexWrap: "wrap" }}>
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
    </Modal>
  );
}

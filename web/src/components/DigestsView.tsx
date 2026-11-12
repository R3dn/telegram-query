/** Digests workspace (v1.0): scheduled + on-demand cited summaries.

Every factual item in a digest cites archived messages; empty sections are
dropped by prompt contract and unresolvable citations are stripped on the
backend. Unchanged periods are never re-sent to the provider. */
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { Digest, DigestSchedule } from "../api/types";
import { mdToHtml } from "../utils/markdown";
import { Ic } from "../design/icons";
import { EmptyState } from "./EmptyState";
import { Modal } from "./Modal";

type T = ReturnType<typeof useLang>["t"];

export function DigestsView() {
  const { groups, toast, appState, jobs, selection, toggleGroup,
          evidenceFocus, setEvidenceFocus } = useStore();
  const { t } = useLang();
  const [schedules, setSchedules] = useState<DigestSchedule[]>([]);
  const [digests, setDigests] = useState<Digest[] | null>(null);
  const [open, setOpen] = useState<Digest | null>(null);
  const [schedOpen, setSchedOpen] = useState(false);
  // v1.0.2: the chosen daily/weekly option was discarded - the modal
  // always opened as "daily" and an unnoticed save scheduled the wrong
  // frequency. The selection now seeds the modal.
  const [newFreq, setNewFreq] = useState<"daily" | "weekly">("daily");
  const openSeq = useRef(0);

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
        ? t("digests.queued")
        : t("digests.alreadyQueued"), "info");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const openDigest = async (id: number) => {
    const seq = ++openSeq.current;   // v1.0.2: last click wins
    try {
      const d = await api.digestGet(id);
      if (seq === openSeq.current) setOpen(d);
    } catch (e) {
      if (seq === openSeq.current) toast((e as Error).message, "err");
    }
  };

  // v1.0.2: Evidence Explorer jump - open the referenced digest instead
  // of only landing on the list.
  useEffect(() => {
    if (evidenceFocus?.kind === "digest") {
      const id = evidenceFocus.id;
      setEvidenceFocus(null);
      void openDigest(id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evidenceFocus]);

  const aiOn = appState?.ai_configured;

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">{t("nav.digests")}</h2>
        <span className="dim dg-sub">{t("digests.subtitle")}</span>
        <span style={{ flex: 1 }} />
        <select className="input dg-sched-select" value=""
                title={t("digests.newSchedule")}
                onChange={(e) => {
                  if (e.target.value === "weekly") setNewFreq("weekly");
                  else if (e.target.value === "daily") setNewFreq("daily");
                  if (e.target.value) setSchedOpen(true);
                  e.currentTarget.value = "";   // reset for the next pick
                }}>
          <option value="">{t("digests.newScheduleOption")}</option>
          <option value="daily">{t("digests.newDaily")}</option>
          <option value="weekly">{t("digests.newWeekly")}</option>
        </select>
        <button className="btn ghost sm" disabled={!aiOn}
                title={aiOn ? t("digests.lastDayHint") : t("digests.aiRequired")}
                onClick={() => void generate("daily")}>
          <Ic.Calendar size={13} /> {t("digests.lastDay")}
        </button>
        <button className="btn ghost sm" disabled={!aiOn}
                title={aiOn ? t("digests.lastWeekHint") : t("digests.aiRequired")}
                onClick={() => void generate("weekly")}>
          <Ic.CalendarDays size={13} /> {t("digests.lastWeek")}
        </button>
      </div>

      <div className="digest-groups">
        <span className="label">{t("digests.scopeLabel")}</span>
        <div className="chips">
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
        <div className="bm-bar dg-scheds-bar">
          <span className="label">{t("digests.schedules")}</span>
        </div>
      )}
      {schedules.map((s) => (
        <div key={s.id} className="bm-card dg-sched">
          <div className="bm-head">
            <span className="badge">
              <Ic.CalendarDays size={10} />{" "}
              {t(s.frequency === "daily" ? "interval.everyDay" : "digests.freqWeekly")}
            </span>
            <span className="dim dg-sub">
              {t("digests.atHour", { h: String(s.hour).padStart(2, "0") })} ·{" "}
              {s.chat_ids.length
                ? t("digests.scopeGroups", { n: s.chat_ids.length })
                : t("filter.allGroups")}
              {s.last_run && ` · ${t("digests.lastRun", { date: s.last_run.slice(0, 10) })}`}
            </span>
            <span style={{ flex: 1 }} />
            <button className="btn danger sm"
                    onClick={() => void (async () => {
                      try {
                        await api.digestScheduleDelete(s.id);
                        toast(t("digests.scheduleDeleted"), "info");
                        await load();
                      } catch (e) { toast((e as Error).message, "err"); }
                    })()}>
              <Ic.Trash size={12} /> {t("action.delete")}
            </button>
          </div>
        </div>
      ))}

      <div className="feed">
        {digests === null && (
          <div className="feed-loading">
            <Ic.Spin size={13} className="spin" /> {t("state.loading")}
          </div>
        )}
        {digests !== null && digests.length === 0 && !open && (
          <EmptyState icon="Newspaper" title={t("digests.emptyTitle")}
            hint={aiOn
              ? t("digests.emptyHintAi")
              : t("digests.emptyHintAiOff")} />
        )}
        {open ? (
          <div className="brief-detail dg-brief">
            <div className="brief-head">
              <div className="brief-meta">
                <span className="badge">
                  {open.period_start.slice(0, 10)} <Ic.ArrowRight size={11} />{" "}
                  {open.period_end.slice(0, 10)}
                </span>
                <span className="dim">{open.model}</span>
                <span style={{ flex: 1 }} />
                <button className="btn ghost sm" onClick={() => setOpen(null)}>
                  <Ic.ChevronLeft size={13} /> {t("digests.backAll")}
                </button>
                <button className="btn danger sm"
                        onClick={() => void (async () => {
                          try {
                            await api.digestDelete(open.id);
                            toast(t("digests.deleted"), "info");
                            setOpen(null);
                            await load();
                          } catch (e) { toast((e as Error).message, "err"); }
                        })()}>
                  <Ic.Trash size={12} /> {t("action.delete")}
                </button>
              </div>
            </div>
            <div className="brief-md" dir="auto"
                 dangerouslySetInnerHTML={{ __html: mdToHtml(open.content_md) }} />
            {open.citations && open.citations.length > 0 && (
              <details className="ai-sources" open>
                <summary>{t("digests.citations", { n: open.citations.length })}</summary>
                {open.citations.map((c) => (
                  <div key={c.idx} className="src-row" dir="auto">
                    <span className="num">[{c.idx}]</span>
                    <span className="src-title">{c.chat_title ?? "?"}</span>
                    <span className="src-date">{(c.date ?? "").slice(0, 10)}</span>
                    <span className="src-text">
                      {(c.text ?? t("digests.deletedFromArchive")).slice(0, 110)}
                    </span>
                    {c.tg_link && (
                      <button className="link"
                              onClick={() => window.open(c.tg_link!, "_blank", "noopener")}>
                        <Ic.ExternalLink size={11} /> {t("action.openTelegram")}
                      </button>
                    )}
                  </div>
                ))}
              </details>
            )}
          </div>
        ) : digests?.map((d) => (
          <div key={d.id} className="bm-card dg-item"
               onClick={() => void openDigest(d.id)}>
            <div className="bm-head">
              <span className="bm-grp">
                {d.period_start.slice(0, 10)} <Ic.ArrowRight size={12} />{" "}
                {d.period_end.slice(0, 10)}
              </span>
              <span className="bm-date">{d.created_at.slice(0, 10)}</span>
              <span className="dim dg-sub">
                {t(d.schedule_id ? "digests.scheduled" : "digests.onDemand")} · {d.model}
              </span>
            </div>
            <div className="bm-text dim" dir="auto">{d.content_md}</div>
          </div>
        ))}
      </div>

      {schedOpen && (
        <SchedModal key={newFreq} initialFreq={newFreq} groups={groups} t={t}
                    onClose={() => setSchedOpen(false)}
                    onSaved={() => { setSchedOpen(false); void load(); }} />
      )}
    </div>
  );
}

function SchedModal({ initialFreq, groups, onClose, onSaved, t }: {
  initialFreq: "daily" | "weekly";
  groups: { chat_id: number; title: string }[];
  onClose: () => void; onSaved: () => void; t: T;
}) {
  const { toast } = useStore();
  const [frequency, setFrequency] = useState<"daily" | "weekly">(initialFreq);
  const [hour, setHour] = useState(9);
  const [language, setLanguage] = useState("auto");
  const [scope, setScope] = useState<Set<number>>(new Set());

  return (
    <Modal title={t("digests.newScheduleTitle")} onClose={onClose}
           footer={
      <>
        <button className="btn ghost sm" onClick={onClose}>{t("action.cancel")}</button>
        <button className="btn primary sm"
                onClick={() => void (async () => {
                  try {
                    await api.digestScheduleCreate({
                      frequency, chat_ids: [...scope], hour, language,
                      enabled: true,
                    });
                    toast(t("digests.scheduleCreated"), "good");
                    onSaved();
                  } catch (e) { toast((e as Error).message, "err"); }
                })()}>
          <Ic.Plus size={13} /> {t("digests.create")}
        </button>
      </>
    }>
      <p className="mm-note dim">{t("digests.schedNote")}</p>
      <div className="label">{t("digests.frequency")}</div>
      <div className="seg" style={{ margin: "6px 0 12px" }}>
        <button className={frequency === "daily" ? "on" : ""}
                onClick={() => setFrequency("daily")}>{t("digests.daily")}</button>
        <button className={frequency === "weekly" ? "on" : ""}
                onClick={() => setFrequency("weekly")}>{t("digests.weekly")}</button>
      </div>
      <div className="label">{t("digests.hourUtc")}</div>
      <input type="number" min={0} max={23} className="input" value={hour}
             style={{ width: 90, margin: "6px 0 12px" }}
             onChange={(e) => setHour(Number(e.target.value))} />
      <div className="label">{t("digests.language")}</div>
      <select className="input" style={{ margin: "6px 0 12px", maxWidth: 140 }}
              value={language} onChange={(e) => setLanguage(e.target.value)}>
        <option value="auto">{t("digests.langAuto")}</option>
        <option value="en">English</option>
        <option value="ar">العربية</option>
      </select>
      <div className="label">{t("digests.fieldScope")}</div>
      <div className="chips dg-chips">
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

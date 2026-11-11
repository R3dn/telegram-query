/** FAQ workspace (v1.0): recurring questions + proposed answers.

An FAQ is never trusted automatically: discovery proposes candidates, and a
human approves. New evidence against an approved answer flags it for
review instead of silently replacing it. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { Faq } from "../api/types";
import { mdToHtml } from "../utils/markdown";
import { statusTone } from "../utils/format";
import { Ic } from "../design/icons";
import { EmptyState } from "./EmptyState";

const TABS = ["candidate", "approved", "needs_review", "rejected"] as const;

const EMPTY_KEY: Record<(typeof TABS)[number] | "all", string> = {
  all: "faqs.emptyAll",
  candidate: "faqs.emptyCandidate",
  approved: "faqs.emptyApproved",
  needs_review: "faqs.emptyReview",
  rejected: "faqs.emptyRejected",
};

export function FaqView() {
  const { toast, appState, groups, selection, toggleGroup, jobs } = useStore();
  const { t } = useLang();
  const [tab, setTab] = useState<(typeof TABS)[number] | "all">("candidate");
  const [rows, setRows] = useState<Faq[] | null>(null);
  const [open, setOpen] = useState<Faq | null>(null);
  const [editing, setEditing] = useState(false);
  const [answer, setAnswer] = useState("");

  const load = async (s = tab) => {
    try {
      setRows(await api.faqs({ status: s === "all" ? undefined : s }));
    } catch (e) {
      toast((e as Error).message, "err");
      setRows([]);
    }
  };
  useEffect(() => { void load(tab); }, [tab]);

  const lastDone = jobs?.last_done;
  useEffect(() => {
    if (lastDone?.name === "faq") void load(tab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastDone?.finished_at]);

  const discover = async () => {
    try {
      const r = await api.faqDiscover({
        chat_ids: [...selection], days: 90,
      });
      toast(r.started ? t("faqs.queued") : t("faqs.discoveryRunning"), "info");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const patch = async (id: number, p: Record<string, unknown>, msg: string) => {
    try {
      await api.faqPatch(id, p);
      toast(msg, "good");
      await load();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const aiOn = appState?.ai_configured;
  const stLabel = (s: Faq["status"]) => t(`faqs.st.${s}`);

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">{t("nav.faqs")}</h2>
        <div className="seg">
          <button className={tab === "all" ? "on" : ""}
                  onClick={() => setTab("all")}>{t("faqs.tabAll")}</button>
          {TABS.map((s) => (
            <button key={s} className={tab === s ? "on" : ""}
                    onClick={() => setTab(s)}>{t(`faqs.st.${s}`)}</button>
          ))}
        </div>
        <span style={{ flex: 1 }} />
        <button className="btn primary sm" disabled={!aiOn}
                title={aiOn ? t("faqs.discoverHint") : t("faqs.aiRequired")}
                onClick={() => void discover()}>
          <Ic.Sparkles size={13} /> {t("faqs.discover")}
        </button>
      </div>

      <div className="digest-groups">
        <span className="label">{t("faqs.scopeLabel")}</span>
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

      <div className="feed">
        {rows === null && (
          <div className="feed-loading">
            <Ic.Spin size={13} className="spin" /> {t("state.loading")}
          </div>
        )}
        {rows !== null && rows.length === 0 && (
          <EmptyState icon="HelpCircle" title={t(EMPTY_KEY[tab])}
            hint={aiOn
              ? t("faqs.emptyHintAi")
              : t("faqs.emptyHintAiOff")} />
        )}
        {rows?.map((f) => (
          <div key={f.id} className="bm-card">
            <div className="bm-head">
              <span className={`badge ${statusTone(f.status)}`}>{stLabel(f.status)}</span>
              <span className="bm-grp" dir="auto">{f.question}</span>
              <span className="dim fq-sub">
                {t("faqs.freq", { n: f.frequency })} ·{" "}
                {t("faqs.lastSeen", { date: f.last_seen.slice(0, 10) })}
              </span>
              <span style={{ flex: 1 }} />
              <button className="btn ghost sm" onClick={() => {
                setOpen(f); setEditing(false); setAnswer(f.answer_md ?? "");
              }}>
                <Ic.ChevronRight size={12} /> {t("action.view")}
              </button>
              {f.status === "candidate" && (
                <button className="btn primary sm"
                        onClick={() => void patch(f.id, { status: "approved" }, t("faqs.approvedToast"))}>
                  <Ic.Check size={12} /> {t("faqs.approve")}
                </button>
              )}
              {f.status === "needs_review" && (
                <button className="btn ghost sm" title={t("faqs.stillCorrectHint")}
                        onClick={() => void patch(f.id, { status: "approved" }, t("faqs.reapproved"))}>
                  <Ic.CircleCheck size={12} /> {t("faqs.stillCorrect")}
                </button>
              )}
            </div>
            {f.answer_md && (
              <div className="faq-answer" dir="auto"
                   dangerouslySetInnerHTML={{ __html: mdToHtml(f.answer_md) }} />
            )}
            {f.status === "candidate" && !f.answer_md && (
              <div className="bm-note dim fq-note">{t("faqs.noAnswerYet")}</div>
            )}
          </div>
        ))}
      </div>

      {open && (
        <div className="modal-overlay" onMouseDown={(e) => {
          if (e.target === e.currentTarget) setOpen(null);
        }}>
          <div className="modal wide">
            <div className="modal-head">
              <h3 dir="auto">{open.question}</h3>
              <button className="btn ghost sm" title={t("action.close")}
                      onClick={() => setOpen(null)}>
                <Ic.Close size={14} />
              </button>
            </div>
            <div className="modal-body">
              {editing ? (
                <>
                  <textarea className="input" rows={8} dir="auto" value={answer}
                            onChange={(e) => setAnswer(e.target.value)} />
                  <div className="settings-actions" style={{ marginTop: 8 }}>
                    <button className="btn primary sm"
                            onClick={() => void (async () => {
                              await patch(open.id, { answer_md: answer }, t("faqs.answerSaved"));
                              setOpen(null);
                            })()}>
                      <Ic.Save size={13} /> {t("faqs.saveAnswer")}
                    </button>
                    <button className="btn ghost sm" onClick={() => setEditing(false)}>
                      {t("action.cancel")}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  {open.answer_md ? (
                    <div className="faq-answer" dir="auto"
                         dangerouslySetInnerHTML={{ __html: mdToHtml(open.answer_md) }} />
                  ) : (
                    <p className="dim">{t("faqs.noDraftedAnswer")}</p>
                  )}
                  <div className="label" style={{ marginTop: 12 }}>
                    {t("faqs.askedSources", { n: open.frequency })}
                  </div>
                  {open.source_questions.map((s, i) => (
                    <div key={i} className="src-row" dir="auto">
                      <span className="src-title">{s.chat_title ?? "?"}</span>
                      <span className="src-date">{s.date}</span>
                      <span className="src-text">{(s.text ?? t("faqs.deleted")).slice(0, 90)}</span>
                      {s.tg_link && (
                        <button className="link"
                                onClick={() => window.open(s.tg_link!, "_blank", "noopener")}>
                          <Ic.ExternalLink size={11} /> {t("action.openTelegram")}
                        </button>
                      )}
                    </div>
                  ))}
                  <div className="settings-actions" style={{ marginTop: 14 }}>
                    <button className="btn primary sm" onClick={() => setEditing(true)}>
                      <Ic.Pencil size={13} /> {t("faqs.editAnswer")}
                    </button>
                    <button className="btn ghost sm"
                            onClick={() => void (async () => {
                              await patch(open.id, { status: "outdated" }, t("faqs.markedOutdated"));
                              setOpen(null);
                            })()}>
                      <Ic.Clock size={13} /> {t("faqs.markOutdated")}
                    </button>
                    <button className="btn danger sm"
                            onClick={() => void (async () => {
                              try {
                                await api.faqDelete(open.id);
                                toast(t("faqs.deletedToast"), "info");
                                setOpen(null);
                                await load();
                              } catch (e) { toast((e as Error).message, "err"); }
                            })()}>
                      <Ic.Trash size={12} /> {t("action.delete")}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

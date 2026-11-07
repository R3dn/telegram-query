/** FAQ workspace (v0.6): recurring questions + proposed answers.

An FAQ is never trusted automatically: discovery proposes candidates, and a
human approves. New evidence against an approved answer flags it for
review instead of silently replacing it. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { Faq } from "../api/types";
import { mdToHtml } from "../utils/markdown";
import { statusTone } from "../utils/format";
import { EmptyState } from "./EmptyState";

const TABS = ["candidate", "approved", "needs_review", "rejected"] as const;

export function FaqView() {
  const { toast, appState, groups, selection, toggleGroup, jobs } = useStore();
  const [tab, setTab] = useState<(typeof TABS)[number] | "all">("candidate");
  const [rows, setRows] = useState<Faq[] | null>(null);
  const [open, setOpen] = useState<Faq | null>(null);
  const [editing, setEditing] = useState(false);
  const [answer, setAnswer] = useState("");

  const load = async (t = tab) => {
    try {
      setRows(await api.faqs({ status: t === "all" ? undefined : t }));
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
      toast(r.started ? "FAQ discovery queued - watch Jobs" : "Discovery already running", "info");
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

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">FAQs</h2>
        <div className="seg">
          <button className={tab === "all" ? "on" : ""} onClick={() => setTab("all")}>All</button>
          {TABS.map((t) => (
            <button key={t} className={tab === t ? "on" : ""}
                    onClick={() => setTab(t)}>{t.replace("_", " ")}</button>
          ))}
        </div>
        <span style={{ flex: 1 }} />
        <button className="btn primary sm" disabled={!aiOn}
                title={aiOn ? "Scan the last 90 days for recurring questions"
                            : "Configure an AI provider first"}
                onClick={() => void discover()}>Discover FAQs</button>
      </div>

      <div className="digest-groups">
        <span className="label">Discovery scope (groups):</span>
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

      <div className="feed">
        {rows === null && <div className="side-note">loading…</div>}
        {rows !== null && rows.length === 0 && (
          <EmptyState icon="❓" title={`No ${tab === "all" ? "" : tab} FAQs`}
            hint={aiOn
              ? "Run \"Discover FAQs\" to cluster the questions your groups keep asking. Proposed answers cite real messages; nothing becomes trusted knowledge until you approve it."
              : "Configure an AI provider (Settings) to draft answers. Question clustering itself is deterministic."} />
        )}
        {rows?.map((f) => (
          <div key={f.id} className="bm-card">
            <div className="bm-head">
              <span className={`badge ${statusTone(f.status)}`}>{f.status.replace("_", " ")}</span>
              <span className="bm-grp" dir="auto">{f.question}</span>
              <span className="dim" style={{ fontSize: 12 }}>
                ×{f.frequency} · last {f.last_seen.slice(0, 10)}
              </span>
              <span style={{ flex: 1 }} />
              <button className="btn ghost sm" onClick={() => {
                setOpen(f); setEditing(false); setAnswer(f.answer_md ?? "");
              }}>Open</button>
              {f.status === "candidate" && (
                <button className="btn primary sm"
                        onClick={() => void patch(f.id, { status: "approved" }, "Approved ✓")}>
                  Approve
                </button>
              )}
              {f.status === "needs_review" && (
                <button className="btn ghost sm"
                        title="Re-approve after checking the new evidence"
                        onClick={() => void patch(f.id, { status: "approved" }, "Re-approved")}>
                  Still correct
                </button>
              )}
            </div>
            {f.answer_md && (
              <div className="faq-answer" dir="auto"
                   dangerouslySetInnerHTML={{ __html: mdToHtml(f.answer_md) }} />
            )}
            {f.status === "candidate" && !f.answer_md && (
              <div className="bm-note dim">no drafted answer yet - run discovery again</div>
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
              <button className="btn ghost sm" onClick={() => setOpen(null)}>✕</button>
            </div>
            <div className="modal-body">
              {editing ? (
                <>
                  <textarea className="input" rows={8} dir="auto" value={answer}
                            onChange={(e) => setAnswer(e.target.value)} />
                  <div className="settings-actions" style={{ marginTop: 8 }}>
                    <button className="btn primary sm"
                            onClick={() => void (async () => {
                              await patch(open.id, { answer_md: answer }, "Answer saved");
                              setOpen(null);
                            })()}>Save answer</button>
                    <button className="btn ghost sm" onClick={() => setEditing(false)}>Cancel</button>
                  </div>
                </>
              ) : (
                <>
                  {open.answer_md ? (
                    <div className="faq-answer" dir="auto"
                         dangerouslySetInnerHTML={{ __html: mdToHtml(open.answer_md) }} />
                  ) : (
                    <p className="dim">No drafted answer yet.</p>
                  )}
                  <div className="label" style={{ marginTop: 12 }}>
                    Asked {open.frequency}× - question sources
                  </div>
                  {open.source_questions.map((s, i) => (
                    <div key={i} className="src-row" dir="auto">
                      <span className="src-title">{s.chat_title ?? "?"}</span>
                      <span className="src-date">{s.date}</span>
                      <span className="src-text">{(s.text ?? "[deleted]").slice(0, 90)}</span>
                      {s.tg_link && (
                        <button className="link"
                                onClick={() => window.open(s.tg_link!, "_blank", "noopener")}>
                          Telegram ↗
                        </button>
                      )}
                    </div>
                  ))}
                  <div className="settings-actions" style={{ marginTop: 14 }}>
                    <button className="btn primary sm" onClick={() => setEditing(true)}>
                      Edit answer
                    </button>
                    <button className="btn ghost sm"
                            onClick={() => void (async () => {
                              await patch(open.id, { status: "outdated" }, "Marked outdated");
                              setOpen(null);
                            })()}>Mark outdated</button>
                    <button className="btn danger sm"
                            onClick={() => void (async () => {
                              try {
                                await api.faqDelete(open.id);
                                toast("FAQ deleted", "info");
                                setOpen(null);
                                await load();
                              } catch (e) { toast((e as Error).message, "err"); }
                            })()}>Delete</button>
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

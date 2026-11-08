/** Discover home (v0.7): the product's landing view.

 *  Deterministic-first community intelligence: trending topics, cross-
 *  group stories, unanswered questions, and group activity - every
 *  card reaches the original messages in <=2 clicks. The only AI here
 *  is the optional topic timeline (cited, fingerprint-cached). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type {
  ActivityReport, OpenQuestion, Story, TimelineResult,
  TrendingTopic,
} from "../api/types";
import { mdToHtml } from "../utils/markdown";
import { nfmt } from "../utils/format";
import { EmptyState } from "./EmptyState";

type DaysWindow = "7d" | "30d";

export function DiscoverView() {
  const { appState, selection, runSearch, select, setRightTab,
          toast, jobs, clearSelection, toggleGroup } = useStore();
  const [days, setDays] = useState<DaysWindow>("7d");
  const [trending, setTrending] = useState<TrendingTopic[] | null>(null);
  const [stories, setStories] = useState<Story[] | null>(null);
  const [questions, setQuestions] = useState<OpenQuestion[] | null>(null);
  const [activity, setActivity] = useState<ActivityReport | null>(null);
  const [timeline, setTimeline] = useState<TimelineResult | null>(null);
  const [timelineBusy, setTimelineBusy] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);

  const nDays = days === "7d" ? 7 : 30;
  const groupIds = [...selection];

  const load = async () => {
    try {
      const [t, s, q, a] = await Promise.all([
        api.discoverTrending({ days: nDays, groups: groupIds, minVolume: 1 }),
        api.discoverStories({ days: nDays, groups: groupIds }),
        api.discoverQuestions({ status: "open", groups: groupIds }),
        api.discoverActivity({ days: 30, groups: groupIds }),
      ]);
      setTrending(t); setStories(s); setQuestions(q); setActivity(a);
    } catch (e) {
      toast((e as Error).message, "err");
      setTrending([]); setStories([]); setQuestions([]); setActivity(null);
    }
  };

  useEffect(() => {
    if (trending !== null) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days, selection, appState?.messages, jobs?.last_done?.finished_at]);

  // first mount: fetch immediately
  useEffect(() => { void load(); /* eslint-disable-line */ }, []);

  const openMessage = (m: { chat_id: number; msg_id: number }) => {
    void (async () => {
      try {
        const full = await api.message(m.chat_id, m.msg_id);
        select(full);
        setRightTab("details");
      } catch {
        toast("Could not open the original message", "err");
      }
    })();
  };

  const showTimeline = (term: string) => {
    setTimelineBusy(true);
    setTimeline(null);
    void (async () => {
      try {
        setTimeline(await api.topicTimeline({ term, chat_ids: groupIds, days: nDays }));
      } catch (e) {
        toast((e as Error).message, "err");
      } finally {
        setTimelineBusy(false);
      }
    })();
  };

  const rebuild = () => {
    setRebuilding(true);
    void (async () => {
      try {
        const r = await api.discoverRebuild();
        toast(r.started ? "Discovery rebuild queued - watch Jobs"
                        : "A discovery job is already queued", "info");
      } catch (e) {
        toast((e as Error).message, "err");
      } finally {
        setRebuilding(false);
      }
    })();
  };

  const scanQuestions = () => {
    void (async () => {
      try {
        const r = await api.questionScan(30);
        toast(`Scanned - ${r.new_open} new open question(s)`, "info");
        setQuestions(await api.discoverQuestions({ status: "open", groups: groupIds }));
      } catch (e) {
        toast((e as Error).message, "err");
      }
    })();
  };

  const setQuestionStatus = (q: OpenQuestion, status: string) => {
    void (async () => {
      try {
        await api.questionSetStatus(q.chat_id, q.msg_id, status);
        setQuestions((qs) => (qs ? qs.filter((x) => x.chat_id !== q.chat_id || x.msg_id !== q.msg_id) : qs));
        toast(status === "ignored" ? "Question ignored" : "Marked answered", "info");
      } catch (e) {
        toast((e as Error).message, "err");
      }
    })();
  };

  if (appState && appState.messages === 0) {
    return (
      <div className="feed-col">
        <div className="feed">
          <EmptyState icon="📈" title="Nothing to discover yet"
            hint="Sync your groups first - trending topics, cross-group stories and unanswered questions appear here automatically after every sync." />
        </div>
      </div>
    );
  }

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">Discover</h2>
        <span className="dim" style={{ fontSize: 12 }}>
          deterministic - computed from your archive, no AI required
        </span>
        <span style={{ flex: 1 }} />
        <div className="seg">
          {(["7d", "30d"] as const).map((d) => (
            <button key={d} className={days === d ? "on" : ""}
                    onClick={() => { setDays(d); setTimeline(null); }}>
              {d === "7d" ? "last 7 days" : "last 30 days"}
            </button>
          ))}
        </div>
        <button className="btn ghost sm" disabled={rebuilding}
                title="Rebuild all discovery data from the archive (visible job)"
                onClick={rebuild}>
          {rebuilding ? "…" : "Rebuild data"}
        </button>
      </div>

      {selection.size > 0 && (
        <div className="digest-groups">
          <span className="label">Scope:</span>
          <button className="chip on" onClick={() => clearSelection()}>
            👥 {selection.size} group{selection.size > 1 ? "s" : ""} <span className="x">✕</span>
          </button>
          <span className="dim" style={{ fontSize: 11 }}>
            (clear to see all groups)
          </span>
        </div>
      )}

      <div className="feed">
        {/* ---- Trending topics ---- */}
        <SectionHead icon="🔥" title="Trending topics"
                     note="recent volume vs the prior window - click through to the messages" />
        {trending === null && <div className="side-note">loading…</div>}
        {trending !== null && trending.length === 0 && (
          <div className="side-note">No topic stood out in the last {nDays} days.</div>
        )}
        {trending?.map((t) => (
          <div key={t.term} className="trend-row">
            <div className="trend-main">
              <button className="trend-term" dir="auto"
                      title="Open matching messages in the feed"
                      onClick={() => runSearch(t.term)}>
                {t.term}
              </button>
              <span className="badge warn" title="recent vs prior window">
                {t.score}×{t.baseline === 0 ? " new" : ""}
              </span>
              <span className="dim" style={{ fontSize: 11 }}>
                {nfmt(t.recent)} msg{t.recent === 1 ? "" : "s"} · {t.chats} group{t.chats === 1 ? "" : "s"}
              </span>
            </div>
            {t.sample && (
              <div className="trend-sample dim" dir="auto"
                   title="Open the sample message"
                   onClick={() => openMessage(t.sample!)}>
                <span className="src-title">{t.sample.chat_title}</span>
                <span className="src-text" dir="auto">{t.sample.text}</span>
              </div>
            )}
            <div className="trend-actions">
              <button className="btn ghost sm" onClick={() => runSearch(t.term)}>View</button>
              <button className="btn ghost sm" disabled={timelineBusy}
                      onClick={() => showTimeline(t.term)}>
                {timelineBusy ? "…" : "Timeline ✦"}
              </button>
            </div>
          </div>
        ))}

        {(timeline || timelineBusy) && (
          <div className="timeline-panel">
            <div className="bm-head">
              <span className="badge">topic timeline</span>
              <span className="dim" dir="auto">{timeline?.term ?? "…"}</span>
              <span style={{ flex: 1 }} />
              <button className="btn ghost sm" onClick={() => { setTimeline(null); setTimelineBusy(false); }}>✕</button>
            </div>
            {timelineBusy && <div className="side-note">analyzing messages…</div>}
            {timeline && (
              <>
                <div className="brief-md" dir="auto"
                     dangerouslySetInnerHTML={{ __html: mdToHtml(timeline.timeline_md) }}
                     onClick={(e) => {
                       const el = (e.target as HTMLElement).closest("[data-cite]");
                       if (!el) return;
                       const n = parseInt((el as HTMLElement).dataset.cite ?? "", 10);
                       const src = timeline.sources[n - 1];
                       if (src) openMessage(src);
                       else toast(`Citation [${n}] has no matching message`, "err");
                     }} />
                <details className="ai-sources">
                  <summary>Sources ({timeline.sources.length})</summary>
                  {timeline.sources.map((s, i) => (
                    <button key={i} className="src-row" onClick={() => openMessage(s)}>
                      <span className="num">[{i + 1}]</span>
                      <span className="src-title" dir="auto">{s.chat_title}</span>
                      <span className="src-date">{(s.date ?? "").slice(0, 10)}</span>
                      <span className="src-text" dir="auto">{s.text.slice(0, 110)}</span>
                    </button>
                  ))}
                </details>
              </>
            )}
          </div>
        )}

        {/* ---- Cross-group stories ---- */}
        <SectionHead icon="📡" title="Cross-group stories"
                     note="the same post forwarded across your communities" />
        {stories === null && <div className="side-note">loading…</div>}
        {stories !== null && stories.length === 0 && (
          <div className="side-note">No cross-group forwards in the last {nDays} days.</div>
        )}
        {stories?.map((s) => (
          <details key={s.key} className="story-card">
            <summary>
              <span className="badge">{s.chats} groups · {s.n} copies</span>
              <span className="story-text" dir="auto">{s.sample_text.slice(0, 140)}</span>
            </summary>
            <div className="story-groups">
              {s.chat_titles.map((t) => (
                <span key={t} className="chip static" dir="auto">{t}</span>
              ))}
            </div>
            {s.occurrences.map((o) => (
              <button key={`${o.chat_id}-${o.msg_id}`} className="src-row"
                      onClick={() => openMessage(o)}>
                <span className="src-title" dir="auto">{o.chat_title}</span>
                <span className="src-date">{(o.date ?? "").slice(0, 10)}</span>
                <span className="src-text" dir="auto">{o.text.slice(0, 110)}</span>
              </button>
            ))}
          </details>
        ))}

        {/* ---- Unanswered questions ---- */}
        <SectionHead icon="❓" title={`Unanswered questions${questions?.length ? ` (${questions.length})` : ""}`}
                     note="questions with no reply - answer one, or let the FAQ answer it" />
        {questions !== null && questions.length > 0 && (
          <div className="q-actions">
            <button className="btn ghost sm" onClick={scanQuestions}>Scan recent</button>
            <span className="dim" style={{ fontSize: 11, alignSelf: "center" }}>
              re-checks the last 30 days; human statuses are never overwritten
            </span>
          </div>
        )}
        {questions === null && <div className="side-note">loading…</div>}
        {questions !== null && questions.length === 0 && (
          <div className="side-note">No open questions - the communities answer fast 💪</div>
        )}
        {questions?.map((q) => (
          <div key={`${q.chat_id}-${q.msg_id}`} className="q-row">
            <div className="q-main">
              <button className="q-text" dir="auto" title="Open in the conversation"
                      onClick={() => openMessage(q)}>{q.text}</button>
              <div className="q-meta dim">
                <span dir="auto">{q.chat_title}</span> · <span>{(q.asked_at ?? "").slice(0, 10)}</span>
                {q.replies === 0 && q.followers === 0 && <span> · no response seen</span>}
              </div>
            </div>
            {q.faq && (
              <details className="q-faq">
                <summary>💡 an approved FAQ answer matches</summary>
                <div dir="auto" dangerouslySetInnerHTML={{ __html: mdToHtml(q.faq.answer_md ?? "") }} />
              </details>
            )}
            <div className="q-acts">
              <button className="btn ghost sm" onClick={() => openMessage(q)}>Open</button>
              <button className="btn ghost sm" onClick={() => setQuestionStatus(q, "answered")}>✓ answered</button>
              <button className="btn ghost sm" onClick={() => setQuestionStatus(q, "ignored")}>ignore</button>
            </div>
          </div>
        ))}

        {/* ---- Group activity ---- */}
        <SectionHead icon="📊" title="Group activity (30 days)"
                     note="aggregate only - no per-member analytics exists in this product" />
        {activity === null && <div className="side-note">loading…</div>}
        {activity && activity.groups.length === 0 && (
          <div className="side-note">No messages in the last 30 days.</div>
        )}
        {activity?.groups.slice(0, 8).map((g) => (
          <button key={g.chat_id} className="act-row"
                  onClick={() => toggleGroup(g.chat_id)}
                  title="Toggle this group in the scope">
            <span className="g-title" dir="auto">{g.title}</span>
            <Spark daily={g.daily} />
            <span className="dim" style={{ fontSize: 11, flex: "none" }}>
              {nfmt(g.total)} msgs · {g.per_day}/day
            </span>
          </button>
        ))}
        {activity && activity.groups.length > 8 && (
          <div className="side-note">+{activity.groups.length - 8} more groups</div>
        )}
      </div>
    </div>
  );
}

function SectionHead({ icon, title, note }: { icon: string; title: string; note?: string }) {
  return (
    <div className="disc-section-head">
      <span className="nav-ic">{icon}</span>
      <span className="disc-title">{title}</span>
      {note && <span className="dim" style={{ fontSize: 11 }}>{note}</span>}
    </div>
  );
}

/** Tiny deterministic sparkline: one bar per day of the window. */
function Spark({ daily }: { daily: { day: string; n: number }[] }) {
  const max = Math.max(1, ...daily.map((d) => d.n));
  const w = 90, h = 22;
  const bw = daily.length ? Math.max(1.5, w / daily.length - 1) : 0;
  return (
    <svg width={w} height={h} className="spark" aria-hidden>
      {daily.map((d, i) => {
        const bh = Math.max(1.5, (d.n / max) * (h - 2));
        return (
          <rect key={d.day} x={i * (bw + 1)} y={h - bh} width={bw} height={bh}
                rx={1} fill="var(--accent)" opacity={0.75} />
        );
      })}
    </svg>
  );
}

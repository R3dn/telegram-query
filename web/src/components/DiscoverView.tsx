/** Discover home (v0.7): the product's landing view.
 *
 *  Deterministic-first community intelligence: trending topics, cross-
 *  group stories, unanswered questions, and group activity - every
 *  card reaches the original messages in <=2 clicks. The only AI here
 *  is the optional topic timeline (cited, fingerprint-cached). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type {
  ActivityReport, OpenQuestion, Story, TimelineResult,
  TrendingTopic,
} from "../api/types";
import { mdToHtml } from "../utils/markdown";
import { nfmt } from "../utils/format";
import { Ic, type IconName } from "../design/icons";
import { EmptyState } from "./EmptyState";

type DaysWindow = "7d" | "30d";

export function DiscoverView() {
  const { appState, selection, runSearch, select, setRightTab,
          toast, jobs, clearSelection, toggleGroup } = useStore();
  const { t } = useLang();
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
      const [trendingRows, storyRows, questionRows, activityRows] = await Promise.all([
        api.discoverTrending({ days: nDays, groups: groupIds, minVolume: 1 }),
        api.discoverStories({ days: nDays, groups: groupIds }),
        api.discoverQuestions({ status: "open", groups: groupIds }),
        api.discoverActivity({ days: 30, groups: groupIds }),
      ]);
      setTrending(trendingRows); setStories(storyRows);
      setQuestions(questionRows); setActivity(activityRows);
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
        toast(t("discover.toast.openOriginalFailed"), "err");
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
        toast(r.started ? t("discover.rebuild.queued")
                        : t("discover.rebuild.alreadyQueued"), "info");
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
        toast(t("discover.toast.scanned", { n: r.new_open }), "info");
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
        toast(status === "ignored" ? t("discover.toast.ignored")
                                   : t("discover.toast.answered"), "info");
      } catch (e) {
        toast((e as Error).message, "err");
      }
    })();
  };

  if (appState && appState.messages === 0) {
    return (
      <div className="feed-col">
        <div className="feed">
          <EmptyState icon="TrendingUp" title={t("discover.empty.title")}
            hint={t("discover.empty.hint")} />
        </div>
      </div>
    );
  }

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <span className="nav-ic"><Ic.TrendingUp size={18} /></span>
        <h2 className="bm-title">{t("nav.discover")}</h2>
        <span className="dim" style={{ fontSize: 12 }}>
          {t("discover.subtitle")}
        </span>
        <span style={{ flex: 1 }} />
        <div className="seg">
          {(["7d", "30d"] as const).map((d) => (
            <button key={d} className={days === d ? "on" : ""}
                    onClick={() => { setDays(d); setTimeline(null); }}>
              {t("discover.window.last", { n: d === "7d" ? 7 : 30 })}
            </button>
          ))}
        </div>
        <button className="btn ghost sm" disabled={rebuilding}
                title={t("discover.rebuild.title")}
                onClick={rebuild}>
          {rebuilding
            ? <Ic.Spin size={13} className="spin" />
            : <><Ic.RefreshCw size={13} /> {t("discover.rebuild.button")}</>}
        </button>
      </div>

      {selection.size > 0 && (
        <div className="digest-groups">
          <span className="label">{t("discover.scope.label")}</span>
          <button className="chip on" onClick={() => clearSelection()}>
            <Ic.Users size={13} />
            {selection.size === 1
              ? t("discover.scope.one", { n: selection.size })
              : t("discover.scope.many", { n: selection.size })}
            <span className="x"><Ic.Close size={11} /></span>
          </button>
          <span className="dim" style={{ fontSize: 11 }}>
            {t("discover.scope.clearHint")}
          </span>
        </div>
      )}

      <div className="feed">
        {/* ---- Trending topics ---- */}
        <SectionHead icon="Flame" title={t("discover.trending.title")}
                     note={t("discover.trending.note")} />
        {trending === null && <div className="side-note">{t("state.loading")}</div>}
        {trending !== null && trending.length === 0 && (
          <div className="side-note">{t("discover.trending.empty", { n: nDays })}</div>
        )}
        {trending?.map((topic) => (
          <div key={topic.term} className="trend-row">
            <div className="trend-main">
              <button className="trend-term" dir="auto"
                      title={t("discover.trending.openTitle")}
                      onClick={() => runSearch(topic.term)}>
                {topic.term}
              </button>
              <span className="badge warn" title={t("discover.trending.badgeTitle")}>
                {topic.score}×{topic.baseline === 0 ? ` ${t("discover.trending.new")}` : ""}
              </span>
              <span className="dim" style={{ fontSize: 11 }}>
                {topic.recent === 1
                  ? t("discover.trending.oneMsg", { n: nfmt(topic.recent) })
                  : t("discover.trending.msgs", { n: nfmt(topic.recent) })}
                {" · "}
                {topic.chats === 1
                  ? t("discover.trending.oneGroup", { n: topic.chats })
                  : t("discover.trending.groups", { n: topic.chats })}
              </span>
            </div>
            {topic.sample && (
              <div className="trend-sample dim" dir="auto"
                   title={t("discover.trending.openSample")}
                   onClick={() => openMessage(topic.sample!)}>
                <span className="src-title">{topic.sample.chat_title}</span>
                <span className="src-text" dir="auto">{topic.sample.text}</span>
              </div>
            )}
            <div className="trend-actions">
              <button className="btn ghost sm" onClick={() => runSearch(topic.term)}>{t("action.view")}</button>
              <button className="btn ghost sm" disabled={timelineBusy}
                      onClick={() => showTimeline(topic.term)}>
                {timelineBusy
                  ? <Ic.Spin size={13} className="spin" />
                  : <><Ic.Sparkles size={13} /> {t("discover.timeline.button")}</>}
              </button>
            </div>
          </div>
        ))}

        {(timeline || timelineBusy) && (
          <div className="timeline-panel">
            <div className="bm-head">
              <span className="badge">{t("discover.timeline.badge")}</span>
              <span className="dim" dir="auto">{timeline?.term ?? "…"}</span>
              <span style={{ flex: 1 }} />
              <button className="btn ghost sm" title={t("action.close")}
                      onClick={() => { setTimeline(null); setTimelineBusy(false); }}>
                <Ic.Close size={14} />
              </button>
            </div>
            {timelineBusy && <div className="side-note">{t("discover.timeline.analyzing")}</div>}
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
                       else toast(t("discover.toast.citationMissing", { n }), "err");
                     }} />
                <details className="ai-sources">
                  <summary>{t("discover.timeline.sources", { n: timeline.sources.length })}</summary>
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
        <SectionHead icon="Radio" title={t("discover.stories.title")}
                     note={t("discover.stories.note")} />
        {stories === null && <div className="side-note">{t("state.loading")}</div>}
        {stories !== null && stories.length === 0 && (
          <div className="side-note">{t("discover.stories.empty", { n: nDays })}</div>
        )}
        {stories?.map((s) => (
          <details key={s.key} className="story-card">
            <summary>
              <span className="badge">{t("discover.stories.badge", { g: s.chats, n: s.n })}</span>
              <span className="story-text" dir="auto">{s.sample_text.slice(0, 140)}</span>
            </summary>
            <div className="story-groups">
              {s.chat_titles.map((title) => (
                <span key={title} className="chip static" dir="auto">{title}</span>
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
        <SectionHead icon="HelpCircle"
                     title={questions?.length
                       ? t("discover.questions.titleCount", { n: questions.length })
                       : t("discover.questions.title")}
                     note={t("discover.questions.note")} />
        {questions !== null && questions.length > 0 && (
          <div className="q-actions">
            <button className="btn ghost sm" onClick={scanQuestions}>{t("discover.questions.scan")}</button>
            <span className="dim" style={{ fontSize: 11, alignSelf: "center" }}>
              {t("discover.questions.scanNote")}
            </span>
          </div>
        )}
        {questions === null && <div className="side-note">{t("state.loading")}</div>}
        {questions !== null && questions.length === 0 && (
          <div className="side-note">{t("discover.questions.empty")}</div>
        )}
        {questions?.map((q) => (
          <div key={`${q.chat_id}-${q.msg_id}`} className="q-row">
            <div className="q-main">
              <button className="q-text" dir="auto" title={t("action.viewConversation")}
                      onClick={() => openMessage(q)}>{q.text}</button>
              <div className="q-meta dim">
                <span dir="auto">{q.chat_title}</span> · <span>{(q.asked_at ?? "").slice(0, 10)}</span>
                {q.replies === 0 && q.followers === 0 && <span> · {t("discover.questions.noResponse")}</span>}
              </div>
            </div>
            {q.faq && (
              <details className="q-faq">
                <summary><Ic.Lightbulb size={14} /> {t("discover.questions.faqMatch")}</summary>
                <div dir="auto" dangerouslySetInnerHTML={{ __html: mdToHtml(q.faq.answer_md ?? "") }} />
              </details>
            )}
            <div className="q-acts">
              <button className="btn ghost sm" onClick={() => openMessage(q)}>{t("discover.questions.open")}</button>
              <button className="btn ghost sm" onClick={() => setQuestionStatus(q, "answered")}>
                <Ic.Check size={13} /> {t("discover.questions.markAnswered")}
              </button>
              <button className="btn ghost sm" onClick={() => setQuestionStatus(q, "ignored")}>{t("discover.questions.ignore")}</button>
            </div>
          </div>
        ))}

        {/* ---- Group activity ---- */}
        <SectionHead icon="ChartColumn" title={t("discover.activity.title")}
                     note={t("discover.activity.note")} />
        {activity === null && <div className="side-note">{t("state.loading")}</div>}
        {activity && activity.groups.length === 0 && (
          <div className="side-note">{t("discover.activity.empty")}</div>
        )}
        {activity?.groups.slice(0, 8).map((g) => (
          <button key={g.chat_id} className="act-row"
                  onClick={() => toggleGroup(g.chat_id)}
                  title={t("discover.activity.toggleTitle")}>
            <span className="g-title" dir="auto">{g.title}</span>
            <Spark daily={g.daily} />
            <span className="dim" style={{ fontSize: 11, flex: "none" }}>
              {t("discover.activity.stats", { n: nfmt(g.total), p: g.per_day })}
            </span>
          </button>
        ))}
        {activity && activity.groups.length > 8 && (
          <div className="side-note">{t("discover.activity.more", { n: activity.groups.length - 8 })}</div>
        )}
      </div>
    </div>
  );
}

function SectionHead({ icon, title, note }: { icon: IconName; title: string; note?: string }) {
  const C = Ic[icon];
  return (
    <div className="disc-section-head">
      <span className="nav-ic"><C size={16} /></span>
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

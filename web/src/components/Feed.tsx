/** The central message feed: infinite scroll, day separators, highlighting,
 *  empty states, and selection.
 *
 *  Performance contract: MessageCard is memoized and receives only stable
 *  props (message identity, booleans, a memoized regex, useCallback
 *  handlers) — a store update (toasts, polling, panel switches) never
 *  re-renders hundreds of cards. */
import { memo, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { useStore, type Store } from "../state/store";
import { useLang } from "../i18n";
import type { Message } from "../api/types";
import { dayKey, dayLabel, fmtTime, highlightRegex } from "../utils/format";
import { EmptyState } from "./EmptyState";
import { Ic } from "../design/icons";

function HighlightedText({ text, re }: { text: string; re: RegExp | null }) {
  if (!re) return <>{text}</>;
  const parts: (string | { m: string })[] = [];
  let last = 0;
  for (const match of text.matchAll(re)) {
    const idx = match.index ?? 0;
    if (idx > last) parts.push(text.slice(last, idx));
    parts.push({ m: match[0] });
    last = idx + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return (
    <>
      {parts.map((p, i) =>
        typeof p === "string" ? p : <mark key={i}>{p.m}</mark>,
      )}
    </>
  );
}

type Toast = Store["toast"];

const MessageCardImpl = ({ m, multi, re, active, onSelect, toast, t }: {
  m: Message;
  multi: boolean;
  re: RegExp | null;
  active: boolean;
  onSelect: (m: Message) => void;
  toast: Toast;
  t: ReturnType<typeof useLang>["t"];
}) => {
  const [starred, setStarred] = useState(m.bookmarked === 1);
  const [note, setNote] = useState<string | null>(m.bookmark_note ?? null);

  useEffect(() => {
    setStarred(m.bookmarked === 1);
    setNote(m.bookmark_note ?? null);
  }, [m.bookmarked, m.bookmark_note]);

  const toggleStar = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const next = !starred;
    setStarred(next);
    if (!next) setNote(null);
    try {
      if (next) {
        await api.bookmarkSet(m.chat_id, m.msg_id, note ?? "");
        toast(t("feed.marked"), "good");
      } else {
        await api.bookmarkDelete(m.chat_id, m.msg_id);
        toast(t("feed.unmarked"), "info");
      }
    } catch (err) {
      setStarred(!next);  // revert on failure - never fake success
      toast((err as Error).message, "err");
    }
  };

  return (
    <div className={`msg-card ${active ? "active" : ""}`} onClick={() => onSelect(m)}>
      <div className="msg-head">
        <span className="msg-sender" dir="auto">{m.sender_name || t("feed.unknown")}</span>
        <span className="msg-time">{fmtTime(m.date)}</span>
        {multi && <span className="msg-grp" dir="auto">{m.chat_title}</span>}
        {m.edited === 1 && (
          <span className="badge" title={t("feed.edited")}><Ic.Pencil size={10} /></span>
        )}
        {m.has_media === 1 && (
          <span className="badge" title={t("feed.hasImage")}><Ic.Image size={10} /></span>
        )}
        <button
          className={`star ${starred ? "on" : ""}`}
          title={starred ? t("feed.unmarkHint") : t("feed.markHint")}
          onClick={(e) => void toggleStar(e)}
        >
          {starred ? <Ic.Star size={13} fill="currentColor" /> : <Ic.Star size={13} />}
        </button>
      </div>
      <div className="msg-body" dir="auto">
        <HighlightedText text={m.text || ""} re={re} />
      </div>
    </div>
  );
};

const MessageCard = memo(MessageCardImpl);

function DaySep({ day }: { day: string }) {
  return (
    <div className="day-sep"><span>{dayLabel(day)}</span></div>
  );
}

export function Feed() {
  const {
    feed, mode, q, loading, hasMore, loadFeed,
    selection, selected, select, setRightTab,
    appState, setModal, wizardOpen, toast,
  } = useStore();
  const { t } = useLang();
  const scrollRef = useRef<HTMLDivElement>(null);
  const highlight = useMemo(() => (mode === "search" ? highlightRegex(q) : null), [mode, q]);
  const multi = selection.size !== 1;

  // stable handler identity: keeps every memoized card untouched when
  // unrelated store state changes
  const onSelect = useCallback((msg: Message) => {
    select(msg);
    setRightTab("details");
  }, [select, setRightTab]);

  // infinite scroll (browse) + jump button visibility
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    if (mode === "browse" && hasMore && !loading &&
        el.scrollTop + el.clientHeight > el.scrollHeight - 400) {
      // soft DOM cap: older history stays one click away, rendering stays fast
      if (feed.length < 3000) {
        void loadFeed(false);
      }
    }
  };

  // when a message is selected via AI citation, highlight + scroll to it
  useEffect(() => {
    if (selected && scrollRef.current) {
      const el = scrollRef.current.querySelector(
        `[data-key="${selected.chat_id}:${selected.msg_id}"]`,
      );
      el?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [selected]);

  const empty = feed.length === 0 && !loading;

  return (
    <div className="feed-col">
      <div className="feed" ref={scrollRef} onScroll={onScroll}>
        {loading && feed.length === 0 && (
          <div className="feed-skeleton">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="skel-msg">
                <div className="skel l1" /><div className="skel l2" /><div className="skel l3" />
              </div>
            ))}
          </div>
        )}

        {empty && mode === "search" && q && (
          <EmptyState
            icon="Search"
            title={t("feed.noResults")}
            hint={t("feed.noResultsHint", { q })}
          />
        )}
        {empty && mode === "browse" && (appState?.messages ?? 0) === 0 && !wizardOpen && (
          <EmptyState
            icon="Database"
            title={t("feed.archiveEmpty")}
            hint={t("feed.archiveEmptyHint")}
            action={<button className="btn primary" onClick={() => setModal("manage")}>{t("groups.manage")}</button>}
          />
        )}
        {empty && mode === "browse" && (appState?.messages ?? 0) > 0 && (
          <EmptyState
            icon="Layers"
            title={t("feed.noMatch")}
            hint={t("feed.noMatchHint")}
          />
        )}
        {empty && mode === "search" && !q && (
          <EmptyState
            icon="Search"
            title={t("feed.searchPrompt")}
            hint={t("feed.searchPromptHint")}
          />
        )}

        {(() => {
          let lastDay: string | null = null;
          return feed.flatMap((m): ReactNode[] => {
            const out: ReactNode[] = [];
            if (mode === "browse") {
              const day = dayKey(m.date);
              if (day !== lastDay) {
                out.push(<DaySep key={`d-${day}`} day={day} />);
                lastDay = day;
              }
            }
            out.push(
              <div key={`${m.chat_id}:${m.msg_id}`} data-key={`${m.chat_id}:${m.msg_id}`}>
                <MessageCard
                  m={m}
                  multi={multi}
                  re={highlight}
                  active={selected?.chat_id === m.chat_id && selected?.msg_id === m.msg_id}
                  onSelect={onSelect}
                  toast={toast}
                  t={t}
                />
              </div>,
            );
            return out;
          });
        })()}

        {loading && feed.length > 0 && (
          <div className="feed-loading">
            <span className="spinner" /> {t("feed.loadingOlder")}
          </div>
        )}
        {mode === "browse" && hasMore && !loading && (
          <div className="feed-more">
            {feed.length < 3000 ? (
              <button className="btn ghost sm" onClick={() => void loadFeed(false)}>{t("feed.loadOlder")}</button>
            ) : (
              <span className="fb-more">
                {t("feed.showingNewest", { n: feed.length.toLocaleString() })}
              </span>
            )}
          </div>
        )}
      </div>
      <JumpTop />
    </div>
  );
}

function JumpTop() {
  const { t } = useLang();
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const feed = ref.current?.parentElement?.querySelector(".feed");
    if (!feed) return;
    const upd = () => {
      const btn = ref.current;
      if (btn) btn.classList.toggle("show", feed.scrollTop > 600);
    };
    feed.addEventListener("scroll", upd);
    return () => feed.removeEventListener("scroll", upd);
  }, []);
  return (
    <button
      ref={ref}
      className="jump-top"
      title={t("feed.jumpLatest")}
      onClick={() => {
        const feed = ref.current?.parentElement?.querySelector(".feed");
        if (feed) feed.scrollTo({ top: 0, behavior: "smooth" });
      }}
    >
      <Ic.ArrowDownToLine size={17} />
    </button>
  );
}

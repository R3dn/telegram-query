/** The central message feed: infinite scroll, day separators, highlighting,
 *  empty states, and selection. */
import { useEffect, useMemo, useRef, type ReactNode } from "react";
import { useStore } from "../state/store";
import type { Message } from "../api/types";
import { dayKey, dayLabel, fmtTime, highlightRegex } from "../utils/format";
import { EmptyState } from "./EmptyState";

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

function MessageCard({ m, multi, re, active, onSelect }: {
  m: Message;
  multi: boolean;
  re: RegExp | null;
  active: boolean;
  onSelect: (m: Message) => void;
}) {
  const badges = (
    <>
      {m.edited === 1 && <span className="badge" title="edited">✎</span>}
      {m.has_media === 1 && <span className="badge" title="has image">🖼</span>}
    </>
  );
  return (
    <div className={`msg-card ${active ? "active" : ""}`} onClick={() => onSelect(m)}>
      <div className="msg-head">
        <span className="msg-sender" dir="auto">{m.sender_name || "unknown"}</span>
        <span className="msg-time">{fmtTime(m.date)}</span>
        {multi && <span className="msg-grp" dir="auto">{m.chat_title}</span>}
        {badges}
      </div>
      <div className="msg-body" dir="auto">
        <HighlightedText text={m.text || ""} re={re} />
      </div>
    </div>
  );
}

function DaySep({ day }: { day: string }) {
  return (
    <div className="day-sep"><span>{dayLabel(day)}</span></div>
  );
}

export function Feed() {
  const {
    feed, mode, q, loading, hasMore, loadFeed,
    selection, selected, select, setRightTab,
    appState, setModal, wizardOpen,
  } = useStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const highlight = useMemo(() => (mode === "search" ? highlightRegex(q) : null), [mode, q]);
  const multi = selection.size !== 1;

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
            icon="🔍"
            title="No results"
            hint={`Nothing matches “${q}” with the current filters. Try different wording, fewer filters, or alternative spellings.`}
          />
        )}
        {empty && mode === "browse" && (appState?.messages ?? 0) === 0 && !wizardOpen && (
          <EmptyState
            icon="🗄"
            title="Your archive is empty"
            hint="Track some groups and run your first sync to start building a searchable archive of your Telegram messages."
            action={<button className="btn primary" onClick={() => setModal("manage")}>Manage groups</button>}
          />
        )}
        {empty && mode === "browse" && (appState?.messages ?? 0) > 0 && (
          <EmptyState
            icon="🗂"
            title="No messages match"
            hint="No messages match the current filters. Widen the date range or clear a filter."
          />
        )}
        {empty && mode === "search" && !q && (
          <EmptyState
            icon="⌨"
            title="Search your archive"
            hint="Type above and press Enter. Separate alternative words with | — e.g.  offer|عرض"
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
                  onSelect={(msg) => { select(msg); setRightTab("details"); }}
                />
              </div>,
            );
            return out;
          });
        })()}

        {loading && feed.length > 0 && (
          <div className="feed-loading"><span className="spinner" /> loading older messages…</div>
        )}
        {mode === "browse" && hasMore && !loading && (
          <div className="feed-more">
            {feed.length < 3000 ? (
              <button className="btn ghost sm" onClick={() => void loadFeed(false)}>Load older messages</button>
            ) : (
              <span className="fb-more">
                Showing the newest {feed.length.toLocaleString()} messages —
                narrow the filters to explore deeper history
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
      title="Jump to latest"
      onClick={() => {
        const feed = ref.current?.parentElement?.querySelector(".feed");
        if (feed) feed.scrollTo({ top: 0, behavior: "smooth" });
      }}
    >
      ↑
    </button>
  );
}

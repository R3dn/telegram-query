/** Bookmarks workspace (v0.4): starred messages + private notes.

Every row references the original archived message; "jump" opens it in the
feed details panel, and the Telegram link opens the original when one
exists (public groups / supergroups only - never fabricated). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { BookmarkRow } from "../api/types";
import { fmtDateTime } from "../utils/format";
import { EmptyState } from "./EmptyState";

export function BookmarksView() {
  const { select, setRightTab, toast } = useStore();
  const [rows, setRows] = useState<BookmarkRow[] | null>(null);
  const [q, setQ] = useState("");

  const load = async (query = q) => {
    try {
      setRows(await api.bookmarks(query.trim() ? { q: query.trim() } : {}));
    } catch (e) {
      toast((e as Error).message, "err");
      setRows([]);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => void load(q), q ? 250 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const unstar = async (b: BookmarkRow) => {
    try {
      await api.bookmarkDelete(b.chat_id, b.msg_id);
      setRows((r) => (r ?? []).filter(
        (x) => !(x.chat_id === b.chat_id && x.msg_id === b.msg_id)));
      toast("Bookmark removed", "info");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const jump = (b: BookmarkRow) => {
    select({
      chat_id: b.chat_id, msg_id: b.msg_id, date: b.date,
      sender_id: b.sender_id, sender_name: b.sender_name, text: b.text,
      has_media: b.has_media, edited: b.edited, chat_title: b.chat_title,
      bookmarked: 1, bookmark_note: b.note, tg_link: b.tg_link,
    });
    setRightTab("details");
    if (window.matchMedia("(max-width: 1100px)").matches) {
      document.body.classList.add("tgq-right-open");
    }
  };

  const copyLink = async (b: BookmarkRow) => {
    if (!b.tg_link) return;
    try {
      await navigator.clipboard.writeText(b.tg_link);
      toast("Link copied", "good");
    } catch {
      toast("Copy failed", "err");
    }
  };

  const exportAs = async (format: "md" | "json") => {
    try {
      const name = await api.exportBookmarks(format);
      toast(`Exported: ${name}`, "good");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">Bookmarks</h2>
        <input
          className="input"
          style={{ maxWidth: 300 }}
          placeholder="Search notes and messages…"
          value={q}
          dir="auto"
          onChange={(e) => setQ(e.target.value)}
        />
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" onClick={() => void exportAs("md")}>Export .md</button>
        <button className="btn ghost sm" onClick={() => void exportAs("json")}>Export .json</button>
      </div>

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
            icon="⭐"
            title={q ? "No bookmarks match" : "No bookmarks yet"}
            hint={q
              ? "Nothing matches that search. Try a different word."
              : "Star messages in the feed (or the Details panel) to keep them here. Notes stay on this machine and are never sent to the AI."}
          />
        )}
        {rows !== null && rows.map((b) => (
          <div key={`${b.chat_id}:${b.msg_id}`} className="bm-card">
            <div className="bm-head">
              <button className="star on" title="Remove bookmark"
                      onClick={() => void unstar(b)}>★</button>
              <span className="bm-grp" dir="auto">{b.chat_title}</span>
              <span className="bm-date">{fmtDateTime(b.date)} UTC</span>
              <span className="bm-sender" dir="auto">{b.sender_name || "unknown"}</span>
              <span style={{ flex: 1 }} />
              <button className="btn ghost sm" onClick={() => jump(b)}>Jump</button>
              {b.tg_link && (
                <>
                  <button className="btn ghost sm" title="Open the original in Telegram"
                          onClick={() => window.open(b.tg_link!, "_blank", "noopener")}>
                    Telegram ↗
                  </button>
                  <button className="btn ghost sm" onClick={() => void copyLink(b)}>Copy link</button>
                </>
              )}
            </div>
            <div className="bm-text" dir="auto">{b.text || "[no text / media only]"}</div>
            {b.note && <div className="bm-note" dir="auto">📝 {b.note}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

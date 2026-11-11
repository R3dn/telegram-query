/** Bookmarks workspace (v1.0 design): starred messages + private notes.

Every row references the original archived message; "jump" opens it in the
feed details panel, and the Telegram link opens the original when one
exists (public groups / supergroups only - never fabricated). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { BookmarkRow } from "../api/types";
import { fmtDateTime } from "../utils/format";
import { EmptyState } from "./EmptyState";
import { Ic } from "../design/icons";

export function BookmarksView() {
  const { select, setRightTab, toast } = useStore();
  const { t } = useLang();
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
    const timer = setTimeout(() => void load(q), q ? 250 : 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const unstar = async (b: BookmarkRow) => {
    try {
      await api.bookmarkDelete(b.chat_id, b.msg_id);
      setRows((r) => (r ?? []).filter(
        (x) => !(x.chat_id === b.chat_id && x.msg_id === b.msg_id)));
      toast(t("feed.unmarked"), "info");
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
      toast(t("bookmarks.linkCopied"), "good");
    } catch {
      toast(t("bookmarks.copyFailed"), "err");
    }
  };

  const exportAs = async (format: "md" | "json") => {
    try {
      const name = await api.exportBookmarks(format);
      toast(t("bookmarks.exportDone", { name }), "good");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">{t("bookmarks.title")}</h2>
        <input
          className="input"
          style={{ maxWidth: 300 }}
          placeholder={t("bookmarks.searchPlaceholder")}
          value={q}
          dir="auto"
          onChange={(e) => setQ(e.target.value)}
        />
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" onClick={() => void exportAs("md")}>
          <Ic.FileDown size={13} /> {t("bookmarks.exportMd")}
        </button>
        <button className="btn ghost sm" onClick={() => void exportAs("json")}>
          <Ic.FileDown size={13} /> {t("bookmarks.exportJson")}
        </button>
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
            icon="Star"
            title={q ? t("bookmarks.noMatchTitle") : t("bookmarks.emptyTitle")}
            hint={q
              ? t("bookmarks.noMatchHint")
              : t("bookmarks.emptyHint")}
          />
        )}
        {rows !== null && rows.map((b) => (
          <div key={`${b.chat_id}:${b.msg_id}`} className="bm-card">
            <div className="bm-head">
              <button className="star on" title={t("feed.unmarkHint")}
                      onClick={() => void unstar(b)}>
                <Ic.Star size={14} fill="currentColor" />
              </button>
              <span className="bm-grp" dir="auto">{b.chat_title}</span>
              <span className="bm-date">{fmtDateTime(b.date)} UTC</span>
              <span className="bm-sender" dir="auto">{b.sender_name || t("feed.unknown")}</span>
              <span style={{ flex: 1 }} />
              <button className="btn ghost sm" onClick={() => jump(b)}>
                <Ic.ArrowRight size={13} /> {t("bookmarks.jump")}
              </button>
              {b.tg_link && (
                <>
                  <button className="btn ghost sm" title={t("action.openTelegram")}
                          onClick={() => window.open(b.tg_link!, "_blank", "noopener")}>
                    {t("bookmarks.telegram")} <Ic.ExternalLink size={13} />
                  </button>
                  <button className="btn ghost sm" onClick={() => void copyLink(b)}>
                    <Ic.Link2 size={13} /> {t("bookmarks.copyLink")}
                  </button>
                </>
              )}
            </div>
            <div className="bm-text" dir="auto">{b.text || t("details.noText")}</div>
            {b.note && (
              <div className="bm-note" dir="auto">
                <Ic.NotepadText size={14} />
                <span className="bm-note-text">{b.note}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

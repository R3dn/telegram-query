/** Right panel "Details" tab: full message, metadata, private note,
 *  bookmark star, conversation reconstruction (v0.7), and Telegram
 *  deep links (v0.4). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { fmtDateTime } from "../utils/format";
import { ConversationBlock } from "./ConversationBlock";

export function DetailsPanel() {
  const { selected, setFilters, loadFeed, toast, senders, select } = useStore();
  const [copied, setCopied] = useState(false);
  const [note, setNote] = useState("");
  const [starred, setStarred] = useState(false);
  const [savingNote, setSavingNote] = useState(false);

  useEffect(() => {
    setNote(selected?.bookmark_note ?? "");
    setStarred(selected?.bookmarked === 1);
  }, [selected?.chat_id, selected?.msg_id, selected?.bookmarked,
      selected?.bookmark_note]);

  if (!selected) {
    return (
      <div className="details-empty">
        <div className="ic">💬</div>
        <p>Select a message in the feed to see its details here.</p>
      </div>
    );
  }
  const m = selected;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(m.text || "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast("Copy failed", "err");
    }
  };

  const copyLink = async () => {
    if (!m.tg_link) return;
    try {
      await navigator.clipboard.writeText(m.tg_link);
      toast("Message link copied", "good");
    } catch {
      toast("Copy failed", "err");
    }
  };

  const toggleStar = async () => {
    const next = !starred;
    setStarred(next);
    try {
      if (next) {
        await api.bookmarkSet(m.chat_id, m.msg_id, note);
        select({ ...m, bookmarked: 1, bookmark_note: note });
        toast("Bookmarked ⭐", "good");
      } else {
        await api.bookmarkDelete(m.chat_id, m.msg_id);
        select({ ...m, bookmarked: 0, bookmark_note: null });
        toast("Bookmark removed", "info");
      }
    } catch (e) {
      setStarred(!next);
      toast((e as Error).message, "err");
    }
  };

  const saveNote = async () => {
    setSavingNote(true);
    try {
      if (!starred) {
        // saving a note stars the message (a note without a bookmark has
        // nowhere to live); the star is honest about it
        await api.bookmarkSet(m.chat_id, m.msg_id, note);
        setStarred(true);
        select({ ...m, bookmarked: 1, bookmark_note: note });
      } else {
        await api.bookmarkSet(m.chat_id, m.msg_id, note);
        select({ ...m, bookmark_note: note });
      }
      toast("Note saved", "good");
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setSavingNote(false);
    }
  };

  const filterBySender = () => {
    if (!m.sender_name) return;
    setFilters({ sender: m.sender_name });
    if (!senders.some((s) => s.sender_name === m.sender_name)) {
      toast("Filtering by sender", "info");
    }
    void loadFeed(true);
  };

  return (
    <div className="details">
      <div className="detail-text" dir="auto">{m.text || "[no text / media only]"}</div>

      <div className="detail-meta">
        <div className="meta-row"><span>Group</span><b dir="auto">{m.chat_title}</b></div>
        <div className="meta-row"><span>Date</span><b>{fmtDateTime(m.date)} UTC</b></div>
        <div className="meta-row"><span>Sender</span><b dir="auto">{m.sender_name || "unknown"}</b></div>
        {m.chat_id != null && (
          <div className="meta-row"><span>ID</span><b>{m.chat_id} / {m.msg_id}</b></div>
        )}
        {m.edited === 1 && <div className="meta-row"><span>Edited</span><b>yes</b></div>}
        {m.has_media === 1 && <div className="meta-row"><span>Media</span><b>image (not stored locally)</b></div>}
      </div>

      <div className="detail-note">
        <ConversationBlock m={m} />
      </div>

      <div className="detail-note">
        <div className="side-head">
          <span className="label">Private note</span>
          <button className={`star ${starred ? "on" : ""}`}
                  title={starred ? "Remove bookmark" : "Bookmark this message"}
                  onClick={() => void toggleStar()}>
            {starred ? "★ bookmarked" : "☆ bookmark"}
          </button>
        </div>
        <textarea
          className="input"
          rows={3}
          dir="auto"
          placeholder="Your note (Arabic/English, stays on this machine, never sent to AI)…"
          value={note}
          maxLength={4000}
          onChange={(e) => setNote(e.target.value)}
        />
        <div className="detail-note-actions">
          <button className="btn ghost sm" disabled={savingNote} onClick={() => void saveNote()}>
            {savingNote ? "Saving…" : "Save note"}
          </button>
          <span className="dim" style={{ fontSize: 12 }}>
            {starred ? "Shows in Bookmarks" : "Saving stars the message"}
          </span>
        </div>
      </div>

      <div className="detail-actions">
        <button className="btn ghost sm" onClick={copy}>{copied ? "Copied ✓" : "Copy text"}</button>
        {m.tg_link ? (
          <>
            <button className="btn ghost sm" title="Open the original in Telegram"
                    onClick={() => window.open(m.tg_link!, "_blank", "noopener")}>
              Open in Telegram ↗
            </button>
            <button className="btn ghost sm" onClick={() => void copyLink()}>Copy message link</button>
          </>
        ) : (
          <span className="dim" style={{ fontSize: 12, alignSelf: "center" }}
                title="Public groups and supergroups have per-message links; basic groups don't. We never fabricate URLs.">
            no Telegram link for this chat
          </span>
        )}
        {m.sender_name && (
          <button className="btn ghost sm" onClick={filterBySender}>Messages from this sender</button>
        )}
      </div>
    </div>
  );
}

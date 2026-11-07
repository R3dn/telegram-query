/** Right panel "Details" tab: full message, metadata, and quick actions. */
import { useState } from "react";
import { useStore } from "../state/store";
import { fmtDateTime } from "../utils/format";

export function DetailsPanel() {
  const { selected, setFilters, loadFeed, toast, senders } = useStore();
  const [copied, setCopied] = useState(false);

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

      <div className="detail-actions">
        <button className="btn ghost sm" onClick={copy}>{copied ? "Copied ✓" : "Copy text"}</button>
        {m.sender_name && (
          <button className="btn ghost sm" onClick={filterBySender}>Messages from this sender</button>
        )}
      </div>
    </div>
  );
}

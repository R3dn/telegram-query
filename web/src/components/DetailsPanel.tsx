/** Right panel "Details" tab: full message, metadata, private note,
 *  bookmark star, conversation reconstruction (v0.7), the Evidence
 *  Explorer - everything that references this message (v0.8) - and
 *  Telegram deep links (v0.4). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { fmtDateTime, statusTone } from "../utils/format";
import type { EvidenceResponse } from "../api/types";
import { ConversationBlock } from "./ConversationBlock";

export function DetailsPanel() {
  const { selected, setFilters, loadFeed, toast, senders, select,
          setMode, setEvidenceFocus } = useStore();
  const [copied, setCopied] = useState(false);
  const [note, setNote] = useState("");
  const [starred, setStarred] = useState(false);
  const [savingNote, setSavingNote] = useState(false);
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);

  useEffect(() => {
    setNote(selected?.bookmark_note ?? "");
    setStarred(selected?.bookmarked === 1);
  }, [selected?.chat_id, selected?.msg_id, selected?.bookmarked,
      selected?.bookmark_note]);

  // Evidence Explorer: load the reverse-citation set for the selection
  useEffect(() => {
    if (!selected) {
      setEvidence(null);
      return;
    }
    let dead = false;
    const load = async () => {
      try {
        const ev = await api.evidence(selected.chat_id, selected.msg_id);
        if (!dead) setEvidence(ev);
      } catch {
        if (!dead) setEvidence(null);
      }
    };
    void load();
    return () => { dead = true; };
  }, [selected?.chat_id, selected?.msg_id]);

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

      <EvidenceSection ev={evidence} setMode={setMode}
                       setEvidenceFocus={setEvidenceFocus} />

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

/** Evidence Explorer (v0.8): everything that references the selected
 *  message - deals, decisions, briefs, digests, alerts, FAQs, entities -
 *  plus its thread. Every record deep-links into its view. */
function EvidenceSection({ ev, setMode, setEvidenceFocus }: {
  ev: EvidenceResponse | null;
  setMode: (m: "deals" | "decisions" | "research" | "digests" | "alerts"
    | "faqs" | "entities" | "browse" | "search") => void;
  setEvidenceFocus: (f: { kind: string; id: number } | null) => void;
}) {
  if (!ev) return null;
  const r = ev.references;
  const total = ev.total;

  const go = (kind: string, id: number, mode: Parameters<typeof setMode>[0]) => {
    setEvidenceFocus({ kind, id });
    setMode(mode);
  };

  return (
    <div className="detail-note evidence">
      <div className="side-head">
        <span className="label">Evidence</span>
        <span className="dim" style={{ fontSize: 12 }}>
          {total === 0 ? "nothing references this message"
            : `${total} reference${total === 1 ? "" : "s"}`}
        </span>
      </div>

      {r.deals.length > 0 && (
        <div className="ev-group">
          <span className="label">Deals ({r.deals.length})</span>
          {r.deals.map((d) => (
            <div key={`d${d.id}`} className="src-row" dir="auto">
              <span className="src-title">{d.title}</span>
              <span className={`badge ${statusTone(d.derived_status)}`}>
                {d.derived_status}
              </span>
              <button className="link"
                      onClick={() => go("deal", d.id, "deals")}>View</button>
            </div>
          ))}
        </div>
      )}

      {r.decisions.length > 0 && (
        <div className="ev-group">
          <span className="label">Decisions ({r.decisions.length})</span>
          {r.decisions.map((d, i) => (
            <div key={`dec${d.id}-${i}`} className="src-row" dir="auto">
              <span className="src-title">{d.title}</span>
              <span className="badge" title={d.as === "followup"
                ? "this message is a follow-up about the decision"
                : "this message states the decision"}>
                {d.as}
              </span>
              <span className={`badge ${statusTone(d.derived_status)}`}>
                {d.derived_status}
              </span>
              <button className="link"
                      onClick={() => go("decision", d.id, "decisions")}>
                View
              </button>
            </div>
          ))}
        </div>
      )}

      {r.briefs.length > 0 && (
        <div className="ev-group">
          <span className="label">Research briefs ({r.briefs.length})</span>
          {r.briefs.map((b) => (
            <div key={`b${b.id}-${b.version}`} className="src-row" dir="auto">
              <span className="src-title">{b.question}</span>
              <span className="src-date">v{b.version}</span>
              <button className="link"
                      onClick={() => go("brief", b.id, "research")}>View</button>
            </div>
          ))}
        </div>
      )}

      {r.digests.length > 0 && (
        <div className="ev-group">
          <span className="label">Digests ({r.digests.length})</span>
          {r.digests.map((g) => (
            <div key={`g${g.id}`} className="src-row" dir="auto">
              <span className="src-title">{g.period_start} → {g.period_end}</span>
              <button className="link"
                      onClick={() => go("digest", g.id, "digests")}>View</button>
            </div>
          ))}
        </div>
      )}

      {r.alerts.length > 0 && (
        <div className="ev-group">
          <span className="label">Alerts ({r.alerts.length})</span>
          {r.alerts.map((a) => (
            <div key={`a${a.id}`} className="src-row" dir="auto">
              <span className="src-title">{a.watchlist_name}</span>
              <span className="src-date">{a.matched_term}</span>
              <button className="link"
                      onClick={() => go("alert", a.id, "alerts")}>View</button>
            </div>
          ))}
        </div>
      )}

      {r.faqs.length > 0 && (
        <div className="ev-group">
          <span className="label">FAQs ({r.faqs.length})</span>
          {r.faqs.map((f, i) => (
            <div key={`f${f.id}-${i}`} className="src-row" dir="auto">
              <span className="src-title">{f.question}</span>
              <span className="badge">{f.as}</span>
              <button className="link"
                      onClick={() => go("faq", f.id, "faqs")}>View</button>
            </div>
          ))}
        </div>
      )}

      {r.entities.length > 0 && (
        <div className="ev-group">
          <span className="label">Entities ({r.entities.length})</span>
          {r.entities.map((e) => (
            <div key={`e${e.id}`} className="src-row" dir="auto">
              <span className="src-title">{e.name}</span>
              <span className="badge">{e.kind}</span>
              <button className="link"
                      onClick={() => go("entity", e.id, "entities")}>View</button>
            </div>
          ))}
        </div>
      )}

      {ev.thread.parent && (
        <div className="ev-group">
          <span className="label">Reply to</span>
          <div className="src-row" dir="auto">
            <span className="src-text">
              {(ev.thread.parent.text ?? "[no text]").slice(0, 140)}
            </span>
          </div>
        </div>
      )}
      {ev.thread.replies.length > 0 && (
        <div className="ev-group">
          <span className="label">Direct replies ({ev.thread.replies.length})</span>
          {ev.thread.replies.map((m) => (
            <div key={`${m.chat_id}-${m.msg_id}`} className="src-row" dir="auto">
              <span className="src-text">
                {(m.text ?? "[no text]").slice(0, 140)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

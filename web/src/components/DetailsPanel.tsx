/** Right panel "Details" tab: full message, metadata, private note,
 *  bookmark star, conversation reconstruction, the Evidence Explorer
 *  (everything that references this message), and Telegram deep links. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import { fmtDateTime, statusTone } from "../utils/format";
import type { EvidenceResponse } from "../api/types";
import { ConversationBlock } from "./ConversationBlock";
import { Ic } from "../design/icons";

export function DetailsPanel() {
  const { selected, setFilters, loadFeed, toast, senders, select,
          setMode, setEvidenceFocus } = useStore();
  const { t } = useLang();
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
        <div className="ic"><Ic.MessageSquare size={22} /></div>
        <p>{t("details.emptyHint")}</p>
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
      toast(t("details.copyFailed"), "err");
    }
  };

  const copyLink = async () => {
    if (!m.tg_link) return;
    try {
      await navigator.clipboard.writeText(m.tg_link);
      toast(t("details.linkCopied"), "good");
    } catch {
      toast(t("details.copyFailed"), "err");
    }
  };

  const toggleStar = async () => {
    const next = !starred;
    setStarred(next);
    try {
      if (next) {
        await api.bookmarkSet(m.chat_id, m.msg_id, note);
        select({ ...m, bookmarked: 1, bookmark_note: note });
        toast(t("feed.marked"), "good");
      } else {
        await api.bookmarkDelete(m.chat_id, m.msg_id);
        select({ ...m, bookmarked: 0, bookmark_note: null });
        toast(t("feed.unmarked"), "info");
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
      toast(t("details.noteSaved"), "good");
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
      toast(t("details.filterBySender"), "info");
    }
    void loadFeed(true);
  };

  return (
    <div className="details">
      <div className="detail-text" dir="auto">{m.text || t("details.noText")}</div>

      <div className="detail-meta">
        <div className="meta-row"><span>{t("details.group")}</span><b dir="auto">{m.chat_title}</b></div>
        <div className="meta-row"><span>{t("details.date")}</span><b>{fmtDateTime(m.date)} UTC</b></div>
        <div className="meta-row"><span>{t("details.sender")}</span><b dir="auto">{m.sender_name || t("feed.unknown")}</b></div>
        {m.chat_id != null && (
          <div className="meta-row"><span>{t("details.id")}</span><b>{m.chat_id} / {m.msg_id}</b></div>
        )}
        {m.edited === 1 && <div className="meta-row"><span>{t("details.edited")}</span><b>{t("details.yes")}</b></div>}
        {m.has_media === 1 && (
          <div className="meta-row"><span>{t("details.media")}</span><b>{t("details.mediaNote")}</b></div>
        )}
      </div>

      <div className="detail-note">
        {/* key: the conversation block is opened per message; without the
         * key, selecting a different message keeps the previous message's
         * fetched thread (with the wrong target highlighted) on screen. */}
        <ConversationBlock key={`${m.chat_id}:${m.msg_id}`} m={m} />
      </div>

      <EvidenceSection ev={evidence} setMode={setMode}
                       setEvidenceFocus={setEvidenceFocus} />

      <div className="detail-note">
        <div className="side-head">
          <span className="label">{t("details.noteTitle")}</span>
          <button className={`star ${starred ? "on" : ""}`}
                  title={starred ? t("feed.unmarkHint") : t("feed.markHint")}
                  onClick={() => void toggleStar()}>
            {starred
              ? <><Ic.Star size={12} fill="currentColor" /> {t("details.bookmarked")}</>
              : <><Ic.Star size={12} /> {t("details.bookmark")}</>}
          </button>
        </div>
        <textarea
          className="input"
          rows={3}
          dir="auto"
          placeholder={t("details.notePlaceholder")}
          value={note}
          maxLength={4000}
          onChange={(e) => setNote(e.target.value)}
        />
        <div className="detail-note-actions">
          <button className="btn ghost sm" disabled={savingNote} onClick={() => void saveNote()}>
            {savingNote
              ? <><Ic.Spin size={13} className="spin" /> {t("details.noteSaving")}</>
              : <Ic.Save size={13} />}
            {" "}{savingNote ? "" : t("details.noteSave")}
          </button>
          <span className="dim" style={{ fontSize: 12 }}>
            {starred ? t("details.noteInBookmarks") : t("details.noteStarsHint")}
          </span>
        </div>
      </div>

      <div className="detail-actions">
        <button className="btn ghost sm" onClick={copy}>
          {copied ? <><Ic.Check size={13} /> {t("action.copied")}</> : <><Ic.Copy size={13} /> {t("action.copy")}</>}
        </button>
        {m.tg_link ? (
          <>
            <button className="btn ghost sm" title={t("action.openTelegram")}
                    onClick={() => window.open(m.tg_link!, "_blank", "noopener")}>
              <Ic.ExternalLink size={13} /> {t("action.openTelegram")}
            </button>
            <button className="btn ghost sm" onClick={() => void copyLink()}>
              <Ic.Link2 size={13} /> {t("details.copyLink")}
            </button>
          </>
        ) : (
          <span className="dim" style={{ fontSize: 12, alignSelf: "center" }}
                title={t("details.noLinkHint")}>
            {t("details.noLink")}
          </span>
        )}
        {m.sender_name && (
          <button className="btn ghost sm" onClick={filterBySender}>
            <Ic.User size={13} /> {t("details.bySender")}
          </button>
        )}
      </div>
    </div>
  );
}

/** Evidence Explorer: everything that references the selected message -
 *  deals, decisions, briefs, digests, alerts, FAQs, entities - plus its
 *  thread. Every record deep-links into its view. */
function EvidenceSection({ ev, setMode, setEvidenceFocus }: {
  ev: EvidenceResponse | null;
  setMode: (m: "deals" | "decisions" | "research" | "digests" | "alerts"
    | "faqs" | "entities" | "browse" | "search") => void;
  setEvidenceFocus: (f: { kind: string; id: number } | null) => void;
}) {
  const { t } = useLang();
  if (!ev) return null;
  const r = ev.references;
  const total = ev.total;

  const go = (kind: string, id: number, mode: Parameters<typeof setMode>[0]) => {
    setEvidenceFocus({ kind, id });
    setMode(mode);
  };

  const group = (label: React.ReactNode, rows: React.ReactNode) => (
    <div className="ev-group">
      <span className="label">{label}</span>
      {rows}
    </div>
  );

  return (
    <div className="detail-note evidence">
      <div className="side-head">
        <span className="label">{t("ev.title")}</span>
        <span className="dim" style={{ fontSize: 12 }}>
          {total === 0 ? t("ev.none") : t("ev.refs", { n: total })}
        </span>
      </div>

      {r.deals.length > 0 &&
        group(t("ev.deals", { n: r.deals.length }),
          r.deals.map((d) => (
            <div key={`d${d.id}`} className="src-row" dir="auto">
              <span className="src-title">{d.title}</span>
              <span className={`badge ${statusTone(d.derived_status)}`}>
                {d.derived_status}
              </span>
              <button className="link"
                      onClick={() => go("deal", d.id, "deals")}>{t("action.view")}</button>
            </div>
          )))}

      {r.decisions.length > 0 &&
        group(t("ev.decisions", { n: r.decisions.length }),
          r.decisions.map((d, i) => (
            <div key={`dec${d.id}-${i}`} className="src-row" dir="auto">
              <span className="src-title">{d.title}</span>
              <span className="badge" title={d.as === "followup"
                ? t("ev.asFollowup") : t("ev.asDecision")}>
                {d.as}
              </span>
              <span className={`badge ${statusTone(d.derived_status)}`}>
                {d.derived_status}
              </span>
              <button className="link"
                      onClick={() => go("decision", d.id, "decisions")}>
                {t("action.view")}
              </button>
            </div>
          )))}

      {r.briefs.length > 0 &&
        group(t("ev.briefs", { n: r.briefs.length }),
          r.briefs.map((b) => (
            <div key={`b${b.id}-${b.version}`} className="src-row" dir="auto">
              <span className="src-title">{b.question}</span>
              <span className="src-date">v{b.version}</span>
              <button className="link"
                      onClick={() => go("brief", b.id, "research")}>{t("action.view")}</button>
            </div>
          )))}

      {r.digests.length > 0 &&
        group(t("ev.digests", { n: r.digests.length }),
          r.digests.map((g) => (
            <div key={`g${g.id}`} className="src-row" dir="auto">
              <span className="src-title">{g.period_start.slice(0, 10)} <Ic.ArrowRight size={10} /> {g.period_end.slice(0, 10)}</span>
              <button className="link"
                      onClick={() => go("digest", g.id, "digests")}>{t("action.view")}</button>
            </div>
          )))}

      {r.alerts.length > 0 &&
        group(t("ev.alerts", { n: r.alerts.length }),
          r.alerts.map((a) => (
            <div key={`a${a.id}`} className="src-row" dir="auto">
              <span className="src-title">{a.watchlist_name}</span>
              <span className="src-date">{a.matched_term}</span>
              <button className="link"
                      onClick={() => go("alert", a.id, "alerts")}>{t("action.view")}</button>
            </div>
          )))}

      {r.faqs.length > 0 &&
        group(t("ev.faqs", { n: r.faqs.length }),
          r.faqs.map((f, i) => (
            <div key={`f${f.id}-${i}`} className="src-row" dir="auto">
              <span className="src-title">{f.question}</span>
              <span className="badge">{f.as}</span>
              <button className="link"
                      onClick={() => go("faq", f.id, "faqs")}>{t("action.view")}</button>
            </div>
          )))}

      {r.entities.length > 0 &&
        group(t("ev.entities", { n: r.entities.length }),
          r.entities.map((e) => (
            <div key={`e${e.id}`} className="src-row" dir="auto">
              <span className="src-title">{e.name}</span>
              <span className="badge">{e.kind}</span>
              <button className="link"
                      onClick={() => go("entity", e.id, "entities")}>{t("action.view")}</button>
            </div>
          )))}

      {ev.thread.parent &&
        group(t("ev.replyTo"),
          <div className="src-row" dir="auto">
            <span className="src-text">
              {(ev.thread.parent.text ?? t("details.noText")).slice(0, 140)}
            </span>
          </div>)}
      {ev.thread.replies.length > 0 &&
        group(t("ev.directReplies", { n: ev.thread.replies.length }),
          ev.thread.replies.map((m) => (
            <div key={`${m.chat_id}-${m.msg_id}`} className="src-row" dir="auto">
              <span className="src-text">
                {(m.text ?? t("details.noText")).slice(0, 140)}
              </span>
            </div>
          )))}
    </div>
  );
}

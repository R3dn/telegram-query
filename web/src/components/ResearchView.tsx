/** Research workspace (v0.5): ask a question, get a saved, cited,
 *  re-runnable brief. Versions preserve history; staleness is computed
 *  deterministically (never by the LLM). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { Brief } from "../api/types";
import { mdToHtml } from "../utils/markdown";
import { EmptyState } from "./EmptyState";

export function ResearchView() {
  const { appState, toast, groups, jobs, selection, toggleGroup } = useStore();
  const [briefs, setBriefs] = useState<Brief[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [question, setQuestion] = useState("");
  const [scopeDays, setScopeDays] = useState<"all" | "30d" | "90d" | "custom">("all");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const load = async () => {
    try {
      const list = await api.briefs();
      setBriefs(list);
      setSelectedId((cur) => cur ?? list[0]?.id ?? null);
    } catch (e) {
      toast((e as Error).message, "err");
      setBriefs([]);
    }
  };

  useEffect(() => { void load(); }, []);

  // a fresh generation lands when the brief job completes
  const lastDone = jobs?.last_done;
  useEffect(() => {
    if (lastDone?.name === "brief") void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastDone?.finished_at]);

  const creating = jobs?.running && jobs?.name === "brief";

  const create = async () => {
    const qt = question.trim();
    if (!qt || creating) return;
    const days: Record<string, [string, string | null]> = {
      "30d": [new Date(Date.now() - 29 * 864e5).toISOString().slice(0, 10), null],
      "90d": [new Date(Date.now() - 89 * 864e5).toISOString().slice(0, 10), null],
    };
    const r = await api.briefCreate({
      question: qt,
      chat_ids: [...selection],
      date_from: scopeDays === "custom" ? from || null : days[scopeDays]?.[0] ?? null,
      date_to: scopeDays === "custom" ? to || null : null,
    }).catch((e) => {
      toast((e as Error).message, "err");
      return null;
    });
    if (r) {
      toast("Research queued - watch Jobs for progress", "info");
      setQuestion("");
      setSelectedId(r.id);
    }
  };

  const selected = briefs?.find((b) => b.id === selectedId) ?? null;

  if (appState && !appState.ai_configured) {
    return (
      <div className="feed-col">
        <EmptyState icon="🔬" title="Research needs an AI provider"
                    hint="Configure AI_API_KEY in Settings to generate evidence-linked research briefs. Everything stays local - only the retrieved excerpts are sent to your provider." />
      </div>
    );
  }

  return (
    <div className="feed-col research-col">
      <div className="bm-bar research-form">
        <textarea className="input" rows={2} placeholder="Research question… e.g. Summarize everything about kubernetes migration · ما كل النقاشات حول الترقية؟"
                  dir="auto" value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault();
                      void create();
                    }
                  }} />
        <div className="research-ctrl">
          <select className="input" value={scopeDays} title="Date scope"
                  onChange={(e) => setScopeDays(e.target.value as typeof scopeDays)}>
            <option value="all">All time</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="custom">Custom…</option>
          </select>
          {scopeDays === "custom" && (
            <span className="date-range">
              <input type="date" className="input" style={{ width: 130 }} value={from}
                     onChange={(e) => setFrom(e.target.value)} />
              <span>→</span>
              <input type="date" className="input" style={{ width: 130 }} value={to}
                     onChange={(e) => setTo(e.target.value)} />
            </span>
          )}
          <button className="btn primary sm" disabled={!question.trim() || creating}
                  onClick={() => void create()}>
            {creating ? "Working…" : "Research it"}
          </button>
        </div>
      </div>

      <div className="research-body">
        <aside className="brief-list">
          <div className="side-head"><span className="label">Briefs</span></div>
          {briefs === null && <div className="side-note">loading…</div>}
          {briefs?.length === 0 && (
            <div className="side-note">No briefs yet - ask your first question above.</div>
          )}
          {briefs?.map((b) => (
            <button key={b.id}
                    className={`saved-main ${b.id === selectedId ? "on" : ""}`}
                    dir="auto" onClick={() => setSelectedId(b.id)}>
              <span className="g-title">{b.question.slice(0, 60)}</span>
              <span className="g-meta">
                {(b.latest?.created_at ?? b.created_at).slice(0, 10)}
                {b.stale_count > 0 && (
                  <span className="badge warn" style={{ marginInlineStart: 6 }}>
                    {b.stale_count} new
                  </span>
                )}
              </span>
            </button>
          ))}
          <div className="side-head" style={{ marginTop: 12 }}>
            <span className="label">Groups in scope</span>
          </div>
          <div className="chips" style={{ padding: "0 8px", flexWrap: "wrap" }}>
            {groups.map((g) => (
              <button key={g.chat_id}
                      className={`chip ${selection.has(g.chat_id) ? "on" : ""}`}
                      dir="auto" title="Toggle group in scope"
                      onClick={() => toggleGroup(g.chat_id)}>
                {g.title.length > 18 ? g.title.slice(0, 18) + "…" : g.title}
              </button>
            ))}
          </div>
        </aside>

        <div className="brief-view">
          {!selected && (
            <EmptyState icon="🔬" title="Your research desk"
                        hint="Ask a question about your groups. The answer becomes a saved, cited brief you can re-run weekly - it will tell you when new relevant messages appeared since." />
          )}
          {selected && !selected.latest && (
            <EmptyState icon="⏳" title="Generating…"
                        hint="Your brief is being researched. Watch the Jobs panel for live progress; this page refreshes automatically." />
          )}
          {selected?.latest && (
            <BriefDetail brief={selected}
                         onDeleted={() => { setSelectedId(null); void load(); }}
                         onReload={() => void load()} />
          )}
        </div>
      </div>
    </div>
  );
}

function BriefDetail({ brief, onDeleted, onReload }: {
  brief: Brief; onDeleted: () => void; onReload: () => void;
}) {
  const { toast, jobs, select, setRightTab } = useStore();
  const [notes, setNotes] = useState(brief.notes);
  const [showCites, setShowCites] = useState(true);
  const busy = jobs?.running && jobs?.name === "brief";

  const regenerate = async () => {
    try {
      const r = await api.briefRegenerate(brief.id);
      toast(r.queued ? "Re-run queued - a new version is on the way" : "Already running", "info");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const saveNotes = async () => {
    try {
      await api.briefPatch(brief.id, { notes });
      toast("Notes saved", "good");
      onReload();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const openCitation = async (chatId: number, msgId: number) => {
    try {
      const m = await api.message(chatId, msgId);
      select(m);
      setRightTab("details");
    } catch {
      toast("Could not open the original message", "err");
    }
  };

  const ver = brief.latest!;

  return (
    <div className="brief-detail">
      <div className="brief-head">
        <h3 className="brief-q" dir="auto">{brief.question}</h3>
        <div className="brief-meta">
          <span className="badge">v{ver.version}</span>
          <span className="dim">generated {ver.created_at.slice(0, 10)} · {ver.model}</span>
          {brief.stale_count > 0 && (
            <span className="badge warn" title="New scope-matching messages appeared after this version">
              {brief.stale_count} new message{brief.stale_count > 1 ? "s" : ""} since
            </span>
          )}
          <span style={{ flex: 1 }} />
          <button className="btn primary sm" disabled={busy} onClick={() => void regenerate()}>
            {busy ? "Working…" : "Re-run"}
          </button>
          <button className="btn ghost sm"
                  onClick={() => void (async () => {
                    try { await api.exportBrief(brief.id, "md"); toast("Exported", "good"); }
                    catch (e) { toast((e as Error).message, "err"); }
                  })()}>Export .md</button>
          <button className="btn ghost sm"
                  onClick={() => void (async () => {
                    try { await api.exportBrief(brief.id, "json"); toast("Exported", "good"); }
                    catch (e) { toast((e as Error).message, "err"); }
                  })()}>.json</button>
          <button className="btn danger sm"
                  onClick={() => void (async () => {
                    try { await api.briefDelete(brief.id); toast("Brief deleted", "info"); onDeleted(); }
                    catch (e) { toast((e as Error).message, "err"); }
                  })()}>Delete</button>
        </div>
      </div>

      <div className="brief-md" dir="auto"
           dangerouslySetInnerHTML={{ __html: mdToHtml(ver.answer_md) }} />

      <details className="ai-sources" open={showCites}
               onToggle={(e) => setShowCites((e.target as HTMLDetailsElement).open)}>
        <summary>Citations ({ver.citations.length}) - every claim traces here</summary>
        {ver.citations.map((c) => (
          <button key={c.idx} className="src-row"
                  onClick={() => void openCitation(c.chat_id, c.msg_id)}>
            <span className="num">[{c.idx}]</span>
            <span className="src-title" dir="auto">{c.chat_title}</span>
            <span className="src-date">{(c.date ?? "").slice(0, 10)}</span>
            <span className="src-sender" dir="auto">{c.sender_name ?? ""}</span>
            <span className="src-text" dir="auto">{(c.text ?? "").slice(0, 110)}</span>
            {c.tg_link && <span className="link">Telegram ↗</span>}
          </button>
        ))}
      </details>

      <div className="brief-notes">
        <span className="label">Your notes</span>
        <textarea className="input" rows={3} dir="auto" value={notes}
                  placeholder="Personal notes for this brief (stays local)…"
                  onChange={(e) => setNotes(e.target.value)} />
        <div><button className="btn ghost sm" onClick={() => void saveNotes()}>Save notes</button></div>
      </div>
    </div>
  );
}

/** Research workspace: ask a question, get a saved, cited, re-runnable
 *  brief. Versions preserve history; staleness is computed
 *  deterministically (never by the LLM). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { Brief } from "../api/types";
import { mdToHtml } from "../utils/markdown";
import { EmptyState } from "./EmptyState";
import { Ic } from "../design/icons";

export function ResearchView() {
  const { appState, toast, groups, jobs, selection, toggleGroup } = useStore();
  const { t } = useLang();
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
      toast(t("research.queued"), "info");
      setQuestion("");
      setSelectedId(r.id);
    }
  };

  const selected = briefs?.find((b) => b.id === selectedId) ?? null;

  if (appState && !appState.ai_configured) {
    return (
      <div className="feed-col">
        <EmptyState icon="BookOpen" title={t("research.needsAi")}
                    hint={t("research.needsAiHint")} />
      </div>
    );
  }

  return (
    <div className="feed-col research-col">
      <div className="bm-bar research-form">
        <textarea className="input" rows={2} placeholder={t("research.placeholder")}
                  dir="auto" value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault();
                      void create();
                    }
                  }} />
        <div className="research-ctrl">
          <select className="input" value={scopeDays} title={t("research.dateScope")}
                  onChange={(e) => setScopeDays(e.target.value as typeof scopeDays)}>
            <option value="all">{t("research.scope.all")}</option>
            <option value="30d">{t("research.scope.30")}</option>
            <option value="90d">{t("research.scope.90")}</option>
            <option value="custom">{t("research.scope.custom")}</option>
          </select>
          {scopeDays === "custom" && (
            <span className="date-range">
              <input type="date" className="input" style={{ width: 130 }} value={from}
                     onChange={(e) => setFrom(e.target.value)} />
              <span><Ic.ArrowRight size={13} /></span>
              <input type="date" className="input" style={{ width: 130 }} value={to}
                     onChange={(e) => setTo(e.target.value)} />
            </span>
          )}
          <button className="btn primary sm" disabled={!question.trim() || creating}
                  onClick={() => void create()}>
            {creating
              ? <><Ic.Spin size={13} className="spin" /> {t("research.working")}</>
              : t("research.submit")}
          </button>
        </div>
      </div>

      <div className="research-body">
        <aside className="brief-list">
          <div className="side-head"><span className="label">{t("research.briefs")}</span></div>
          {briefs === null && <div className="side-note">{t("state.loading")}</div>}
          {briefs?.length === 0 && (
            <div className="side-note">{t("research.noBriefs")}</div>
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
                    {t("research.nNew", { n: b.stale_count })}
                  </span>
                )}
              </span>
            </button>
          ))}
          <div className="side-head" style={{ marginTop: 12 }}>
            <span className="label">{t("research.groupsInScope")}</span>
          </div>
          <div className="chips" style={{ padding: "0 8px", flexWrap: "wrap" }}>
            {groups.map((g) => (
              <button key={g.chat_id}
                      className={`chip ${selection.has(g.chat_id) ? "on" : ""}`}
                      dir="auto" title={t("research.toggleGroup")}
                      onClick={() => toggleGroup(g.chat_id)}>
                {g.title.length > 18 ? g.title.slice(0, 18) + "…" : g.title}
              </button>
            ))}
          </div>
        </aside>

        <div className="brief-view">
          {!selected && (
            <EmptyState icon="BookOpen" title={t("research.desk")}
                        hint={t("research.deskHint")} />
          )}
          {selected && !selected.latest && (
            <EmptyState icon="Hourglass" title={t("research.generating")}
                        hint={t("research.generatingHint")} />
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
  const { t } = useLang();
  const [notes, setNotes] = useState(brief.notes);
  const [showCites, setShowCites] = useState(true);
  const busy = jobs?.running && jobs?.name === "brief";

  const regenerate = async () => {
    try {
      const r = await api.briefRegenerate(brief.id);
      toast(r.queued ? t("research.rerunQueued") : t("research.alreadyRunning"), "info");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const saveNotes = async () => {
    try {
      await api.briefPatch(brief.id, { notes });
      toast(t("research.notesSaved"), "good");
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
      toast(t("research.couldNotOpen"), "err");
    }
  };

  const ver = brief.latest!;

  return (
    <div className="brief-detail">
      <div className="brief-head">
        <h3 className="brief-q" dir="auto">{brief.question}</h3>
        <div className="brief-meta">
          <span className="badge">v{ver.version}</span>
          <span className="dim">{t("research.generated", { date: ver.created_at.slice(0, 10), model: ver.model })}</span>
          {brief.stale_count > 0 && (
            <span className="badge warn" title={t("research.staleBadgeHint")}>
              {t("research.staleBadge", { n: brief.stale_count })}
            </span>
          )}
          <span style={{ flex: 1 }} />
          <button className="btn primary sm" disabled={busy} onClick={() => void regenerate()}>
            {busy
              ? <><Ic.Spin size={13} className="spin" /> {t("research.working")}</>
              : <><Ic.RotateCcw size={13} /> {t("research.rerun")}</>}
          </button>
          <button className="btn ghost sm"
                  onClick={() => void (async () => {
                    try { await api.exportBrief(brief.id, "md"); toast(t("research.exported"), "good"); }
                    catch (e) { toast((e as Error).message, "err"); }
                  })()}>
            <Ic.FileDown size={13} /> {t("research.exportMd")}
          </button>
          <button className="btn ghost sm"
                  onClick={() => void (async () => {
                    try { await api.exportBrief(brief.id, "json"); toast(t("research.exported"), "good"); }
                    catch (e) { toast((e as Error).message, "err"); }
                  })()}>{t("research.exportJson")}</button>
          <button className="btn danger sm"
                  onClick={() => void (async () => {
                    try { await api.briefDelete(brief.id); toast(t("research.deleted"), "info"); onDeleted(); }
                    catch (e) { toast((e as Error).message, "err"); }
                  })()}>
            <Ic.Trash size={13} /> {t("research.delete")}
          </button>
        </div>
      </div>

      <div className="brief-md" dir="auto"
           dangerouslySetInnerHTML={{ __html: mdToHtml(ver.answer_md) }} />

      <details className="ai-sources" open={showCites}
               onToggle={(e) => setShowCites((e.target as HTMLDetailsElement).open)}>
        <summary>{t("research.citations", { n: ver.citations.length })}</summary>
        {ver.citations.map((c) => (
          <button key={c.idx} className="src-row"
                  onClick={() => void openCitation(c.chat_id, c.msg_id)}>
            <span className="num">[{c.idx}]</span>
            <span className="src-title" dir="auto">{c.chat_title}</span>
            <span className="src-date">{(c.date ?? "").slice(0, 10)}</span>
            <span className="src-sender" dir="auto">{c.sender_name ?? ""}</span>
            <span className="src-text" dir="auto">{(c.text ?? "").slice(0, 110)}</span>
            {c.tg_link && <span className="link">{t("action.openTelegram")}</span>}
          </button>
        ))}
      </details>

      <div className="brief-notes">
        <span className="label">{t("research.notes")}</span>
        <textarea className="input" rows={3} dir="auto" value={notes}
                  placeholder={t("research.notesPlaceholder")}
                  onChange={(e) => setNotes(e.target.value)} />
        <div>
          <button className="btn ghost sm" onClick={() => void saveNotes()}>
            <Ic.Save size={13} /> {t("research.saveNotes")}
          </button>
        </div>
      </div>
    </div>
  );
}

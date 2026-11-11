/** Right panel "Ask AI" tab: conversational history, grounded answers with
 *  clickable citations, visible retrieval scope chips, answer export,
 *  provider disclosure, and setup/empty states. */
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import { mdToHtml } from "../utils/markdown";
import {
  clearChat, getAiScopeDays, getChat, pushChat, setAiScopeDays, type ChatTurn,
} from "../utils/history";
import { fmtDate } from "../utils/format";
import { EmptyState } from "./EmptyState";
import { Ic } from "../design/icons";

// Bilingual by design: examples show Arabic and English questions.
const EXAMPLES = [
  "What were the main topics this week?",
  "ما أهم العروض المنشورة مؤخراً؟",
  "What problems do people report and how are they solved?",
  "لخّص آخر النقاشات في المجموعات",
];

export function AiPanel() {
  const { appState, selection, clearSelection, select, setRightTab, toast } = useStore();
  const { t } = useLang();
  const [chat, setChat] = useState<ChatTurn[]>(getChat);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [scopeDays, setScopeDays] = useState<"all" | "7d" | "30d">(getAiScopeDays);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [chat.length, busy]);

  const scope = useMemo(() => {
    if (scopeDays === "all") return { chat_ids: [...selection], date_from: null, date_to: null };
    const to = new Date().toISOString().slice(0, 10);
    const from = new Date(Date.now() - (scopeDays === "7d" ? 6 : 29) * 864e5)
      .toISOString().slice(0, 10);
    return { chat_ids: [...selection], date_from: from, date_to: to };
  }, [selection, scopeDays]);

  const ask = async (q: string) => {
    const qt = q.trim();
    if (!qt || busy) return;
    setQuestion("");
    setBusy(true);
    setChat(pushChat({ question: qt, answer: null, sources: [], keywords: [] }));
    try {
      const r = await api.ask(qt, scope);
      setChat(
        pushChat({
          question: qt,
          answer: r.answer,
          error: r.error,
          sources: (r.sources ?? []).map((s) => ({
            chat_id: s.chat_id, msg_id: s.msg_id, title: s.chat_title,
            date: s.date, sender: s.sender_name ?? "", text: s.text,
          })),
          keywords: (r.keywords_tried ?? []).flat(),
          fallback: r.fallback,
        }),
      );
    } catch (e) {
      setChat(
        pushChat({
          question: qt, answer: null, error: (e as Error).message,
          sources: [], keywords: [],
        }),
      );
    } finally {
      setBusy(false);
    }
  };

  const openSource = (src: ChatTurn["sources"][number]) => {
    // full message is fetched by id; highlights in the feed when present
    void (async () => {
      try {
        const m = await api.message(src.chat_id, src.msg_id);
        select(m);
        setRightTab("details");
      } catch {
        toast(t("ai.couldNotOpen"), "err");
      }
    })();
  };

  if (appState && !appState.ai_configured) {
    return (
      <div className="ai-panel">
        <EmptyState
          icon="Sparkles"
          title={t("ai.notConfigured")}
          hint={t("ai.notConfiguredHint")}
        />
      </div>
    );
  }

  const scopeSummary = t("ai.scopeGroups", { n: selection.size })
    + (scopeDays === "all" ? "" : ` · ${t("filter.days", { n: scopeDays === "7d" ? 7 : 30 })}`);

  return (
    <div className="ai-panel">
      {chat.length === 0 && !busy && (
        <EmptyState
          icon="Sparkles"
          title={t("ai.emptyTitle")}
          hint={t("ai.emptyHint", {
            n: (appState?.messages ?? 0).toLocaleString(),
          })}
        />
      )}

      {(chat.length > 0 || busy) && (
        <div className="ai-chat">
          {chat.map((turn, i) => (
            <TurnView key={i} turn={turn} onOpenSource={openSource}
                      providerHost={appState?.ai_provider_host}
                      providerModel={appState?.ai_model} />
          ))}
          {busy && (
            <div className="ai-thinking">
              <span className="spinner" /> {t("ai.thinking", { scope: scopeSummary })}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {chat.length === 0 && (
        <div className="ai-examples">
          {EXAMPLES.map((ex) => (
            <button key={ex} className="chip" onClick={() => { setQuestion(ex); void ask(ex); }}>
              {ex}
            </button>
          ))}
        </div>
      )}

      <div className="ai-scope-row" title={t("ai.scopeHint")}>
        <span className="label">{t("ai.scope")}</span>
        {selection.size > 0 ? (
          <button className="chip on" onClick={() => clearSelection()}
                  title={t("ai.scopeGroupsHint")}>
            <Ic.Users size={12} /> {t("ai.scopeGroups", { n: selection.size })}
            <span className="x"><Ic.Close size={11} /></span>
          </button>
        ) : (
          <span className="chip on static" title={t("ai.scopeAllHint")}>
            <Ic.Globe size={12} /> {t("filter.allGroups")}
          </span>
        )}
        {(["all", "7d", "30d"] as const).map((c) => (
          <button key={c}
                  className={`chip ${scopeDays === c ? "on" : ""}`}
                  onClick={() => { setScopeDays(c); setAiScopeDays(c); }}>
            {c === "all" ? t("filter.allTime") : t("filter.days", { n: c === "7d" ? 7 : 30 })}
          </button>
        ))}
      </div>

      <div className="ai-input-row">
        <textarea
          className="input"
          rows={2}
          placeholder={t("ai.placeholder")}
          value={question}
          dir="auto"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              void ask(question);
            }
          }}
        />
        <button className="btn primary" disabled={busy || !question.trim()} onClick={() => void ask(question)}>
          {t("ai.ask")}
        </button>
      </div>
      <div className="ai-disclosure">
        {appState && (
          <span>
            {t("ai.disclosure", {
              host: appState.ai_provider_host,
              model: appState.ai_model,
              scope: scopeSummary,
            })}
          </span>
        )}
        {chat.length > 0 && (
          <button className="link" onClick={() => { clearChat(); setChat([]); }}>{t("ai.clearHistory")}</button>
        )}
      </div>
    </div>
  );
}

function TurnView({ turn, onOpenSource, providerHost, providerModel }: {
  turn: ChatTurn;
  onOpenSource: (s: ChatTurn["sources"][number]) => void;
  providerHost?: string;
  providerModel?: string;
}) {
  const { select, setRightTab, toast } = useStore();
  const { t } = useLang();
  const [exporting, setExporting] = useState(false);

  // citation clicks inside the answer open the cited message
  const onAnswerClick = (e: React.MouseEvent) => {
    const el = (e.target as HTMLElement).closest("[data-cite]");
    if (!el) return;
    const n = parseInt((el as HTMLElement).dataset.cite ?? "", 10);
    const src = turn.sources[n - 1];
    if (!src) {
      // model cited something outside the retrieved set - never fake it
      toast(t("ai.badCitation", { n }), "err");
      return;
    }
    void (async () => {
      try {
        const m = await api.message(src.chat_id, src.msg_id);
        select(m);
        setRightTab("details");
      } catch {
        toast(t("ai.couldNotOpen"), "err");
      }
    })();
  };

  const exportAnswer = async () => {
    if (!turn.answer) return;
    setExporting(true);
    try {
      const name = await api.exportAiAnswer({
        question: turn.question,
        answer: turn.answer,
        sources: turn.sources.map((s) => ({ chat_id: s.chat_id, msg_id: s.msg_id })),
        provider_host: providerHost,
        model: providerModel,
      });
      toast(t("ai.exported", { name }), "good");
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="ai-turn">
      <div className="ai-q" dir="auto">{turn.question}</div>
      {turn.answer && (
        <>
          <div className="ai-a" dir="auto" onClick={onAnswerClick}
               dangerouslySetInnerHTML={{ __html: mdToHtml(turn.answer) }} />
          <div className="ai-src-meta">
            {turn.fallback === "recent"
              ? t("ai.fallbackRecent")
              : t("ai.basedOn", { n: turn.sources.length })}
            <button className="link" disabled={exporting}
                    onClick={() => void exportAnswer()} style={{ marginInlineStart: 8 }}>
              {exporting
                ? t("ai.exporting")
                : t("ai.export")}
            </button>
          </div>
          {turn.sources.length > 0 && (
            <details className="ai-sources">
              <summary>{t("ai.sources", { n: turn.sources.length })}</summary>
              {turn.sources.map((s, i) => (
                <button key={i} className="src-row" onClick={() => onOpenSource(s)}>
                  <span className="num">[{i + 1}]</span>
                  <span className="src-title" dir="auto">{s.title}</span>
                  <span className="src-date">{fmtDate(s.date)}</span>
                  <span className="src-sender" dir="auto">{s.sender}</span>
                  <span className="src-text" dir="auto">{s.text.slice(0, 120)}</span>
                </button>
              ))}
            </details>
          )}
        </>
      )}
      {turn.error && <div className="ai-error">{turn.error}</div>}
    </div>
  );
}

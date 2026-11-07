/** Right panel "Ask AI" tab: conversational history, grounded answers with
 *  clickable citations, provider disclosure, and setup/empty states. */
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { mdToHtml } from "../utils/markdown";
import {
  clearChat, getChat, pushChat, type ChatTurn,
} from "../utils/history";
import { fmtDate } from "../utils/format";
import { EmptyState } from "./EmptyState";

const EXAMPLES = [
  "What were the main topics this week?",
  "ما أهم العروض المنشورة مؤخراً؟",
  "What problems do people report and how are they solved?",
  "لخّص آخر النقاشات في المجموعات",
];

export function AiPanel() {
  const { appState, select, setRightTab, toast } = useStore();
  const [chat, setChat] = useState<ChatTurn[]>(getChat);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [chat.length, busy]);

  const ask = async (q: string) => {
    const qt = q.trim();
    if (!qt || busy) return;
    setQuestion("");
    setBusy(true);
    setChat(pushChat({ question: qt, answer: null, sources: [], keywords: [] }));
    try {
      const r = await api.ask(qt);
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
        toast("Could not open the original message", "err");
      }
    })();
  };

  if (appState && !appState.ai_configured) {
    return (
      <div className="ai-panel">
        <EmptyState
          icon="✦"
          title="Ask AI is not configured"
          hint="Add AI_API_KEY (and optionally AI_BASE_URL / AI_MODEL) in your .env file to enable grounded answers over your archive. Works with any OpenAI-compatible endpoint - OpenAI, Groq, OpenRouter, Ollama, vLLM and more. Restart the app after editing .env."
        />
      </div>
    );
  }

  return (
    <div className="ai-panel">
      {chat.length === 0 && !busy && (
        <EmptyState
          icon="✦"
          title="Ask anything about your groups"
          hint={`Answers are grounded in your ${appState?.messages.toLocaleString() ?? ""} archived messages, with clickable citations. Questions in Arabic get Arabic answers.`}
        />
      )}

      <div className="ai-chat">
        {chat.map((turn, i) => (
          <TurnView key={i} turn={turn} onOpenSource={openSource} />
        ))}
        {busy && (
          <div className="ai-thinking"><span className="spinner" /> searching the archive and thinking…</div>
        )}
        <div ref={bottomRef} />
      </div>

      {chat.length === 0 && (
        <div className="ai-examples">
          {EXAMPLES.map((ex) => (
            <button key={ex} className="chip" onClick={() => { setQuestion(ex); void ask(ex); }}>
              {ex}
            </button>
          ))}
        </div>
      )}

      <div className="ai-input-row">
        <textarea
          className="input"
          rows={2}
          placeholder="Ask a question…  (Ctrl+Enter)"
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
          Ask
        </button>
      </div>
      <div className="ai-disclosure">
        {appState && (
          <span>
            Answers send retrieved message excerpts to <b>{appState.ai_provider_host}</b> ({appState.ai_model}).
            Nothing is sent unless you ask.
          </span>
        )}
        {chat.length > 0 && (
          <button className="link" onClick={() => { clearChat(); setChat([]); }}>clear history</button>
        )}
      </div>
    </div>
  );
}

function TurnView({ turn, onOpenSource }: {
  turn: ChatTurn;
  onOpenSource: (s: ChatTurn["sources"][number]) => void;
}) {
  const { select, setRightTab, toast } = useStore();
  // citation clicks inside the answer open the cited message
  const onAnswerClick = (e: React.MouseEvent) => {
    const el = (e.target as HTMLElement).closest("[data-cite]");
    if (!el) return;
    const n = parseInt((el as HTMLElement).dataset.cite ?? "", 10);
    const src = turn.sources[n - 1];
    if (!src) {
      // model cited something outside the retrieved set - never fake it
      toast(`Citation [${n}] has no matching retrieved message`, "err");
      return;
    }
    void (async () => {
      try {
        const m = await api.message(src.chat_id, src.msg_id);
        select(m);
        setRightTab("details");
      } catch {
        toast("Could not open the original message", "err");
      }
    })();
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
              ? "No keyword hits — answer based on the most recent messages."
              : `Based on ${turn.sources.length} retrieved message${turn.sources.length === 1 ? "" : "s"}.`}
          </div>
          {turn.sources.length > 0 && (
            <details className="ai-sources">
              <summary>Sources ({turn.sources.length})</summary>
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

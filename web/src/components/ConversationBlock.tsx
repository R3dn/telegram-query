/** Conversation reconstruction around the selected message (v0.7).
 *  Reply chains where captured (v0.5+), same-chat window always - the
 *  honest fallback for older messages. Every row opens its original. */
import { useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { ConversationContext, Message } from "../api/types";
import { fmtTime } from "../utils/format";

export function ConversationBlock({ m }: { m: Message }) {
  const { select, toast } = useStore();
  const [ctx, setCtx] = useState<ConversationContext | null>(null);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    void (async () => {
      try {
        setCtx(await api.messageContext(m.chat_id, m.msg_id));
      } catch (e) {
        toast((e as Error).message, "err");
      } finally {
        setLoading(false);
      }
    })();
  };

  const open = (row: Message) => {
    void (async () => {
      try {
        select(await api.message(row.chat_id, row.msg_id));
      } catch {
        toast("Could not open the message", "err");
      }
    })();
  };

  if (ctx === null) {
    return (
      <button className="btn ghost sm" disabled={loading} onClick={load}
              title="Reply chain (where captured) + the messages around this one">
        {loading ? "loading…" : "💬 View in conversation"}
      </button>
    );
  }

  return (
    <div className="conv-block">
      <div className="side-head" style={{ padding: "0 0 4px" }}>
        <span className="label">Conversation</span>
        <button className="link" onClick={() => setCtx(null)}>✕</button>
      </div>
      {ctx.ancestors.length > 0 && (
        <div className="conv-note dim">
          ↩ replying to {ctx.ancestors.map((a) => `#${a.msg_id}`).join(" ← ")}
        </div>
      )}
      <div className="conv-rows">
        {ctx.rows.map((r) => (
          <button key={`${r.chat_id}-${r.msg_id}`}
                  className={`conv-row ${r.is_target ? "target" : ""}`}
                  onClick={() => open(r)}>
            <span className="msg-time">{fmtTime(r.date)}</span>
            <span className="conv-sender" dir="auto">{r.sender_name || "unknown"}</span>
            {r.is_reply === 1 && <span className="badge" title="direct reply">↩</span>}
            <span className="conv-text" dir="auto">{r.text || "[media only]"}</span>
          </button>
        ))}
      </div>
      {ctx.rows.length === 1 && (
        <div className="conv-note dim">No neighboring messages archived around this one.</div>
      )}
    </div>
  );
}

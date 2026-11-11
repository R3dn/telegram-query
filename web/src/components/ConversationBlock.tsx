/** Conversation reconstruction around the selected message.
 *  Reply chains where captured, same-chat window always - the honest
 *  fallback for older messages. Every row opens its original. */
import { useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { ConversationContext, Message } from "../api/types";
import { fmtTime } from "../utils/format";
import { Ic } from "../design/icons";

export function ConversationBlock({ m }: { m: Message }) {
  const { select, toast } = useStore();
  const { t } = useLang();
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
        toast(t("conv.couldNotOpen"), "err");
      }
    })();
  };

  if (ctx === null) {
    return (
      <button className="btn ghost sm" disabled={loading} onClick={load}
              title={t("conv.openHint")}>
        {loading
          ? <><Ic.Spin size={13} className="spin" /> {t("state.loading")}</>
          : <><Ic.MessageSquare size={13} /> {t("action.viewConversation")}</>}
      </button>
    );
  }

  return (
    <div className="conv-block">
      <div className="side-head" style={{ padding: "0 0 4px" }}>
        <span className="label">{t("conv.title")}</span>
        <button className="link" onClick={() => setCtx(null)}><Ic.Close size={12} /></button>
      </div>
      {ctx.ancestors.length > 0 && (
        <div className="conv-note dim">
          <Ic.CornerUpLeft size={11} /> {t("conv.repliesTo", { ids: ctx.ancestors.map((a) => `#${a.msg_id}`).join(" · ") })}
        </div>
      )}
      <div className="conv-rows">
        {ctx.rows.map((r) => (
          <button key={`${r.chat_id}-${r.msg_id}`}
                  className={`conv-row ${r.is_target ? "target" : ""}`}
                  onClick={() => open(r)}>
            <span className="msg-time">{fmtTime(r.date)}</span>
            <span className="conv-sender" dir="auto">{r.sender_name || t("feed.unknown")}</span>
            {r.is_reply === 1 && <span className="badge" title={t("conv.directReply")}><Ic.Reply size={10} /></span>}
            <span className="conv-text" dir="auto">{r.text || t("conv.mediaOnly")}</span>
          </button>
        ))}
      </div>
      {ctx.rows.length === 1 && (
        <div className="conv-note dim">{t("conv.noNeighbors")}</div>
      )}
    </div>
  );
}

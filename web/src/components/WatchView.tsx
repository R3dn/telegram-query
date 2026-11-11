/** Watchlists workspace (v1.0): keyword monitors + the alerts inbox.

Watchlists are DETERMINISTIC: matching runs on the same normalized text as
search, right after each sync - the AI provider is never involved, so
monitoring works (and costs nothing) even without one. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { Alert, Watchlist } from "../api/types";
import { fmtDateTime } from "../utils/format";
import { Ic } from "../design/icons";
import { EmptyState } from "./EmptyState";
import { Modal } from "./Modal";

type T = ReturnType<typeof useLang>["t"];

const ALERT_TAB: Record<"new" | "read" | "archived", { label: string; empty: string }> = {
  new: { label: "watch.tabNew", empty: "watch.emptyNew" },
  read: { label: "watch.tabRead", empty: "watch.emptyRead" },
  archived: { label: "watch.tabArchived", empty: "watch.emptyArchived" },
};

export function WatchView() {
  const { groups, toast } = useStore();
  const { t } = useLang();
  const [rows, setRows] = useState<Watchlist[] | null>(null);
  const [editing, setEditing] = useState<Watchlist | null>(null);
  const [creating, setCreating] = useState(false);

  const load = async () => {
    try {
      setRows(await api.watchlists());
    } catch (e) {
      toast((e as Error).message, "err");
      setRows([]);
    }
  };
  useEffect(() => { void load(); }, []);

  const checkNow = async (backfill = 0) => {
    try {
      const r = await api.watchCheck(backfill);
      toast(r.matches > 0
        ? t("watch.checkedNew", { n: r.matches, u: r.unread })
        : t("watch.checkedNone"), r.matches > 0 ? "good" : "info");
      await load();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">{t("nav.watchlists")}</h2>
        <span className="dim wl-sub">{t("watch.subtitle")}</span>
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" title={t("watch.checkNowHint")}
                onClick={() => void checkNow(0)}>
          <Ic.Play size={13} /> {t("watch.checkNow")}
        </button>
        <button className="btn ghost sm" title={t("watch.checkBackfillHint")}
                onClick={() => void checkNow(7)}>
          <Ic.RotateCcw size={13} /> {t("watch.checkBackfill")}
        </button>
        <button className="btn primary sm" onClick={() => setCreating(true)}>
          <Ic.Plus size={14} /> {t("watch.newList")}
        </button>
      </div>

      <div className="feed">
        {rows === null && (
          <div className="feed-loading">
            <Ic.Spin size={13} className="spin" /> {t("state.loading")}
          </div>
        )}
        {rows !== null && rows.length === 0 && (
          <EmptyState icon="Eye" title={t("watch.emptyTitle")}
            hint={t("watch.emptyHint")} />
        )}
        {rows?.map((w) => (
          <div key={w.id} className="bm-card">
            <div className="bm-head">
              <span className="wl-ic"><Ic.Eye size={14} /></span>
              <span className="bm-grp" dir="auto">{w.name}</span>
              {w.unread > 0 && (
                <span className="badge warn">
                  <Ic.Bell size={10} /> {t("watch.badgeNew", { n: w.unread })}
                </span>
              )}
              {!w.enabled && (
                <span className="badge">
                  <Ic.CircleOff size={10} /> {t("watch.paused")}
                </span>
              )}
              <span style={{ flex: 1 }} />
              <button className="btn ghost sm"
                      onClick={() => void (async () => {
                        try {
                          await api.watchUpdate(w.id, {
                            name: w.name, terms: w.terms,
                            exclude_terms: w.exclude_terms,
                            chat_ids: w.chat_ids, enabled: !w.enabled,
                          });
                          await load();
                        } catch (e) { toast((e as Error).message, "err"); }
                      })()}>
                {w.enabled
                  ? t("watch.pause")
                  : <><Ic.Play size={12} /> {t("watch.resume")}</>}
              </button>
              <button className="btn ghost sm" onClick={() => setEditing(w)}>
                <Ic.Pencil size={12} /> {t("watch.edit")}
              </button>
              <button className="btn danger sm"
                      onClick={() => void (async () => {
                        try {
                          await api.watchDelete(w.id);
                          toast(t("watch.deleted"), "info");
                          await load();
                        } catch (e) { toast((e as Error).message, "err"); }
                      })()}>
                <Ic.Trash size={12} /> {t("action.delete")}
              </button>
            </div>
            <div className="wl-terms">
              {w.terms.map((term, i) => (
                <span key={i} className="wl-term" dir="auto">{term}</span>
              ))}
              {w.exclude_terms.map((term, i) => (
                <span key={`x-${i}`} className="wl-term off" dir="auto">
                  <Ic.Minus size={10} /> {term}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {(creating || editing) && (
        <WatchModal w={editing} groups={groups} t={t}
                    onClose={() => { setCreating(false); setEditing(null); }}
                    onSaved={() => { setCreating(false); setEditing(null); void load(); }} />
      )}
    </div>
  );
}

function WatchModal({ w, groups, onClose, onSaved, t }: {
  w: Watchlist | null;
  groups: { chat_id: number; title: string }[];
  onClose: () => void;
  onSaved: () => void;
  t: T;
}) {
  const { toast } = useStore();
  const [name, setName] = useState(w?.name ?? "");
  const [terms, setTerms] = useState((w?.terms ?? []).join(", "));
  const [excludes, setExcludes] = useState((w?.exclude_terms ?? []).join(", "));
  const [scope, setScope] = useState<Set<number>>(new Set(w?.chat_ids ?? []));

  const save = async () => {
    const body = {
      name: name.trim(),
      terms: terms.split(",").map((x) => x.trim()).filter(Boolean),
      exclude_terms: excludes.split(",").map((x) => x.trim()).filter(Boolean),
      chat_ids: [...scope],
      enabled: true,
    };
    if (!body.name || body.terms.length === 0) {
      toast(t("watch.needNameAndTerm"), "err");
      return;
    }
    try {
      if (w) await api.watchUpdate(w.id, body);
      else await api.watchCreate(body);
      toast(w ? t("watch.updated") : t("watch.created"), "good");
      onSaved();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <Modal title={w ? t("watch.editTitle") : t("watch.newList")} onClose={onClose}
           footer={
      <>
        <button className="btn ghost sm" onClick={onClose}>{t("action.cancel")}</button>
        <button className="btn primary sm" onClick={() => void save()}>
          <Ic.Save size={13} /> {t("action.save")}
        </button>
      </>
    }>
      <p className="mm-note dim">{t("watch.modalNote")}</p>
      <label className="field"><span>{t("watch.fieldName")}</span>
        <input className="input" value={name} dir="auto" maxLength={100}
               placeholder={t("watch.phName")}
               onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="field"><span>{t("watch.fieldTerms")}</span>
        <input className="input" value={terms} dir="auto"
               placeholder={t("watch.phTerms")}
               onChange={(e) => setTerms(e.target.value)} />
      </label>
      <label className="field"><span>{t("watch.fieldExcludes")}</span>
        <input className="input" value={excludes} dir="auto"
               placeholder={t("watch.phExcludes")}
               onChange={(e) => setExcludes(e.target.value)} />
      </label>
      <div className="field"><span>{t("watch.fieldScope")}</span>
        <div className="chips wl-chips">
          {groups.map((g) => (
            <button key={g.chat_id}
                    className={`chip ${scope.has(g.chat_id) ? "on" : ""}`}
                    dir="auto"
                    onClick={() => setScope((s) => {
                      const n = new Set(s);
                      if (n.has(g.chat_id)) n.delete(g.chat_id);
                      else n.add(g.chat_id);
                      return n;
                    })}>
              {g.title}
            </button>
          ))}
        </div>
      </div>
    </Modal>
  );
}

export function AlertsView() {
  const { toast, select, setRightTab, jobs } = useStore();
  const { t } = useLang();
  const [state, setState] = useState<"new" | "read" | "archived">("new");
  const [rows, setRows] = useState<Alert[] | null>(null);

  const load = async (s = state) => {
    try {
      setRows(await api.alerts({ state: s }));
    } catch (e) {
      toast((e as Error).message, "err");
      setRows([]);
    }
  };
  useEffect(() => { void load(state); }, [state]);

  const lastDone = jobs?.last_done;
  useEffect(() => {
    if (lastDone?.name === "sync") void load(state);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastDone?.finished_at]);

  const act = async (id: number, action: "read" | "archive") => {
    try {
      await api.alertAction(id, action);
      await load();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const jump = (a: Alert) => {
    void (async () => {
      try {
        const m = await api.message(a.chat_id, a.msg_id);
        select(m);
        setRightTab("details");
      } catch {
        toast(t("watch.jumpFailed"), "err");
      }
    })();
  };

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">{t("nav.alerts")}</h2>
        <div className="seg">
          {(["new", "read", "archived"] as const).map((s) => (
            <button key={s} className={state === s ? "on" : ""}
                    onClick={() => setState(s)}>{t(ALERT_TAB[s].label)}</button>
          ))}
        </div>
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" onClick={() => void load()}>
          <Ic.RefreshCw size={13} /> {t("watch.refresh")}
        </button>
      </div>

      <div className="feed">
        {rows === null && (
          <div className="feed-loading">
            <Ic.Spin size={13} className="spin" /> {t("state.loading")}
          </div>
        )}
        {rows !== null && rows.length === 0 && (
          <EmptyState icon="Bell" title={t(ALERT_TAB[state].empty)}
            hint={state === "new"
              ? t("watch.emptyNewHint")
              : t("watch.emptyOtherHint")} />
        )}
        {rows?.map((a) => (
          <div key={a.id} className={`bm-card ${a.read ? "dim" : "alert-unread"}`}>
            <div className="bm-head">
              <span className="badge"><Ic.Eye size={10} /> {a.watchlist_name}</span>
              <span className="bm-grp" dir="auto">{a.chat_title}</span>
              <span className="bm-date">{fmtDateTime(a.date)} UTC</span>
              <span className="bm-sender" dir="auto">{a.sender_name ?? ""}</span>
              <span style={{ flex: 1 }} />
              {!a.read && (
                <button className="btn ghost sm" onClick={() => void act(a.id, "read")}>
                  <Ic.Check size={12} /> {t("watch.markRead")}
                </button>
              )}
              {!a.archived && (
                <button className="btn ghost sm" onClick={() => void act(a.id, "archive")}>
                  {t("watch.archive")}
                </button>
              )}
              <button className="btn ghost sm" onClick={() => jump(a)}>
                <Ic.ArrowRight size={12} /> {t("watch.jump")}
              </button>
              {a.tg_link && (
                <button className="btn ghost sm"
                        onClick={() => window.open(a.tg_link!, "_blank", "noopener")}>
                  <Ic.ExternalLink size={12} /> {t("action.openTelegram")}
                </button>
              )}
            </div>
            <div className="bm-text" dir="auto">{a.text}</div>
            {a.matched_term && (
              <div className="bm-note wl-matched" dir="auto">
                <Ic.Tag size={12} /> {t("watch.matchedTerm", { term: a.matched_term })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

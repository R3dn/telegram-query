/** Manage groups: tracked list (untrack with confirm), Telegram discovery
 *  with live progress, track-with-backfill queueing. */
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Dialog } from "../api/types";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import { fmtDate, jobKey, nfmt } from "../utils/format";
import { Ic } from "../design/icons";
import { Modal } from "./Modal";

type Listing =
  | { state: "idle" }
  | { state: "waiting"; note: string }
  | { state: "listing" };

type TFn = (key: string, vars?: Record<string, string | number>) => string;

/** Localized count noun: Arabic picks .one/.two/.few/.many plural classes,
 *  English .one/.many. `base` is a "system.pl.*" key prefix. */
function nounT(t: TFn, lang: string, base: string, n: number): string {
  const sfx = lang === "ar"
    ? n === 1 ? "one" : n === 2 ? "two" : n <= 10 ? "few" : "many"
    : n === 1 ? "one" : "many";
  return t(`${base}.${sfx}`, { n });
}

async function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export function ManageGroups({ onClose }: { onClose: () => void }) {
  const { groups, refreshGroups, refreshAppState, jobs, refreshJobs, toast, loadFeed } = useStore();
  const { t, lang } = useLang();
  const [dialogs, setDialogs] = useState<Dialog[] | null>(null);
  const [listing, setListing] = useState<Listing>({ state: "idle" });
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [armed, setArmed] = useState<{ id: number; mode: "untrack" | "delete" } | null>(null);
  const armTimer = useRef<number | null>(null);

  // tracked-set helpers
  const trackedIds = new Set(groups.map((g) => g.chat_id));

  useEffect(() => {
    if (dialogs === null) void loadDialogs(false);
    return () => { if (armTimer.current) clearTimeout(armTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshDialogs = () => void loadDialogs(true);

  async function loadDialogs(force: boolean) {
    try {
      if (!force) {
        const r = await api.dialogsGet();
        if (r.ready && r.dialogs) {
          setDialogs(r.dialogs);
          return;
        }
      }
      setListing({ state: "waiting", note: t("system.mm.loadingGroups") });
      let tries = 0;
      while (true) {
        const status = await api.jobStatus();
        if (status.running || status.queued.length > 0) {
          setListing({
            state: "waiting",
            note: t("system.mm.waitingJob", {
              job: t(jobKey(status.name || status.queued[0])),
            }),
          });
          await sleep(1300);
          continue;
        }
        const r0 = await api.dialogsGet();
        if (r0.ready && r0.dialogs) {
          setDialogs(r0.dialogs);
          break;
        }
        if (++tries > 3) {
          toast(t("system.mm.loadFailed"), "err");
          break;
        }
        await api.dialogsStart();
        void refreshJobs();
        setListing({ state: "listing" });
        await sleep(1300);
      }
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setListing({ state: "idle" });
    }
  }

  const trackChecked = async () => {
    const ids = [...checked].filter((id) => !trackedIds.has(id));
    if (!ids.length) {
      toast(t("system.mm.tickFirst"), "info");
      return;
    }
    try {
      const r = await api.track(ids);
      if (r.started === false) {
        toast(r.reason === "already_tracked" ? t("system.alreadyTracking") : t("system.trackFailed"), "info");
        return;
      }
      const behind = r.queued_behind?.length ?? 0;
      toast(
        behind > 0
          ? t("system.mm.trackedQueued", {
            groups: nounT(t, lang, "system.pl.group", ids.length),
            jobs: nounT(t, lang, "system.pl.job", behind),
          })
          : t("system.mm.trackedBackfill", {
            groups: nounT(t, lang, "system.pl.group", ids.length),
          }),
        "good",
      );
      setChecked(new Set());
      await refreshGroups();
      void refreshJobs();   // kick off live polling for the backfill
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const doUntrack = async (id: number, del: boolean) => {
    try {
      await api.untrack([id], del);
      toast(
        del ? t("system.mm.untrackedDeleted") : t("system.mm.untrackedKept"),
        del ? "good" : "info",
      );
      await Promise.all([refreshGroups(), refreshAppState()]);
      void loadFeed(true);
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const arm = (id: number, mode: "untrack" | "delete") => {
    if (armed?.id === id && armed.mode === mode) {
      setArmed(null);
      void doUntrack(id, mode === "delete");
      return;
    }
    setArmed({ id, mode });
    if (armTimer.current) clearTimeout(armTimer.current);
    armTimer.current = window.setTimeout(() => setArmed(null), 4000);
  };

  const busy = listing.state !== "idle";

  const renderOthers = () => {
    if (!dialogs) return null;
    const others = dialogs.filter((d) => !trackedIds.has(d.chat_id));
    if (!others.length) {
      return <p className="mm-note dim">{t("system.mm.allTracked")}</p>;
    }
    return others.map((d) => (
      <label key={d.chat_id} className="mm-row clickable">
        <input
          type="checkbox"
          checked={checked.has(d.chat_id)}
          onChange={() => setChecked((s) => {
            const n = new Set(s);
            if (n.has(d.chat_id)) n.delete(d.chat_id);
            else n.add(d.chat_id);
            return n;
          })}
        />
        <span className="g-ic">
          {d.kind === "channel" ? <Ic.Radio size={14} /> : <Ic.Users size={14} />}
        </span>
        <span className="g-main">
          <span className="g-title" dir="auto">{d.title}</span>
          <span className="g-meta">{d.chat_id}{d.username ? ` · @${d.username}` : ""}</span>
        </span>
      </label>
    ));
  };

  return (
    <Modal
      title={t("groups.manage")}
      wide
      onClose={onClose}
      footer={
        <>
          <button className="btn primary" disabled={busy} onClick={() => void trackChecked()}>
            {t("system.mm.trackSelected")}{checked.size > 0 ? ` (${checked.size})` : ""}
          </button>
          <button className="btn ghost" onClick={refreshDialogs} disabled={busy}>
            <Ic.RefreshCw size={13} /> {t("system.mm.reloadList")}
          </button>
        </>
      }
    >
      <div className="label" style={{ marginTop: 6 }}>{t("system.mm.trackedSection")}</div>
      {groups.length === 0 && <p className="mm-note dim">{t("system.mm.noneTrackedHint")}</p>}
      {groups.map((g) => (
        <div key={g.chat_id} className="mm-row">
          <span className="g-ic">
            {g.kind === "channel" ? <Ic.Radio size={14} /> : <Ic.Users size={14} />}
          </span>
          <span className="g-main">
            <span className="g-title" dir="auto">{g.title}</span>
            <span className="g-meta">
              {t("groups.msgs", { n: nfmt(g.message_count) })}
              {g.last_message ? ` · ${t("system.lastMessage", { date: fmtDate(g.last_message) })}` : ""}
            </span>
          </span>
          <span className="row-actions">
            <button
              className={`btn ghost sm ${armed?.id === g.chat_id && armed.mode === "untrack" ? "armed" : ""}`}
              title={t("system.mm.untrackTitle")}
              onClick={() => arm(g.chat_id, "untrack")}
            >
              {armed?.id === g.chat_id && armed.mode === "untrack"
                ? <><Ic.CircleAlert size={13} /> {t("system.mm.untrackArmed")}</>
                : <><Ic.CircleX size={13} /> {t("system.mm.untrack")}</>}
            </button>
            <button
              className={`btn danger sm ${armed?.id === g.chat_id && armed.mode === "delete" ? "armed" : ""}`}
              title={t("system.mm.deleteTitle")}
              onClick={() => arm(g.chat_id, "delete")}
            >
              {armed?.id === g.chat_id && armed.mode === "delete"
                ? <><Ic.CircleAlert size={13} /> {t("system.mm.deleteArmed", { n: nfmt(g.message_count) })}</>
                : <><Ic.Trash size={13} /> {t("action.delete")}</>}
            </button>
          </span>
        </div>
      ))}

      <div className="label" style={{ marginTop: 16 }}>{t("system.mm.othersSection")}</div>

      {busy && (
        <div className="mm-progress">
          <Ic.Spin size={13} className="spin" />
          <div>
            <div>{listing.state === "waiting" ? listing.note : t("system.mm.fetching")}</div>
            <pre className="mm-log">{jobs?.log?.split("\n").slice(-4).join("\n") || t("system.starting")}</pre>
            {jobs?.running && (
              <button className="btn danger sm" style={{ marginTop: 8 }}
                onClick={async () => { await api.jobStop(false); toast(t("system.mm.stoppingList"), "info"); }}>
                <Ic.CircleOff size={13} /> {t("system.jobs.stopCurrent")}
              </button>
            )}
          </div>
        </div>
      )}

      {!busy && dialogs === null && (
        <div className="mm-note dim">{t("state.loading")}</div>
      )}
      {!busy && dialogs !== null && renderOthers()}
    </Modal>
  );
}

/** Job center: queue visibility, status chips, live log, stop/cancel/retry. */
import { useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import { jobKey } from "../utils/format";
import { Ic } from "../design/icons";
import { Modal } from "./Modal";

type TFn = (key: string, vars?: Record<string, string | number>) => string;

function StatusChip({ name, ok, running, queued, t }: {
  name: string; ok: boolean; running?: boolean; queued?: boolean; t: TFn;
}) {
  const label = name ? t(jobKey(name)) : t("sync.idle");
  if (running) {
    return (
      <span className="badge accent">
        <Ic.Spin size={9} className="spin" />{label}
      </span>
    );
  }
  if (queued) return <span className="badge warn">{label} · {t("system.jobs.queued")}</span>;
  if (!name) return <span className="badge">{t("sync.idle")}</span>;
  return (
    <span className={`badge ${ok ? "good" : "err"}`}>
      {label} · {ok ? t("job.finished") : t("job.failed")}
    </span>
  );
}

export function JobCenter({ onClose }: { onClose: () => void }) {
  const { jobs, refreshJobs, toast, refreshAppState, refreshGroups } = useStore();
  const { t } = useLang();
  const [showLog, setShowLog] = useState(true);

  const running = jobs?.running ?? false;
  const queued = jobs?.queued ?? [];
  const lastDone = jobs?.last_done;

  const stop = async (clearQueue = false) => {
    try {
      const r = await api.jobStop(clearQueue);
      if (r.stopping) toast(t("system.jobs.stoppingSaved"), "info");
      if (r.cleared.length) {
        toast(t("system.jobs.cancelledQueued", {
          jobs: r.cleared.map((n) => t(jobKey(n))).join(", "),
        }), "info");
      }
      await refreshJobs();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const retry = async () => {
    if (!lastDone) return;
    try {
      if (lastDone.name === "sync") {
        await api.sync();
        toast(t("system.jobs.retrySync"), "good");
      } else if (lastDone.name === "dialogs") {
        await api.dialogsStart();
        toast(t("system.jobs.retryDialogs"), "good");
      } else {
        toast(t("system.jobs.retryTrack", { manage: t("groups.manage") }), "info");
        return;
      }
      await refreshJobs();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <Modal
      title={t("nav.jobs")}
      wide
      onClose={onClose}
      footer={
        <>
          {running && (
            <button className="btn danger" onClick={() => void stop(false)}>
              <Ic.CircleOff size={13} /> {t("system.jobs.stopCurrent")}
            </button>
          )}
          {queued.length > 0 && (
            <button className="btn danger" onClick={() => void stop(true)}>
              {t("system.jobs.cancelQueued", { n: queued.length })}
            </button>
          )}
          {lastDone && !lastDone.ok && !running && (
            <button className="btn primary" onClick={() => void retry()}>
              <Ic.RotateCcw size={13} /> {t("system.jobs.retryLast")}
            </button>
          )}
          <span style={{ flex: 1 }} />
          <button
            className="btn ghost"
            onClick={() => { void refreshJobs(); void refreshAppState(); void refreshGroups(); }}
          >
            <Ic.RefreshCw size={13} /> {t("system.refresh")}
          </button>
        </>
      }
    >
      <div className="job-rows">
        <div className="job-row">
          <StatusChip name={jobs?.name || "idle"} ok={!!lastDone?.ok} running={running} t={t} />
          <span className="job-desc">
            {running ? t("system.jobs.usingSession") : t("system.jobs.noneRunning")}
          </span>
        </div>
        {queued.map((n, i) => (
          <div key={i} className="job-row">
            <StatusChip name={n} ok={false} queued t={t} />
            <span className="job-desc">{t("system.jobs.runsAfter")}</span>
          </div>
        ))}
        {lastDone && (
          <div className="job-row">
            <StatusChip name={lastDone.name} ok={lastDone.ok} t={t} />
            <span className="job-desc">
              {new Date(lastDone.finished_at * 1000).toLocaleTimeString()} —{" "}
              {lastDone.ok ? t("job.finished") : t("job.failed")}
            </span>
          </div>
        )}
      </div>

      <div className="side-head" style={{ marginTop: 14 }}>
        <span className="label">{t("system.jobs.liveLog")}</span>
        <button className="link" onClick={() => setShowLog((s) => !s)}>
          {showLog ? t("onboarding.form.hide") : t("onboarding.form.show")}
        </button>
      </div>
      {showLog && (
        <pre className="job-log">{jobs?.log || t("system.jobs.noOutput")}</pre>
      )}
    </Modal>
  );
}

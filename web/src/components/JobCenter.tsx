/** Job center: queue visibility, status chips, live log, stop/cancel/retry. */
import { useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { jobLabel } from "../utils/format";
import { Modal } from "./Modal";

function StatusChip({ name, ok, running, queued }: {
  name: string; ok: boolean; running?: boolean; queued?: boolean;
}) {
  const label = name ? jobLabel(name) : "idle";
  if (running) return <span className="badge accent"><span className="spinner" style={{ width: 9, height: 9, borderWidth: 1.5, marginInlineEnd: 4 }} />{label}</span>;
  if (queued) return <span className="badge warn">{label} · queued</span>;
  if (!name) return <span className="badge">idle</span>;
  return <span className={`badge ${ok ? "good" : "err"}`}>{label} · {ok ? "completed" : "failed"}</span>;
}

export function JobCenter({ onClose }: { onClose: () => void }) {
  const { jobs, refreshJobs, toast, refreshAppState, refreshGroups } = useStore();
  const [showLog, setShowLog] = useState(true);

  const running = jobs?.running ?? false;
  const queued = jobs?.queued ?? [];
  const lastDone = jobs?.last_done;

  const stop = async (clearQueue = false) => {
    try {
      const r = await api.jobStop(clearQueue);
      if (r.stopping) toast("Stopping at the next checkpoint — progress is saved", "info");
      if (r.cleared.length) toast(`Cancelled queued: ${r.cleared.join(", ")}`, "info");
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
        toast("Retry: sync queued", "good");
      } else if (lastDone.name === "dialogs") {
        await api.dialogsStart();
        toast("Retry: group listing queued", "good");
      } else {
        toast("Open Manage groups to retry tracking", "info");
        return;
      }
      await refreshJobs();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <Modal
      title="Jobs"
      wide
      onClose={onClose}
      footer={
        <>
          {running && <button className="btn danger" onClick={() => void stop(false)}>■ Stop current job</button>}
          {queued.length > 0 && <button className="btn danger" onClick={() => void stop(true)}>Cancel {queued.length} queued</button>}
          {lastDone && !lastDone.ok && !running && <button className="btn primary" onClick={() => void retry()}>↻ Retry last job</button>}
          <span style={{ flex: 1 }} />
          <button className="btn ghost" onClick={() => { void refreshJobs(); void refreshAppState(); void refreshGroups(); }}>Refresh</button>
        </>
      }
    >
      <div className="job-rows">
        <div className="job-row">
          <StatusChip name={jobs?.name || "idle"} ok={!!lastDone?.ok} running={running} />
          <span className="job-desc">
            {running ? "The current job is using the Telegram session." : "No job is running."}
          </span>
        </div>
        {queued.map((n, i) => (
          <div key={i} className="job-row">
            <StatusChip name={n} ok={false} queued />
            <span className="job-desc">Runs after the current job finishes.</span>
          </div>
        ))}
        {lastDone && (
          <div className="job-row">
            <StatusChip name={lastDone.name} ok={lastDone.ok} />
            <span className="job-desc">
              {new Date(lastDone.finished_at * 1000).toLocaleTimeString()} — {lastDone.ok ? "completed" : "failed"}
            </span>
          </div>
        )}
      </div>

      <div className="side-head" style={{ marginTop: 14 }}>
        <span className="label">Live log</span>
        <button className="link" onClick={() => setShowLog((s) => !s)}>{showLog ? "hide" : "show"}</button>
      </div>
      {showLog && (
        <pre className="job-log">{jobs?.log || "(no output yet)"}</pre>
      )}
    </Modal>
  );
}

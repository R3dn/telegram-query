/** Filter bar: mode segment, date presets, sender/media/sort/star filters,
 *  active chips, and saving the current search (v0.4). */
import { useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { Sender } from "../api/types";
import { Modal } from "./Modal";

export function FilterBar() {
  const {
    mode, setMode, filters, setFilters, dateChip, setDateChip,
    senders, selection, clearSelection, groups, hasMore,
    q, refreshSaved, toast,
  } = useStore();

  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");

  const activeChips: { label: string; clear: () => void }[] = [];
  if (filters.from) activeChips.push({ label: `from ${filters.from}`, clear: () => setDateChip("all") });
  if (filters.sender)
    activeChips.push({ label: `sender: ${filters.sender.slice(0, 24)}`, clear: () => setFilters({ sender: "" }) });
  if (filters.media === "1") activeChips.push({ label: "with images", clear: () => setFilters({ media: "" }) });
  if (filters.media === "0") activeChips.push({ label: "text only", clear: () => setFilters({ media: "" }) });
  if (filters.sort === "asc") activeChips.push({ label: "oldest first", clear: () => setFilters({ sort: "desc" }) });
  if (filters.starred) activeChips.push({ label: "⭐ starred", clear: () => setFilters({ starred: false }) });
  if (selection.size > 0)
    activeChips.push({
      label: `${selection.size} group${selection.size > 1 ? "s" : ""}`,
      clear: () => clearSelection(),
    });

  const scope = selection.size === 0
    ? "all groups"
    : groups.filter((g) => selection.has(g.chat_id)).map((g) => g.title).join(", ");

  const savable = (mode === "search" && !!q.trim()) ||
    !!(filters.from || filters.to || filters.sender || filters.media || selection.size);

  const saveCurrent = async () => {
    const name = saveName.trim();
    if (!name) return;
    try {
      await api.savedCreate({
        name,
        q: mode === "search" ? q : "",
        chat_ids: [...selection],
        sender: filters.sender,
        media: filters.media,
        date_from: filters.from,
        date_to: filters.to,
        sort: filters.sort,
      });
      toast(`Saved “${name}”`, "good");
      setSaveOpen(false);
      setSaveName("");
      await refreshSaved();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="filterbar">
      <div className="fb-row">
        <div className="seg">
          <button className={mode === "browse" ? "on" : ""} onClick={() => setMode("browse")}>Browse</button>
          <button className={mode === "search" ? "on" : ""} onClick={() => { if (mode !== "search") setMode("search"); }}>Search</button>
        </div>

        <div className="chips">
          {(["all", "today", "7d", "30d"] as const).map((c) => (
            <button key={c} className={`chip ${dateChip === c ? "on" : ""}`} onClick={() => setDateChip(c)}>
              {c === "all" ? "All time" : c === "7d" ? "7 days" : c === "30d" ? "30 days" : "Today"}
            </button>
          ))}
          <button className={`chip ${dateChip === "custom" ? "on" : ""}`} onClick={() => setDateChip("custom")}>📅</button>
        </div>
        {dateChip === "custom" && (
          <span className="date-range">
            <input type="date" className="input" style={{ width: 130 }} value={filters.from}
              onChange={(e) => { setFilters({ from: e.target.value }); setDateChip("custom"); }} />
            <span>→</span>
            <input type="date" className="input" style={{ width: 130 }} value={filters.to}
              onChange={(e) => { setFilters({ to: e.target.value }); setDateChip("custom"); }} />
          </span>
        )}

        <select id="f-sender" className="input" style={{ maxWidth: 190 }} title="Sender"
          value={filters.sender} onChange={(e) => setFilters({ sender: e.target.value })}>
          <option value="">Any sender</option>
          {senders.map((s: Sender) => (
            <option key={s.sender_name} value={s.sender_name}>{s.sender_name} ({s.count})</option>
          ))}
        </select>

        <select className="input" style={{ maxWidth: 130 }} title="Message type"
          value={filters.media} onChange={(e) => setFilters({ media: e.target.value })}>
          <option value="">Any type</option>
          <option value="1">With images</option>
          <option value="0">Text only</option>
        </select>

        <select className="input" style={{ maxWidth: 140 }} title="Sort"
          value={filters.sort} onChange={(e) => setFilters({ sort: e.target.value })}>
          <option value="desc">Newest first</option>
          <option value="asc">Oldest first</option>
        </select>

        <button
          className={`chip ${filters.starred ? "on" : ""}`}
          title="Show only bookmarked messages"
          onClick={() => setFilters({ starred: !filters.starred })}
        >
          ⭐ Starred
        </button>

        <button
          className="chip"
          title="Save this search + filters under a name"
          disabled={!savable}
          onClick={() => setSaveOpen(true)}
        >
          💾 Save search
        </button>
      </div>

      <div className="fb-meta">
        <span className="fb-scope" dir="auto" title={scope}>{scope}</span>
        <span className="fb-chips">
          {activeChips.map((c, i) => (
            <button key={i} className="chip on" onClick={c.clear}>
              {c.label} <span className="x">✕</span>
            </button>
          ))}
        </span>
        {mode === "browse" && hasMore && <span className="fb-more">more on scroll</span>}
      </div>

      {saveOpen && (
        <Modal title="Save search" onClose={() => setSaveOpen(false)}
          footer={
            <>
              <button className="btn ghost sm" onClick={() => setSaveOpen(false)}>Cancel</button>
              <button className="btn primary sm" disabled={!saveName.trim()} onClick={() => void saveCurrent()}>
                Save
              </button>
            </>
          }>
          <p className="mm-note dim">
            Saves the query, selected groups, and filters - not the result rows.
            Run it any time to re-execute against the live archive.
          </p>
          <input
            className="input"
            autoFocus
            placeholder="Name, e.g. أروع العروض / best deals"
            value={saveName}
            dir="auto"
            maxLength={100}
            onChange={(e) => setSaveName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && saveName.trim()) void saveCurrent();
            }}
          />
          <div className="save-summary">
            {(mode === "search" && q) ? <span className="chip on">“{q.slice(0, 40)}”</span> : null}
            {selection.size > 0 && <span className="chip on">{selection.size} group(s)</span>}
            {(filters.from || filters.to) && <span className="chip on">{filters.from || "…"} → {filters.to || "…"}</span>}
            {filters.sender && <span className="chip on">sender</span>}
            {filters.media && <span className="chip on">{filters.media === "1" ? "images" : "text"}</span>}
          </div>
        </Modal>
      )}
    </div>
  );
}

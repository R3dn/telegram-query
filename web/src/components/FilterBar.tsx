/** Filter bar: mode segment, date presets, sender/media/sort, active chips. */
import { useStore } from "../state/store";
import type { Sender } from "../api/types";

export function FilterBar() {
  const {
    mode, setMode, filters, setFilters, dateChip, setDateChip,
    senders, selection, clearSelection, groups, hasMore,
  } = useStore();

  const activeChips: { label: string; clear: () => void }[] = [];
  if (filters.from) activeChips.push({ label: `from ${filters.from}`, clear: () => setDateChip("all") });
  if (filters.sender)
    activeChips.push({ label: `sender: ${filters.sender.slice(0, 24)}`, clear: () => setFilters({ sender: "" }) });
  if (filters.media === "1") activeChips.push({ label: "with images", clear: () => setFilters({ media: "" }) });
  if (filters.media === "0") activeChips.push({ label: "text only", clear: () => setFilters({ media: "" }) });
  if (filters.sort === "asc") activeChips.push({ label: "oldest first", clear: () => setFilters({ sort: "desc" }) });
  if (selection.size > 0)
    activeChips.push({
      label: `${selection.size} group${selection.size > 1 ? "s" : ""}`,
      clear: () => clearSelection(),
    });

  const scope = selection.size === 0
    ? "all groups"
    : groups.filter((g) => selection.has(g.chat_id)).map((g) => g.title).join(", ");

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
    </div>
  );
}

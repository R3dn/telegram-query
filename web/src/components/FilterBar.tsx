/** Filter bar: mode segment, date presets, sender/media/sort/star filters,
 *  active chips, and saving the current search. */
import { useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { Sender } from "../api/types";
import { Modal } from "./Modal";
import { Ic } from "../design/icons";

export function FilterBar() {
  const {
    mode, setMode, filters, setFilters, dateChip, setDateChip,
    senders, selection, clearSelection, groups, hasMore,
    q, refreshSaved, toast,
  } = useStore();
  const { t } = useLang();

  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");

  const activeChips: { label: string; clear: () => void }[] = [];
  if (filters.from)
    activeChips.push({ label: t("filter.chip.from", { date: filters.from }), clear: () => setDateChip("all") });
  if (filters.sender)
    activeChips.push({ label: t("filter.chip.sender", { name: filters.sender.slice(0, 24) }), clear: () => setFilters({ sender: "" }) });
  if (filters.media === "1") activeChips.push({ label: t("filter.chip.images"), clear: () => setFilters({ media: "" }) });
  if (filters.media === "0") activeChips.push({ label: t("filter.chip.text"), clear: () => setFilters({ media: "" }) });
  if (filters.sort === "asc") activeChips.push({ label: t("filter.chip.oldest"), clear: () => setFilters({ sort: "desc" }) });
  if (filters.starred) activeChips.push({ label: t("filter.chip.starred"), clear: () => setFilters({ starred: false }) });
  if (selection.size > 0)
    activeChips.push({
      label: t("filter.chip.groups", { n: selection.size }),
      clear: () => clearSelection(),
    });

  const scope = selection.size === 0
    ? t("filter.allGroups")
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
      toast(t("filter.savedToast", { name }), "good");
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
          <button className={mode === "browse" ? "on" : ""} onClick={() => setMode("browse")}>{t("filter.browse")}</button>
          <button className={mode === "search" ? "on" : ""} onClick={() => { if (mode !== "search") setMode("search"); }}>{t("filter.search")}</button>
        </div>

        <div className="chips">
          {(["all", "today", "7d", "30d"] as const).map((c) => (
            <button key={c} className={`chip ${dateChip === c ? "on" : ""}`} onClick={() => setDateChip(c)}>
              {c === "all" ? t("filter.allTime") : c === "7d" ? t("filter.days", { n: 7 }) : c === "30d" ? t("filter.days", { n: 30 }) : t("filter.today")}
            </button>
          ))}
          <button
            className={`chip ${dateChip === "custom" ? "on" : ""}`}
            title={t("filter.custom")}
            onClick={() => setDateChip("custom")}
          >
            <Ic.CalendarDays size={13} />
          </button>
        </div>
        {dateChip === "custom" && (
          <span className="date-range">
            <input type="date" className="input" style={{ width: 130 }} value={filters.from}
              onChange={(e) => { setFilters({ from: e.target.value }); setDateChip("custom"); }} />
            <span><Ic.ArrowRight size={13} /></span>
            <input type="date" className="input" style={{ width: 130 }} value={filters.to}
              onChange={(e) => { setFilters({ to: e.target.value }); setDateChip("custom"); }} />
          </span>
        )}

        <select id="f-sender" className="input" style={{ maxWidth: 190 }} title={t("filter.anySender")}
          value={filters.sender} onChange={(e) => setFilters({ sender: e.target.value })}>
          <option value="">{t("filter.anySender")}</option>
          {senders.map((s: Sender) => (
            <option key={s.sender_name} value={s.sender_name}>{s.sender_name} ({s.count})</option>
          ))}
        </select>

        <select className="input" style={{ maxWidth: 130 }} title={t("filter.anyType")}
          value={filters.media} onChange={(e) => setFilters({ media: e.target.value })}>
          <option value="">{t("filter.anyType")}</option>
          <option value="1">{t("filter.withImages")}</option>
          <option value="0">{t("filter.textOnly")}</option>
        </select>

        <select className="input" style={{ maxWidth: 140 }} title={t("filter.newestFirst")}
          value={filters.sort} onChange={(e) => setFilters({ sort: e.target.value })}>
          <option value="desc">{t("filter.newestFirst")}</option>
          <option value="asc">{t("filter.oldestFirst")}</option>
        </select>

        <button
          className={`chip ${filters.starred ? "on" : ""}`}
          title={t("filter.starredHint")}
          onClick={() => setFilters({ starred: !filters.starred })}
        >
          <Ic.Star size={13} /> {t("filter.starred")}
        </button>

        <button
          className="chip"
          title={t("filter.saveHint")}
          disabled={!savable}
          onClick={() => setSaveOpen(true)}
        >
          <Ic.Save size={13} /> {t("filter.save")}
        </button>
      </div>

      <div className="fb-meta">
        <span className="fb-scope" dir="auto" title={scope}>{scope}</span>
        <span className="fb-chips">
          {activeChips.map((c, i) => (
            <button key={i} className="chip on" onClick={c.clear}>
              {c.label} <span className="x"><Ic.Close size={11} /></span>
            </button>
          ))}
        </span>
        {mode === "browse" && hasMore && <span className="fb-more">{t("filter.moreOnScroll")}</span>}
      </div>

      {saveOpen && (
        <Modal title={t("filter.saveTitle")} onClose={() => setSaveOpen(false)}
          footer={
            <>
              <button className="btn ghost sm" onClick={() => setSaveOpen(false)}>{t("action.cancel")}</button>
              <button className="btn primary sm" disabled={!saveName.trim()} onClick={() => void saveCurrent()}>
                {t("action.save")}
              </button>
            </>
          }>
          <p className="mm-note dim">{t("filter.saveNote")}</p>
          <input
            className="input"
            autoFocus
            placeholder={t("filter.savePlaceholder")}
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
            {selection.size > 0 && <span className="chip on">{t("filter.chip.groups", { n: selection.size })}</span>}
            {(filters.from || filters.to) && <span className="chip on">{filters.from || "…"} <Ic.ArrowRight size={11} /> {filters.to || "…"}</span>}
            {filters.sender && <span className="chip on">{t("filter.chip.sender", { name: "" })}</span>}
            {filters.media && <span className="chip on">{filters.media === "1" ? t("filter.chip.images") : t("filter.chip.text")}</span>}
          </div>
        </Modal>
      )}
    </div>
  );
}

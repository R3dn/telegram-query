/** Entities workspace (v0.7): the gazetteer of named things your
 *  communities talk about - brands, products, orgs, projects, places.
 *  Every mention links to its original message; the gazetteer is
 *  human-controlled (add / rename / merge / ignore). NEVER people. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import type { EntitiesSettings, Entity, EntityDetail } from "../api/types";
import { nfmt } from "../utils/format";
import { Ic } from "../design/icons";
import { EmptyState } from "./EmptyState";

type TFunc = ReturnType<typeof useLang>["t"];

export function EntityView() {
  const { appState, toast, select, setRightTab, selection } = useStore();
  const { t } = useLang();
  const [rows, setRows] = useState<Entity[] | null>(null);
  const [settings, setSettings] = useState<EntitiesSettings | null>(null);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"recent" | "mentions">("recent");
  const [open, setOpen] = useState<EntityDetail | null>(null);
  const [adding, setAdding] = useState(false);

  const load = async (query = q) => {
    try {
      setRows(await api.entitiesList({ q: query, sort, groups: [...selection] }));
    } catch (e) {
      toast((e as Error).message, "err");
      setRows([]);
    }
  };

  useEffect(() => { void load(); /* eslint-disable-line */ }, [sort, selection]);

  useEffect(() => {
    void api.entitiesSettings().then(setSettings).catch(() => {});
  }, []);

  const openEntity = async (id: number) => {
    try {
      setOpen(await api.entityGet(id, 30, 0));
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const openMessage = (m: { chat_id: number; msg_id: number }) => {
    void (async () => {
      try {
        const full = await api.message(m.chat_id, m.msg_id);
        select(full);
        setRightTab("details");
      } catch {
        toast(t("discover.toast.openOriginalFailed"), "err");
      }
    })();
  };

  const patch = async (id: number, body: Record<string, unknown>, note: string) => {
    try {
      await api.entityPatch(id, body);
      toast(note, "info");
      await load();
      if (open && open.id === id) setOpen(null);
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const mergeInto = async (targetId: number) => {
    if (!open || targetId === open.id) return;
    try {
      const r = await api.entityMerge(open.id, targetId);
      toast(t("entities.toast.merged"), "good");
      setOpen(r);
      await load();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const toggleAuto = async () => {
    if (!settings) return;
    try {
      const r = await api.entitiesAuto(!settings.auto);
      setSettings({ ...settings, auto: r.auto });
      toast(r.auto
        ? t("entities.toast.autoOn")
        : t("entities.toast.autoOff"), "info");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <span className="nav-ic"><Ic.MapPin size={18} /></span>
        <h2 className="bm-title">{t("nav.entities")}</h2>
        <span className="dim" style={{ fontSize: 12 }}>
          {t("entities.subtitle")}
        </span>
        <span style={{ flex: 1 }} />
        <input className="input" style={{ maxWidth: 180 }} placeholder={t("entities.searchPlaceholder")}
               value={q} onChange={(e) => { setQ(e.target.value); void load(e.target.value); }} />
        <select className="input" style={{ maxWidth: 130 }} value={sort}
                onChange={(e) => setSort(e.target.value as "recent" | "mentions")}>
          <option value="recent">{t("entities.sort.recent")}</option>
          <option value="mentions">{t("entities.sort.mentions")}</option>
        </select>
        <button className="btn ghost sm" onClick={() => setAdding((a) => !a)}
                title={adding ? t("action.close") : t("entities.add.submit")}>
          {adding
            ? <Ic.Close size={14} />
            : <><Ic.Plus size={14} /> {t("entities.add.submit")}</>}
        </button>
      </div>

      {settings?.ai_configured && (
        <div className="digest-groups">
          <label className="label" style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={settings.auto} onChange={() => void toggleAuto()} />
            {t("entities.autoLabel")}
          </label>
        </div>
      )}

      {adding && <AddEntityForm t={t} onDone={() => { setAdding(false); void load(); }} />}

      <div className="feed">
        {open ? (
          <div className="entity-detail">
            <div className="bm-head">
              <span className="badge">{open.kind}</span>
              <b className="bm-grp" dir="auto">{open.name}</b>
              <span className="dim" style={{ fontSize: 12 }}>
                {t("entities.detail.stats", { n: nfmt(open.mentions_count), g: open.groups.length })}
              </span>
              <span style={{ flex: 1 }} />
              <button className="btn ghost sm" onClick={() => setOpen(null)}>
                <Ic.ChevronLeft size={13} /> {t("entities.backToList")}
              </button>
            </div>
            {open.aliases.length > 0 && (
              <div className="story-groups" style={{ margin: "0 0 8px" }}>
                {open.aliases.map((a) => (
                  <span key={a} className="chip static" dir="auto">{a}</span>
                ))}
              </div>
            )}
            {open.groups.length > 0 && (
              <div className="story-groups" style={{ margin: "0 0 8px" }}>
                {open.groups.map((g) => (
                  <span key={g.chat_id} className="chip static" dir="auto"
                        title={t("entities.detail.groupChip", { n: g.n })}>
                    {g.title} ({g.n})
                  </span>
                ))}
              </div>
            )}
            <div className="q-acts" style={{ margin: "0 0 10px", flexWrap: "wrap" }}>
              <button className="btn ghost sm"
                      onClick={() => void patch(open.id, { ignored: true }, t("entities.toast.hidden"))}>
                <Ic.Ban size={13} /> {t("entities.hideFromDiscovery")}
              </button>
              {rows && rows.filter((r) => r.id !== open.id).length > 0 && (
                <select className="input" style={{ maxWidth: 220 }} value=""
                        title={t("entities.mergeHint")}
                        onChange={(e) => {
                          if (e.target.value) void mergeInto(Number(e.target.value));
                        }}>
                  <option value="">{t("entities.mergeInto")}</option>
                  {rows!.filter((r) => r.id !== open.id).map((r) => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              )}
              <button className="btn danger sm"
                      onClick={() => {
                        if (!open) return;
                        void (async () => {
                          try {
                            await api.entityDelete(open.id);
                            toast(t("entities.toast.deleted"), "info");
                            setOpen(null);
                            await load();
                          } catch (e) { toast((e as Error).message, "err"); }
                        })();
                      }}>
                <Ic.Trash size={13} /> {t("action.delete")}
              </button>
            </div>
            <div className="label">{t("entities.detail.mentions")}</div>
            {open.mentions.length === 0 && (
              <div className="side-note">{t("entities.detail.noMentions")}</div>
            )}
            {open.mentions.map((m) => (
              <button key={`${m.chat_id}-${m.msg_id}`} className="src-row"
                      style={{ display: "flex" }} onClick={() => openMessage(m)}>
                <span className="src-title" dir="auto">{m.chat_title}</span>
                <span className="src-date">{(m.date ?? "").slice(0, 10)}</span>
                <span className="src-text" dir="auto">{m.text.slice(0, 120)}</span>
              </button>
            ))}
            {open.mentions_count > open.mentions.length && (
              <div className="side-note">
                {t("entities.detail.older", { n: open.mentions_count - open.mentions.length })}
              </div>
            )}
          </div>
        ) : rows === null ? (
          <div className="side-note">{t("state.loading")}</div>
        ) : rows.length === 0 ? (
          <EmptyState icon="MapPin" title={t("entities.empty.title")}
            hint={appState?.messages
              ? t("entities.empty.hintSynced")
              : t("entities.empty.hintNoSync")} />
        ) : rows.map((r) => (
          <div key={r.id} className="entity-row">
            <button className="entity-main" onClick={() => void openEntity(r.id)}>
              <span className="g-title" dir="auto">{r.name}</span>
              <span className="g-meta">
                <span className="badge" style={{ marginInlineEnd: 6 }}>{r.kind}</span>
                {r.mentions === 1
                  ? t("entities.row.mention", { n: nfmt(r.mentions) })
                  : t("entities.row.mentions", { n: nfmt(r.mentions) })}
                {r.recent > 0 && <>{" · "}{t("entities.row.recent", { n: r.recent })}</>}
                {r.last_seen && <>{" · "}{t("entities.row.lastSeen", { d: (r.last_seen ?? "").slice(0, 10) })}</>}
              </span>
            </button>
            <button className="saved-act" title={t("entities.hideHint")}
                    onClick={() => void patch(r.id, { ignored: true }, t("entities.toast.hidden"))}>
              <Ic.Ban size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function AddEntityForm({ t, onDone }: { t: TFunc; onDone: () => void }) {
  const { toast } = useStore();
  const [name, setName] = useState("");
  const [kind, setKind] = useState("brand");
  const [aliases, setAliases] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!name.trim() || saving) return;
    setSaving(true);
    try {
      await api.entityCreate({
        name: name.trim(), kind,
        aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean),
      });
      toast(t("entities.toast.added"), "good");
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="digest-groups" style={{ flexDirection: "column", alignItems: "stretch" }}>
      <div className="label">{t("entities.add.title")}</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input className="input" style={{ flex: 1, minWidth: 160 }} dir="auto"
               placeholder={t("entities.add.namePlaceholder")} value={name}
               onChange={(e) => setName(e.target.value)} />
        <select className="input" style={{ maxWidth: 120 }} value={kind}
                onChange={(e) => setKind(e.target.value)}>
          {["brand", "product", "org", "project", "place", "event", "other"].map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </select>
        <input className="input" style={{ flex: 1, minWidth: 160 }} dir="auto"
               placeholder={t("entities.add.aliasesPlaceholder")} value={aliases}
               onChange={(e) => setAliases(e.target.value)} />
        <button className="btn primary sm" disabled={saving || !name.trim()}
                onClick={() => void save()}>
          {saving ? <Ic.Spin size={13} className="spin" /> : t("entities.add.submit")}
        </button>
      </div>
    </div>
  );
}

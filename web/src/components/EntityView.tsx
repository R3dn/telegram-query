/** Entities workspace (v0.7): the gazetteer of named things your
 *  communities talk about - brands, products, orgs, projects, places.
 *  Every mention links to its original message; the gazetteer is
 *  human-controlled (add / rename / merge / ignore). NEVER people. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { EntitiesSettings, Entity, EntityDetail } from "../api/types";
import { nfmt } from "../utils/format";
import { EmptyState } from "./EmptyState";

export function EntityView() {
  const { appState, toast, select, setRightTab, selection } = useStore();
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
        toast("Could not open the original message", "err");
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
      toast("Entities merged - mentions and aliases moved over", "good");
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
        ? "AI discovery on - new entities are found incrementally after each sync (cached, opt-out any time)"
        : "AI discovery off - matching continues with the current gazetteer", "info");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="feed-col">
      <div className="bm-bar">
        <h2 className="bm-title">Entities</h2>
        <span className="dim" style={{ fontSize: 12 }}>
          brands, products, orgs, places - never individual people
        </span>
        <span style={{ flex: 1 }} />
        <input className="input" style={{ maxWidth: 180 }} placeholder="Search entities…"
               value={q} onChange={(e) => { setQ(e.target.value); void load(e.target.value); }} />
        <select className="input" style={{ maxWidth: 130 }} value={sort}
                onChange={(e) => setSort(e.target.value as "recent" | "mentions")}>
          <option value="recent">Recent activity</option>
          <option value="mentions">Most mentioned</option>
        </select>
        <button className="btn ghost sm" onClick={() => setAdding((a) => !a)}>
          {adding ? "✕" : "+ Add"}
        </button>
      </div>

      {settings?.ai_configured && (
        <div className="digest-groups">
          <label className="label" style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={settings.auto} onChange={() => void toggleAuto()} />
            AI discovery of new entities (opt-in; runs incrementally after each sync, cached by content)
          </label>
        </div>
      )}

      {adding && <AddEntityForm onDone={() => { setAdding(false); void load(); }} />}

      <div className="feed">
        {open ? (
          <div className="entity-detail">
            <div className="bm-head">
              <span className="badge">{open.kind}</span>
              <b className="bm-grp" dir="auto">{open.name}</b>
              <span className="dim" style={{ fontSize: 12 }}>
                {nfmt(open.mentions_count)} mentions · {open.groups.length} group(s)
              </span>
              <span style={{ flex: 1 }} />
              <button className="btn ghost sm" onClick={() => setOpen(null)}>← All entities</button>
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
                        title={`${g.n} mention(s)`}>
                    {g.title} ({g.n})
                  </span>
                ))}
              </div>
            )}
            <div className="q-acts" style={{ margin: "0 0 10px", flexWrap: "wrap" }}>
              <button className="btn ghost sm"
                      onClick={() => void patch(open.id, { ignored: true }, "Entity hidden")}>
                hide from discovery
              </button>
              {rows && rows.filter((r) => r.id !== open.id).length > 0 && (
                <select className="input" style={{ maxWidth: 220 }} value=""
                        title="Fold this entity's mentions and aliases into another one"
                        onChange={(e) => {
                          if (e.target.value) void mergeInto(Number(e.target.value));
                        }}>
                  <option value="">Merge this entity into…</option>
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
                            toast("Entity deleted (mentions were references only)", "info");
                            setOpen(null);
                            await load();
                          } catch (e) { toast((e as Error).message, "err"); }
                        })();
                      }}>
                delete
              </button>
            </div>
            <div className="label">Mentions</div>
            {open.mentions.length === 0 && (
              <div className="side-note">No mentions yet - they accumulate after each sync.</div>
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
              <div className="side-note">+{open.mentions_count - open.mentions.length} older mention(s)</div>
            )}
          </div>
        ) : rows === null ? (
          <div className="side-note">loading…</div>
        ) : rows.length === 0 ? (
          <EmptyState icon="📌" title="No entities yet"
            hint={appState?.messages
              ? "Add brands/products manually, seed them from your extracted deals (Rebuild data in Discover), or turn on AI discovery to find them incrementally after each sync."
              : "Sync your groups first."} />
        ) : rows.map((r) => (
          <div key={r.id} className="entity-row">
            <button className="entity-main" onClick={() => void openEntity(r.id)}>
              <span className="g-title" dir="auto">{r.name}</span>
              <span className="g-meta">
                <span className="badge" style={{ marginInlineEnd: 6 }}>{r.kind}</span>
                {nfmt(r.mentions)} mention{r.mentions === 1 ? "" : "s"}
                {r.recent > 0 && ` · ${r.recent} this week`}
                {r.last_seen && ` · last ${(r.last_seen ?? "").slice(0, 10)}`}
              </span>
            </button>
            <button className="saved-act" title="Hide from discovery (keep history)"
                    onClick={() => void patch(r.id, { ignored: true }, "Entity hidden")}>🚫</button>
          </div>
        ))}
      </div>
    </div>
  );
}

function AddEntityForm({ onDone }: { onDone: () => void }) {
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
      toast("Entity added", "good");
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="digest-groups" style={{ flexDirection: "column", alignItems: "stretch" }}>
      <div className="label">New entity</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input className="input" style={{ flex: 1, minWidth: 160 }} dir="auto"
               placeholder="Name, e.g. GadgetHub" value={name}
               onChange={(e) => setName(e.target.value)} />
        <select className="input" style={{ maxWidth: 120 }} value={kind}
                onChange={(e) => setKind(e.target.value)}>
          {["brand", "product", "org", "project", "place", "event", "other"].map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </select>
        <input className="input" style={{ flex: 1, minWidth: 160 }} dir="auto"
               placeholder="Aliases (comma-separated)" value={aliases}
               onChange={(e) => setAliases(e.target.value)} />
        <button className="btn primary sm" disabled={saving || !name.trim()}
                onClick={() => void save()}>
          {saving ? "…" : "Add"}
        </button>
      </div>
    </div>
  );
}

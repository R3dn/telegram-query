/** Thin fetch wrapper: JSON, error extraction, no secrets ever leave here. */
import type {
  AiUsage,
  Alert,
  AppState,
  AskResult,
  AskScope,
  AuthState,
  Brief,
  BookmarkRow,
  Deal,
  DealsSettings,
  Digest,
  DigestSchedule,
  Dialog,
  Faq,
  FeedPage,
  Group,
  JobStatus,
  Message,
  SavedSearch,
  SchedulerState,
  Sender,
  Watchlist,
} from "./types";

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const data = await r.json().catch(() => null);
  if (!r.ok) {
    const msg = (data && (data.error ?? data.detail)) ?? `request failed (${r.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data as T;
}

const post = <T>(url: string, body?: unknown): Promise<T> =>
  req<T>(url, { method: "POST", body: JSON.stringify(body ?? {}) });

const patch = <T>(url: string, body?: unknown): Promise<T> =>
  req<T>(url, { method: "PATCH", body: JSON.stringify(body ?? {}) });

/** Fetch a file endpoint and trigger a browser download of the response. */
async function download(url: string, init?: RequestInit): Promise<string> {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) {
    const data = await r.json().catch(() => null);
    const msg = (data && (data.error ?? data.detail)) ?? `export failed (${r.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  const blob = await r.blob();
  const name = (r.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/)?.[1])
    ?? "telegram-query-export.txt";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 30_000);
  return name;
}

export const api = {
  // general
  appState: () => req<AppState>("/api/app/state"),

  // auth
  authStatus: () => req<AuthState>("/api/auth/status"),
  authStart: (phone: string) => post<{ stage: string; error?: string; authenticated?: boolean; user?: string }>("/api/auth/start", { phone }),
  authCode: (code: string) => post<{ stage: string; error?: string; authenticated?: boolean; user?: string }>("/api/auth/code", { code }),
  authPassword: (password: string) => post<{ stage: string; error?: string; authenticated?: boolean; user?: string }>("/api/auth/password", { password }),
  authLogout: () => post<{ logged_out: boolean; error?: string }>("/api/auth/logout"),

  // archive
  groups: () => req<Group[]>("/api/groups"),
  senders: (groups: number[]) =>
    req<Sender[]>(`/api/senders?groups=${groups.join(",")}`),
  messages: (p: {
    groups: number[]; sender?: string; from?: string; to?: string;
    media?: string; cursor?: string; limit?: number; sort?: string;
    bookmarked?: boolean;
  }): Promise<FeedPage> => {
    const q = new URLSearchParams();
    if (p.groups.length) q.set("groups", p.groups.join(","));
    if (p.sender) q.set("sender", p.sender);
    if (p.from) q.set("from_", p.from);
    if (p.to) q.set("to", p.to);
    if (p.media) q.set("media", p.media);
    if (p.cursor) q.set("cursor", p.cursor);
    if (p.bookmarked) q.set("bookmarked", "true");
    q.set("limit", String(p.limit ?? 50));
    q.set("sort", p.sort ?? "desc");
    return req<FeedPage>(`/api/messages?${q}`);
  },
  message: (chatId: number, msgId: number) =>
    req<Message>(`/api/message/${chatId}/${msgId}`),
  search: (p: {
    q: string; groups: number[]; sender?: string; from?: string; to?: string;
    limit?: number; bookmarked?: boolean;
  }): Promise<Message[]> => {
    const q = new URLSearchParams({ q: p.q });
    if (p.groups.length) q.set("groups", p.groups.join(","));
    if (p.sender) q.set("sender", p.sender);
    if (p.from) q.set("from_", p.from);
    if (p.to) q.set("to", p.to);
    if (p.bookmarked) q.set("bookmarked", "true");
    q.set("limit", String(p.limit ?? 200));
    return req<Message[]>(`/api/search?${q}`);
  },

  // ai
  ask: (question: string, scope?: AskScope) =>
    post<AskResult>("/api/ask", { question, scope: scope ?? null }),
  aiUsage: () => req<AiUsage>("/api/ai/usage"),

  // bookmarks + notes (v0.4)
  bookmarks: (p?: { q?: string; groups?: number[] }) => {
    const q = new URLSearchParams();
    if (p?.q) q.set("q", p.q);
    if (p?.groups?.length) q.set("groups", p.groups.join(","));
    return req<BookmarkRow[]>(`/api/bookmarks${q.size ? `?${q}` : ""}`);
  },
  bookmarkSet: (chatId: number, msgId: number, note?: string) =>
    post<{ ok: boolean }>("/api/bookmarks",
      { chat_id: chatId, msg_id: msgId, note: note ?? "" }),
  bookmarkDelete: (chatId: number, msgId: number) =>
    req<{ ok: boolean }>(`/api/bookmarks/${chatId}/${msgId}`, { method: "DELETE" }),

  // saved searches (v0.4)
  savedList: () => req<SavedSearch[]>("/api/saved-searches"),
  savedCreate: (s: Omit<SavedSearch, "id" | "created_at" | "last_used_at">) =>
    post<SavedSearch>("/api/saved-searches", s),
  savedUpdate: (id: number, s: Omit<SavedSearch, "id" | "created_at" | "last_used_at">) =>
    patch<SavedSearch>(`/api/saved-searches/${id}`, s),
  savedDelete: (id: number) =>
    req<{ ok: boolean }>(`/api/saved-searches/${id}`, { method: "DELETE" }),
  savedDuplicate: (id: number) =>
    post<SavedSearch>(`/api/saved-searches/${id}/duplicate`),
  savedRun: (id: number) => post<SavedSearch>(`/api/saved-searches/${id}/run`),

  // scheduler (v0.4)
  schedulerState: () => req<SchedulerState>("/api/scheduler"),
  schedulerConfig: (p: { enabled?: boolean; interval_min?: number }) =>
    post<SchedulerState>("/api/scheduler", p),
  reindex: () => post<{ started: boolean }>("/api/reindex"),

  // exports (v0.4)
  exportBookmarks: (format: "md" | "json") =>
    download(`/api/export/bookmarks?format=${format}`),
  exportSaved: () => download("/api/export/saved-searches"),
  exportAiAnswer: (p: {
    question: string; answer: string;
    sources: { chat_id: number; msg_id: number }[];
    provider_host?: string; model?: string;
  }) => download("/api/export/ai-answer", {
    method: "POST", body: JSON.stringify(p),
  }),

  // deals (v0.5)
  deals: (p?: {
    status?: string; category?: string; vendor?: string; group?: string;
    q?: string; from?: string; to?: string; sort?: string;
  }) => {
    const q = new URLSearchParams();
    if (p?.status) q.set("status", p.status);
    if (p?.category) q.set("category", p.category);
    if (p?.vendor) q.set("vendor", p.vendor);
    if (p?.group) q.set("group", p.group);
    if (p?.q) q.set("q", p.q);
    if (p?.from) q.set("from_", p.from);
    if (p?.to) q.set("to", p.to);
    if (p?.sort) q.set("sort", p.sort);
    return req<Deal[]>(`/api/deals${q.size ? `?${q}` : ""}`);
  },
  dealPatch: (id: number, p: Record<string, unknown>) =>
    patch<Deal>(`/api/deals/${id}`, p),
  dealDelete: (id: number) =>
    req<{ ok: boolean }>(`/api/deals/${id}`, { method: "DELETE" }),
  dealAdd: (p: Record<string, unknown>) => post<Deal>("/api/deals", p),
  dealsExtract: (p: { chat_ids: number[]; date_from?: string | null; date_to?: string | null }) =>
    post<{ started: boolean }>("/api/deals/extract", p),
  dealsSettings: () => req<DealsSettings>("/api/deals/settings"),
  dealsAuto: (enabled: boolean) =>
    post<{ auto: boolean }>("/api/deals/auto", { enabled }),
  exportDeals: (format: "md" | "json") =>
    download(`/api/export/deals?format=${format}`),

  // research briefs (v0.5)
  briefs: () => req<Brief[]>("/api/briefs"),
  briefCreate: (p: {
    question: string; chat_ids: number[];
    date_from?: string | null; date_to?: string | null;
  }) => post<{ id: number; queued: boolean }>("/api/briefs", p),
  briefGet: (id: number) => req<Brief>(`/api/briefs/${id}`),
  briefPatch: (id: number, p: Record<string, unknown>) =>
    patch<Brief>(`/api/briefs/${id}`, p),
  briefRegenerate: (id: number) =>
    post<{ queued: boolean }>(`/api/briefs/${id}/regenerate`),
  briefDelete: (id: number) =>
    req<{ ok: boolean }>(`/api/briefs/${id}`, { method: "DELETE" }),
  briefVersions: (id: number) =>
    req<{ version: number; created_at: string; model: string }[]>(
      `/api/briefs/${id}/versions`),
  exportBrief: (id: number, format: "md" | "json") =>
    download(`/api/export/briefs/${id}?format=${format}`),

  // watchlists + alerts (v0.6)
  watchlists: () => req<Watchlist[]>("/api/watchlists"),
  watchCreate: (p: {
    name: string; terms: string[]; exclude_terms: string[];
    chat_ids: number[]; enabled: boolean;
  }) => post<Watchlist>("/api/watchlists", p),
  watchUpdate: (id: number, p: {
    name: string; terms: string[]; exclude_terms: string[];
    chat_ids: number[]; enabled: boolean;
  }) => patch<Watchlist>(`/api/watchlists/${id}`, p),
  watchDelete: (id: number) =>
    req<{ ok: boolean }>(`/api/watchlists/${id}`, { method: "DELETE" }),
  watchCheck: (backfillDays = 0) =>
    post<{ matches: number; unread: number }>("/api/watchlists/check",
      { backfill_days: backfillDays }),
  alerts: (p?: { state?: string; watchlist?: number }) => {
    const q = new URLSearchParams();
    if (p?.state) q.set("state", p.state);
    if (p?.watchlist) q.set("watchlist", String(p.watchlist));
    return req<Alert[]>(`/api/alerts${q.size ? `?${q}` : ""}`);
  },
  alertAction: (id: number, action: "read" | "unread" | "archive" | "unarchive") =>
    post<{ ok: boolean; unread: number }>(`/api/alerts/${id}`, { action }),
  alertDelete: (id: number) =>
    req<{ ok: boolean }>(`/api/alerts/${id}`, { method: "DELETE" }),
  alertsUnread: () => req<{ unread: number }>("/api/alerts/unread"),

  // digests (v0.6)
  digestSchedules: () => req<DigestSchedule[]>("/api/digests/schedules"),
  digestScheduleCreate: (p: {
    frequency: string; chat_ids: number[]; hour: number;
    language: string; enabled: boolean;
  }) => post<DigestSchedule>("/api/digests/schedules", p),
  digestScheduleDelete: (id: number) =>
    req<{ ok: boolean }>(`/api/digests/schedules/${id}`, { method: "DELETE" }),
  digests: () => req<Digest[]>("/api/digests"),
  digestGet: (id: number) => req<Digest>(`/api/digests/${id}`),
  digestDelete: (id: number) =>
    req<{ ok: boolean }>(`/api/digests/${id}`, { method: "DELETE" }),
  digestGenerate: (p: {
    chat_ids: number[]; frequency: string; language: string;
  }) => post<{ started: boolean }>("/api/digests/generate", p),

  // faqs (v0.6)
  faqs: (p?: { status?: string }) => {
    const q = new URLSearchParams();
    if (p?.status) q.set("status", p.status);
    return req<Faq[]>(`/api/faqs${q.size ? `?${q}` : ""}`);
  },
  faqPatch: (id: number, p: Record<string, unknown>) =>
    patch<Faq>(`/api/faqs/${id}`, p),
  faqDelete: (id: number) =>
    req<{ ok: boolean }>(`/api/faqs/${id}`, { method: "DELETE" }),
  faqDiscover: (p: { chat_ids: number[]; days: number }) =>
    post<{ started: boolean }>("/api/faqs/discover", p),

  // groups management
  dialogsGet: () => req<{ ready: boolean; dialogs?: Dialog[] }>("/api/dialogs"),
  dialogsStart: () => post<{ started: boolean; reason: string | null }>("/api/dialogs"),

  // setup wizard (credential values are write-only; never read back)
  setupTelegram: (apiId: string, apiHash: string) =>
    post<{ telegram_configured: boolean; error?: string }>(
      "/api/setup/telegram", { api_id: apiId, api_hash: apiHash }),
  setupAi: (p: { base_url?: string; api_key: string; model?: string }) =>
    post<{ ai_configured: boolean; error?: string }>("/api/setup/ai", p),
  testAi: (p: { base_url?: string; api_key: string; model?: string }) =>
    post<{ ok: boolean; error?: string; model?: string; reply?: string }>(
      "/api/setup/ai/test", p),

  track: (chatIds: number[]) =>
    post<{ started: boolean; chat_ids?: number[]; reason?: string; queued_behind?: string[] }>("/api/groups/track", { chat_ids: chatIds }),
  untrack: (chatIds: number[], deleteMessages = false) =>
    post<{ ok: boolean; deleted_messages?: boolean }>("/api/groups/untrack",
      { chat_ids: chatIds, delete_messages: deleteMessages }),

  // jobs
  sync: () => post<{ started: boolean; reason?: string; queued_behind?: string[] }>("/api/sync"),
  jobStatus: () => req<JobStatus>("/api/job/status"),
  jobStop: (clearQueue = false) =>
    post<{ stopping: boolean; cleared: string[] }>("/api/job/stop", { clear_queue: clearQueue }),
};

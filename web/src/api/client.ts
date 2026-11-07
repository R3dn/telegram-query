/** Thin fetch wrapper: JSON, error extraction, no secrets ever leave here. */
import type {
  AppState,
  AskResult,
  AuthState,
  Dialog,
  FeedPage,
  Group,
  JobStatus,
  Message,
  Sender,
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
  }): Promise<FeedPage> => {
    const q = new URLSearchParams();
    if (p.groups.length) q.set("groups", p.groups.join(","));
    if (p.sender) q.set("sender", p.sender);
    if (p.from) q.set("from_", p.from);
    if (p.to) q.set("to", p.to);
    if (p.media) q.set("media", p.media);
    if (p.cursor) q.set("cursor", p.cursor);
    q.set("limit", String(p.limit ?? 50));
    q.set("sort", p.sort ?? "desc");
    return req<FeedPage>(`/api/messages?${q}`);
  },
  message: (chatId: number, msgId: number) =>
    req<Message>(`/api/message/${chatId}/${msgId}`),
  search: (p: {
    q: string; groups: number[]; sender?: string; from?: string; to?: string;
    limit?: number;
  }): Promise<Message[]> => {
    const q = new URLSearchParams({ q: p.q });
    if (p.groups.length) q.set("groups", p.groups.join(","));
    if (p.sender) q.set("sender", p.sender);
    if (p.from) q.set("from_", p.from);
    if (p.to) q.set("to", p.to);
    q.set("limit", String(p.limit ?? 200));
    return req<Message[]>(`/api/search?${q}`);
  },

  // ai
  ask: (question: string) => post<AskResult>("/api/ask", { question }),

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

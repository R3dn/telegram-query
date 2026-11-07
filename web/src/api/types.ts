/** Shared API types (mirror of the FastAPI response shapes). */

export interface Message {
  chat_id: number;
  msg_id: number;
  date: string;
  sender_id?: number | null;
  sender_name: string | null;
  text: string;
  has_media: number;
  edited: number;
  chat_title: string;
  /** v0.4 */
  bookmarked?: number;        // 1 when starred
  bookmark_note?: string | null;
  tg_link?: string | null;    // open-in-Telegram link, null when none exists
}

export interface SavedSearch {
  id: number;
  name: string;
  q: string;
  chat_ids: number[];
  sender: string;
  media: string;
  date_from: string;
  date_to: string;
  sort: string;
  created_at: string;
  last_used_at: string | null;
}

export interface BookmarkRow extends Message {
  note: string;
  bookmarked_at: string;
  note_updated_at: string;
}

export interface SchedulerState {
  enabled: boolean;
  interval_min: number;
  next_due: string | null;
  last_success: string | null;
}

export interface AskScope {
  chat_ids: number[];
  date_from: string | null;
  date_to: string | null;
}

export interface Group {
  chat_id: number;
  title: string;
  kind: string;
  username: string | null;
  last_synced: string | null;
  message_count: number;
  last_message: string | null;
}

export interface Sender {
  sender_name: string;
  count: number;
}

export interface Dialog {
  chat_id: number;
  title: string;
  username: string | null;
  kind: string;
  tracked?: boolean;
}

export interface FeedPage {
  messages: Message[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface JobStatus {
  running: boolean;
  name: string;
  log: string;
  queued: string[];
  last_done: { name: string; ok: boolean; finished_at: number } | null;
}

export interface AppState {
  version: string;
  telegram_configured: boolean;
  authenticated: boolean | null; // null = still checking
  auth_user: string | null;
  tracked_groups: number;
  messages: number;
  pending_backfills: number;
  last_message: string | null;
  ai_configured: boolean;
  ai_provider_host: string;
  ai_model: string;
}

export interface AskResult {
  answer: string | null;
  error?: string;
  sources: Message[];
  attempts: number;
  keywords_tried: string[][];
  fallback?: string | null;
  provider_host?: string;
  provider_model?: string;
  scope?: AskScope;
}

export interface AuthState {
  authenticated: boolean | null;
  user: string | null;
}

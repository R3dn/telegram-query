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

export interface DealSource {
  chat_id: number;
  msg_id: number;
  text: string | null;
  date: string | null;
  sender_name: string | null;
  chat_title: string | null;
  tg_link: string | null;
  missing: boolean;
}

export interface Deal {
  id: number;
  title: string;
  description: string;
  category: string | null;
  vendor: string | null;
  discount_pct: number | null;
  price: number | null;
  currency: string | null;
  promo_code: string | null;
  eligibility: string | null;
  geo: string | null;
  valid_from: string | null;
  expires: string | null;
  status: string;
  user_status: string | null;   // confirmed | dismissed | null
  confidence: number | null;
  derived_status: string;
  confidence_label: string;
  human_added: boolean;
  last_seen: string;
  sources: DealSource[];
}

export interface DealsSettings {
  auto: boolean;
  categories: string[];
  vendors: string[];
  watermark: Record<string, number>;
}

export interface BriefCitation {
  idx: number;
  chat_id: number;
  msg_id: number;
  excerpt: string;
  text: string;
  date: string;
  sender_name: string | null;
  chat_title: string;
  tg_link: string | null;
}

export interface Brief {
  id: number;
  question: string;
  chat_ids: number[];
  date_from: string | null;
  date_to: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
  latest: {
    version: number;
    created_at: string;
    model: string;
    prompt_version: string;
    answer_md: string;
    citations: BriefCitation[];
  } | null;
  stale_count: number;
}

export interface Watchlist {
  id: number;
  name: string;
  terms: string[];
  exclude_terms: string[];
  chat_ids: number[];
  enabled: boolean;
  created_at: string;
  last_match_at: string | null;
  unread: number;
}

export interface Alert {
  id: number;
  watchlist_id: number;
  watchlist_name: string;
  chat_id: number;
  msg_id: number;
  matched_term: string;
  created_at: string;
  read: number;
  archived: number;
  text: string;
  date: string;
  sender_name: string | null;
  chat_title: string;
  tg_link: string | null;
}

export interface DigestSchedule {
  id: number;
  frequency: "daily" | "weekly";
  chat_ids: number[];
  hour: number;
  weekday: number;
  language: string;
  enabled: boolean;
  created_at: string;
  last_run: string | null;
}

export interface DigestCitation {
  idx: number;
  chat_id: number;
  msg_id: number;
  excerpt: string;
  text: string | null;
  date: string | null;
  chat_title: string | null;
  tg_link: string | null;
  missing: boolean;
}

export interface Digest {
  id: number;
  schedule_id: number | null;
  period_start: string;
  period_end: string;
  content_md: string;
  prompt_version: string;
  model: string;
  created_at: string;
  citations?: DigestCitation[];
}

export interface FaqSource {
  chat_id: number;
  msg_id: number;
  date: string;
  text?: string | null;
  chat_title?: string | null;
  tg_link: string | null;
}

export interface Faq {
  id: number;
  question: string;
  answer_md: string | null;
  status: "candidate" | "approved" | "rejected" | "needs_review" | "outdated";
  frequency: number;
  first_seen: string;
  last_seen: string;
  updated_at: string;
  source_questions: FaqSource[];
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

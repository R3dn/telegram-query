/** localStorage-backed histories: recent searches and AI conversations. */

export interface SearchHistoryItem {
  q: string;
  at: number;
}

const SEARCH_KEY = "tgq-search-history";
const CHAT_KEY = "tgq-ai-chat";
const THEME_KEY = "tgq-theme";

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full/blocked - histories are non-essential */
  }
}

// ---------- search history ----------

export function getSearchHistory(): SearchHistoryItem[] {
  return read<SearchHistoryItem[]>(SEARCH_KEY, []);
}

export function pushSearchHistory(q: string): SearchHistoryItem[] {
  const qTrim = q.trim();
  if (!qTrim) return getSearchHistory();
  const next = [
    { q: qTrim, at: Date.now() },
    ...getSearchHistory().filter((h) => h.q !== qTrim),
  ].slice(0, 8);
  write(SEARCH_KEY, next);
  return next;
}

export function clearSearchHistory(): SearchHistoryItem[] {
  localStorage.removeItem(SEARCH_KEY);
  return [];
}

// ---------- AI chat ----------

export interface ChatTurn {
  question: string;
  answer: string | null;
  error?: string;
  sources: { chat_id: number; msg_id: number; title: string; date: string; sender: string; text: string }[];
  keywords: string[];
  fallback?: string | null;
  at: number;
}

export function getChat(): ChatTurn[] {
  return read<ChatTurn[]>(CHAT_KEY, []);
}

export function pushChat(turn: Omit<ChatTurn, "at">): ChatTurn[] {
  const next = [...getChat(), { ...turn, at: Date.now() }].slice(-50);
  write(CHAT_KEY, next);
  return next;
}

export function clearChat(): ChatTurn[] {
  localStorage.removeItem(CHAT_KEY);
  return [];
}

// ---------- theme ----------

export function getTheme(): "dark" | "light" {
  const t = localStorage.getItem(THEME_KEY);
  return t === "light" ? "light" : "dark";
}

export function setTheme(theme: "dark" | "light"): void {
  localStorage.setItem(THEME_KEY, theme);
  document.documentElement.classList.toggle("light", theme === "light");
}

// ---------- AI scope (v0.4) ----------

/** Persisted AI-scope date preset ("all" | "7d" | "30d"), per user choice. */
const AI_SCOPE_KEY = "tgq-ai-scope-days";

export function getAiScopeDays(): "all" | "7d" | "30d" {
  const v = localStorage.getItem(AI_SCOPE_KEY);
  return v === "7d" || v === "30d" ? v : "all";
}

export function setAiScopeDays(days: "all" | "7d" | "30d"): void {
  localStorage.setItem(AI_SCOPE_KEY, days);
}

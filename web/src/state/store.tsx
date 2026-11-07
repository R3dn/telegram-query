/** Global application state: theme, toasts, app state, groups, filters,
 *  feed loading, job polling, and UI panel/modal switches. */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import type {
  AppState, Group, JobStatus, Message, SavedSearch, Sender,
} from "../api/types";
import {
  getSearchHistory,
  pushSearchHistory,
  setTheme as applyTheme,
  getTheme,
  type SearchHistoryItem,
} from "../utils/history";
import { jobLabel } from "../utils/format";

export type FeedMode = "browse" | "search" | "bookmarks";
export type RightTab = "ai" | "details";
export type DateChip = "all" | "today" | "7d" | "30d" | "custom";

export interface Filters {
  from: string;
  to: string;
  sender: string;
  media: string; // '' | '0' | '1'
  sort: string; // 'desc' | 'asc'
  starred: boolean; // only bookmarked messages (v0.4)
}

const DEFAULT_FILTERS: Filters = {
  from: "", to: "", sender: "", media: "", sort: "desc", starred: false,
};

interface Store {
  // theme
  theme: "dark" | "light";
  toggleTheme: () => void;

  // toasts
  toast: (text: string, type?: "info" | "good" | "err", ms?: number) => void;
  toasts: { id: number; text: string; type: string; out?: boolean }[];

  // app state
  appState: AppState | null;
  refreshAppState: () => Promise<void>;

  // groups + selection
  groups: Group[];
  selection: Set<number>;
  toggleGroup: (id: number) => void;
  clearSelection: () => void;
  refreshGroups: () => Promise<void>;
  senders: Sender[];

  // feed
  mode: FeedMode;
  setMode: (m: FeedMode) => void;
  q: string;
  runSearch: (query: string) => void;
  feed: Message[];
  hasMore: boolean;
  loading: boolean;
  loadFeed: (reset?: boolean) => Promise<void>;
  filters: Filters;
  setFilters: (f: Partial<Filters>) => void;
  dateChip: DateChip;
  setDateChip: (c: DateChip) => void;
  searchHistory: SearchHistoryItem[];
  pushSearch: (q: string) => void;

  // saved searches (v0.4)
  savedSearches: SavedSearch[];
  refreshSaved: () => Promise<void>;
  applySaved: (s: SavedSearch) => void;

  // jobs
  jobs: JobStatus | null;
  refreshJobs: () => Promise<void>;

  // UI
  rightTab: RightTab;
  setRightTab: (t: RightTab) => void;
  selected: Message | null;
  select: (m: Message | null) => void;
  modal: null | "manage" | "jobs" | "settings";
  setModal: (m: null | "manage" | "jobs" | "settings") => void;
  wizardOpen: boolean;
  setWizardOpen: (b: boolean) => void;
}

const Ctx = createContext<Store | null>(null);

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useStore outside provider");
  return s;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  // ---------- theme ----------
  const [theme, setThemeState] = useState<"dark" | "light">(getTheme);
  const toggleTheme = useCallback(() => {
    setThemeState((t) => {
      const next = t === "dark" ? "light" : "dark";
      applyTheme(next);
      return next;
    });
  }, []);

  // ---------- toasts ----------
  interface ToastItem { id: number; text: string; type: string; out?: boolean }
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastId = useRef(1);
  const toast = useCallback((text: string, type = "info", ms = 3500) => {
    const id = toastId.current++;
    setToasts((ts) => [...ts, { id, text, type }]);
    setTimeout(() => {
      setToasts((ts) => ts.map((t) => (t.id === id ? { ...t, out: true } : t)));
      setTimeout(() => setToasts((ts) => ts.filter((t) => t.id !== id)), 320);
    }, ms);
  }, []);

  // ---------- app state ----------
  const [appState, setAppState] = useState<AppState | null>(null);
  const refreshAppState = useCallback(async () => {
    try {
      setAppState(await api.appState());
    } catch {
      /* server restarting */
    }
  }, []);

  // ---------- groups + selection ----------
  const [groups, setGroups] = useState<Group[]>([]);
  const [selection, setSelection] = useState<Set<number>>(new Set());
  const [senders, setSenders] = useState<Sender[]>([]);

  const refreshGroups = useCallback(async () => {
    try {
      setGroups(await api.groups());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await api.senders([...selection]);
        if (!cancelled) setSenders(list);
      } catch {
        /* ignore */
      }
    })();
    return () => { cancelled = true; };
  }, [selection, groups]);

  const toggleGroup = useCallback((id: number) => {
    setSelection((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);
  const clearSelection = useCallback(() => setSelection(new Set()), []);

  // ---------- filters / mode / search ----------
  const [mode, setModeState] = useState<FeedMode>("browse");
  const [q, setQ] = useState("");
  const [filters, setFiltersState] = useState<Filters>(DEFAULT_FILTERS);
  const [dateChip, setDateChipState] = useState<DateChip>("all");
  const [searchHistory, setSearchHistory] = useState<SearchHistoryItem[]>(getSearchHistory);

  const setFilters = useCallback((f: Partial<Filters>) => {
    setFiltersState((prev) => ({ ...prev, ...f }));
  }, []);

  const setDateChip = useCallback((c: DateChip) => {
    setDateChipState(c);
    if (c === "all") setFilters({ from: "", to: "" });
    else if (c === "custom") return; // keep current values
    else {
      const to = new Date().toISOString().slice(0, 10);
      const from = c === "today" ? to : new Date(Date.now() - (c === "7d" ? 6 : 29) * 864e5).toISOString().slice(0, 10);
      setFilters({ from, to });
    }
  }, [setFilters]);

  // ---------- feed ----------
  const [feed, setFeed] = useState<Message[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const cursorRef = useRef<string | null>(null);
  const loadSeq = useRef(0);

  const loadFeed = useCallback(
    async (reset = true) => {
      const seq = ++loadSeq.current;
      setLoading(true);
      if (reset) {
        cursorRef.current = null;
        setFeed([]);
        setHasMore(false);
      }
      try {
        if (mode === "search") {
          if (!q.trim()) {
            setFeed([]);
            setHasMore(false);
            return;
          }
          let rows = await api.search({
            q, groups: [...selection], sender: filters.sender,
            from: filters.from, to: filters.to,
            bookmarked: filters.starred || undefined,
          });
          rows = rows.slice().sort((a, b) => (filters.sort === "asc" ? (a.date < b.date ? -1 : 1) : a.date > b.date ? -1 : 1));
          if (seq !== loadSeq.current) return;
          setFeed(rows);
          setHasMore(false);
        } else {
          const page = await api.messages({
            groups: [...selection],
            sender: filters.sender,
            from: filters.from,
            to: filters.to,
            media: filters.media,
            cursor: reset ? undefined : cursorRef.current ?? undefined,
            limit: 50,
            sort: filters.sort,
            bookmarked: filters.starred || undefined,
          });
          if (seq !== loadSeq.current) return;
          setFeed((f) => (reset ? page.messages : [...f, ...page.messages]));
          cursorRef.current = page.next_cursor;
          setHasMore(page.has_more);
        }
      } catch (e) {
        toast(`Load failed: ${(e as Error).message}`, "err");
      } finally {
        if (seq === loadSeq.current) setLoading(false);
      }
    },
    [mode, q, selection, filters, toast],
  );

  // reload whenever the query source changes
  useEffect(() => { void loadFeed(true); }, [mode, q, selection, filters]); // eslint-disable-line react-hooks/exhaustive-deps

  const setMode = useCallback((m: FeedMode) => {
    setModeState(m);
    if (m === "browse") setQ("");
  }, []);

  const pushSearch = useCallback((query: string) => {
    setSearchHistory(pushSearchHistory(query));
  }, []);

  // ---------- saved searches (v0.4) ----------
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);

  const refreshSaved = useCallback(async () => {
    try {
      setSavedSearches(await api.savedList());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void refreshSaved();
  }, [refreshSaved]);

  const applySaved = useCallback((s: SavedSearch) => {
    setSelection(new Set(s.chat_ids));
    setFiltersState((prev) => ({
      ...prev,
      sender: s.sender,
      media: s.media,
      sort: s.sort,
      from: s.date_from,
      to: s.date_to,
      starred: false,
    }));
    setDateChipState(s.date_from || s.date_to ? "custom" : "all");
    if (s.q.trim()) {
      setQ(s.q);
      setModeState("search");
      setSearchHistory(pushSearchHistory(s.q));
    } else {
      setQ("");
      setModeState("browse");
    }
    void (async () => {
      try {
        await api.savedRun(s.id);
        await refreshSaved();
      } catch {
        /* non-essential */
      }
    })();
  }, [refreshSaved]);

  const runSearch = useCallback((query: string) => {
    const queryTrim = query.trim();
    if (!queryTrim) {
      setMode("browse");
      return;
    }
    setQ(queryTrim);
    setModeState("search");
    setSearchHistory(pushSearchHistory(queryTrim));
  }, [setMode]);

  // ---------- jobs ----------
  const [jobs, setJobs] = useState<JobStatus | null>(null);
  const pollRef = useRef<number | null>(null);
  const lastDoneRef = useRef<number | null | undefined>(undefined);

  const refreshJobs = useCallback(async () => {
    try {
      setJobs(await api.jobStatus());
    } catch {
      /* ignore */
    }
  }, []);

  // poll while a job runs or the queue is non-empty; detect completions
  useEffect(() => {
    const running = jobs?.running || (jobs?.queued?.length ?? 0) > 0;
    if (running && pollRef.current === null) {
      const tick = () => {
        void (async () => {
          try {
            const s = await api.jobStatus();
            setJobs(s);
            const done = s.last_done;
            if (done && done.finished_at !== lastDoneRef.current) {
              const first = lastDoneRef.current === undefined;
              lastDoneRef.current = done.finished_at;
              if (!first) {
                toast(`${jobLabel(done.name)} ${done.ok ? "finished" : "failed"}`, done.ok ? "good" : "err");
                await Promise.all([refreshAppState(), refreshGroups()]);
                void loadFeed(true);
              }
            }
            const still = s.running || (s.queued?.length ?? 0) > 0;
            if (!still && pollRef.current !== null) {
              clearInterval(pollRef.current!);
              pollRef.current = null;
            }
          } catch {
            /* keep polling through transient errors */
          }
        })();
      };
      pollRef.current = window.setInterval(tick, 1200);
    }
  }, [jobs?.running, jobs?.queued?.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void refreshJobs();
    void refreshAppState();
    void refreshGroups();
  }, [refreshJobs, refreshAppState, refreshGroups]);

  // ---------- UI ----------
  const [rightTab, setRightTab] = useState<RightTab>("ai");
  const [selected, select] = useState<Message | null>(null);
  const [modal, setModal] = useState<Store["modal"]>(null);
  const [wizardOpen, setWizardOpen] = useState(false);

  const value = useMemo<Store>(
    () => ({
      theme, toggleTheme,
      toasts, toast,
      appState, refreshAppState,
      groups, selection, toggleGroup, clearSelection, refreshGroups, senders,
      mode, setMode, q, runSearch, feed, hasMore, loading, loadFeed,
      filters, setFilters, dateChip, setDateChip, searchHistory, pushSearch,
      savedSearches, refreshSaved, applySaved,
      jobs, refreshJobs,
      rightTab, setRightTab, selected, select, modal, setModal,
      wizardOpen, setWizardOpen,
    }),
    [theme, toggleTheme, toasts, toast, appState, refreshAppState, groups,
     selection, toggleGroup, clearSelection, refreshGroups, senders, mode,
     setMode, q, runSearch, feed, hasMore, loading, loadFeed, filters,
     setFilters, dateChip, setDateChip, searchHistory, pushSearch,
     savedSearches, refreshSaved, applySaved, jobs,
     refreshJobs, rightTab, selected, modal, wizardOpen],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

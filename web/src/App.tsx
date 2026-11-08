/** Telegram Query app shell: layout, wizard gating, panels, modals. */
import { useEffect, useRef, useState } from "react";
import { useStore } from "./state/store";
import { Sidebar } from "./components/Sidebar";
import { SearchBar } from "./components/SearchBar";
import { FilterBar } from "./components/FilterBar";
import { Feed } from "./components/Feed";
import { BookmarksView } from "./components/BookmarksView";
import { DealsView } from "./components/DealsView";
import { ResearchView } from "./components/ResearchView";
import { AlertsView, WatchView } from "./components/WatchView";
import { DigestsView } from "./components/DigestsView";
import { FaqView } from "./components/FaqView";
import { DiscoverView } from "./components/DiscoverView";
import { EntityView } from "./components/EntityView";
import { DetailsPanel } from "./components/DetailsPanel";
import { AiPanel } from "./components/AiPanel";
import { JobCenter } from "./components/JobCenter";
import { ManageGroups } from "./components/ManageGroups";
import { SettingsModal } from "./components/SettingsModal";
import { Onboarding } from "./components/Onboarding";
import { Toasts } from "./components/Toasts";

function shouldShowWizard(
  s: ReturnType<typeof useStore>["appState"],
): boolean {
  if (!s) return false;
  if (!s.telegram_configured) return true;
  if (s.authenticated === false) return true;
  return false;
}

export default function App() {
  const store = useStore();
  const { appState, wizardOpen, setWizardOpen, modal, setModal, mode } = store;

  const [wizardSeen, setWizardSeen] = useState(
    () => localStorage.getItem("tgq-wizard-seen") === "1",
  );

  // auto-open behavior: a signed-out user always needs the login wizard
  // (like a fresh install); the one-time flag only suppresses the
  // "no credentials" nags, and is cleared on sign-out.
  useEffect(() => {
    if (!appState) return;
    if (appState.authenticated === false) {
      localStorage.removeItem("tgq-wizard-seen");
      if (!wizardOpen) setWizardOpen(true);
      return;
    }
    const fresh = shouldShowWizard(appState) && !wizardSeen;
    if (fresh) {
      setWizardOpen(true);
      localStorage.setItem("tgq-wizard-seen", "1");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appState?.telegram_configured, appState?.authenticated]);

  const closeWizard = () => {
    setWizardOpen(false);
    setWizardSeen(true);
  };

  return (
    <>
      <div className="app">
        <Sidebar />
        <main className="center">
          {mode === "discover" ? (
            <DiscoverView />
          ) : mode === "entities" ? (
            <EntityView />
          ) : mode === "bookmarks" ? (
            <BookmarksView />
          ) : mode === "deals" ? (
            <DealsView />
          ) : mode === "research" ? (
            <ResearchView />
          ) : mode === "watchlists" ? (
            <WatchView />
          ) : mode === "alerts" ? (
            <AlertsView />
          ) : mode === "digests" ? (
            <DigestsView />
          ) : mode === "faqs" ? (
            <FaqView />
          ) : (
            <>
              <SearchBar />
              <FilterBar />
              <Feed />
            </>
          )}
        </main>
        <RightPanel />
      </div>

      <MobileNav />

      {wizardOpen && <Onboarding onClose={closeWizard} />}
      {modal === "manage" && <ManageGroups onClose={() => setModal(null)} />}
      {modal === "jobs" && <JobCenter onClose={() => setModal(null)} />}
      {modal === "settings" && <SettingsModal onClose={() => setModal(null)} />}
      <Toasts />
    </>
  );
}

function RightPanel() {
  const { rightTab, setRightTab } = useStore();
  const [width, setWidth] = useState(() =>
    parseInt(localStorage.getItem("tgq-right-w") ?? "360", 10),
  );
  const [hidden, setHidden] = useState(false);
  const dragging = useRef(false);

  const onPointerDown = (e: React.PointerEvent) => {
    dragging.current = true;
    (e.target as HTMLElement).classList.add("active");
    e.preventDefault();
  };

  useEffect(() => {
    const move = (e: PointerEvent) => {
      if (!dragging.current) return;
      const w = window.innerWidth - e.clientX;
      setWidth(Math.min(Math.max(w, 280), 560));
    };
    const up = () => {
      if (dragging.current) {
        dragging.current = false;
        localStorage.setItem("tgq-right-w", String(width));
        document.querySelectorAll(".resize-handle.active")
          .forEach((el) => el.classList.remove("active"));
      }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [width]);

  const narrow = window.matchMedia("(max-width: 1100px)").matches;

  return (
    <aside
      className={`right ${hidden && !narrow ? "hidden" : ""} ${narrow ? "" : ""}`}
      style={narrow ? undefined : { width, maxWidth: "50vw" }}
    >
      {!narrow && (
        <div
          className="resize-handle"
          onPointerDown={onPointerDown}
          title="Drag to resize"
        />
      )}
      <div className="right-tabs">
        <button className={`tab ${rightTab === "ai" ? "on" : ""}`} onClick={() => setRightTab("ai")}>✦ Ask AI</button>
        <button className={`tab ${rightTab === "details" ? "on" : ""}`} onClick={() => setRightTab("details")}>Details</button>
        <span style={{ flex: 1 }} />
        <button
          className="btn ghost sm"
          title={hidden ? "Show panel" : "Hide panel"}
          onClick={() => {
            if (narrow) document.body.classList.remove("tgq-right-open");
            else setHidden((h) => !h);
          }}
        >
          {narrow ? "✕" : hidden ? "«" : "»"}
        </button>
      </div>
      <div className="right-body">
        {rightTab === "ai" ? <AiPanel /> : <DetailsPanel />}
      </div>
    </aside>
  );
}

function MobileNav() {
  const { setMode, setRightTab, setModal, mode } = useStore();

  const open = (cls: "tgq-side-open" | "tgq-right-open") => {
    document.body.classList.remove("tgq-side-open", "tgq-right-open");
    document.body.classList.add(cls);
  };

  return (
    <>
      <div
        className="tgq-backdrop"
        onClick={() => document.body.classList.remove("tgq-side-open", "tgq-right-open")}
      />
      <nav className="bottom-nav">
        <button onClick={() => { setMode("discover"); document.body.classList.remove("tgq-side-open", "tgq-right-open"); }}
          className={mode === "discover" ? "on" : ""}>
          <span className="bic">📈</span> Discover
        </button>
        <button onClick={() => { setMode("browse"); document.body.classList.remove("tgq-side-open", "tgq-right-open"); }}
          className={mode === "browse" || mode === "search" ? "on" : ""}>
          <span className="bic">🔍</span> Browse
        </button>
        <button onClick={() => open("tgq-side-open")}>
          <span className="bic">👥</span> Groups
        </button>
        <button onClick={() => { setRightTab("ai"); open("tgq-right-open"); }}>
          <span className="bic">✦</span> Ask AI
        </button>
        <button onClick={() => setModal("jobs")}>
          <span className="bic">⇄</span> Jobs
        </button>
      </nav>
    </>
  );
}

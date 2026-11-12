/** Telegram Query app shell: layout, wizard gating, panels, modals. */
import { useEffect, useRef, useState } from "react";
import { useStore } from "./state/store";
import { useLang } from "./i18n";
import { Sidebar } from "./components/Sidebar";
import { SearchBar } from "./components/SearchBar";
import { FilterBar } from "./components/FilterBar";
import { Feed } from "./components/Feed";
import { BookmarksView } from "./components/BookmarksView";
import { DealsView } from "./components/DealsView";
import { DecisionsView } from "./components/DecisionsView";
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
import { Ic } from "./design/icons";

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
  const { appState, wizardOpen, setWizardOpen, modal, setModal, mode, rightOpen } = store;

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
      <div className={`app ${!rightOpen ? "hide-right" : ""}`}>
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
          ) : mode === "decisions" ? (
            <DecisionsView />
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
  const { rightTab, setRightTab, selected, rightOpen, setRightOpen } = useStore();
  const { t } = useLang();
  const [width, setWidth] = useState(() =>
    parseInt(localStorage.getItem("tgq-right-w") ?? "360", 10),
  );
  const dragging = useRef(false);
  // v1.0.2: react to window resizes. A once-per-render matchMedia check
  // went stale after resizing the desktop window across the 1100px
  // breakpoint (panel mode + mobile nav never re-evaluated).
  const [narrow, setNarrow] = useState(
    () => window.matchMedia("(max-width: 1100px)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1100px)");
    const upd = () => setNarrow(mq.matches);
    mq.addEventListener("change", upd);
    return () => mq.removeEventListener("change", upd);
  }, []);

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

  return (
    <aside
      className={`right ${!rightOpen && !narrow ? "hidden" : ""}`}
      style={narrow ? undefined : { width }}
    >
      {!narrow && (
        <div
          className="resize-handle"
          onPointerDown={onPointerDown}
          title={t("panel.dragResize")}
        />
      )}
      <div className="right-tabs">
        <div className="tab-pills">
          <button
            className={`tab ${rightTab === "ai" ? "on" : ""}`}
            onClick={() => setRightTab("ai")}
          >
            <Ic.Sparkles size={14} /> {t("panel.askAi")}
          </button>
          <button
            className={`tab ${rightTab === "details" ? "on" : ""}`}
            disabled={!selected}
            title={!selected ? t("panel.detailsHint") : undefined}
            onClick={() => setRightTab("details")}
          >
            {t("panel.details")}
          </button>
        </div>
        <button
          className="btn ghost sm icon"
          title={!rightOpen ? t("panel.show") : t("panel.hide")}
          onClick={() => {
            if (narrow) document.body.classList.remove("tgq-right-open");
            else setRightOpen(!rightOpen);
          }}
        >
          {narrow
            ? <Ic.Close size={14} />
            : !rightOpen
              ? <Ic.PanelRightOpen size={14} />
              : <Ic.PanelRightClose size={14} />}
        </button>
      </div>
      <div className="right-body">
        {rightTab === "ai" ? <AiPanel /> : <DetailsPanel />}
      </div>
    </aside>
  );
}

function MobileNav() {
  const { setMode, setRightTab, setRightOpen, setModal, mode } = useStore();
  const { t } = useLang();

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
          <span className="bic"><Ic.TrendingUp size={19} /></span> {t("nav.discover")}
        </button>
        <button onClick={() => { setMode("browse"); document.body.classList.remove("tgq-side-open", "tgq-right-open"); }}
          className={mode === "browse" || mode === "search" ? "on" : ""}>
          <span className="bic"><Ic.Search size={19} /></span> {t("nav.browseShort")}
        </button>
        <button onClick={() => open("tgq-side-open")}>
          <span className="bic"><Ic.Users size={19} /></span> {t("nav.groups")}
        </button>
        <button onClick={() => { setRightTab("ai"); setRightOpen(true); open("tgq-right-open"); }}>
          <span className="bic"><Ic.Sparkles size={19} /></span> {t("nav.askAi")}
        </button>
        <button onClick={() => setModal("jobs")}>
          <span className="bic"><Ic.RefreshCw size={19} /></span> {t("nav.jobs")}
        </button>
      </nav>
    </>
  );
}

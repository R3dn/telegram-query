import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { StoreProvider } from "./state/store";
import { LangProvider } from "./i18n";
import App from "./App";

// Self-hosted fonts (bundled by Vite; the app works fully offline).
import "@fontsource-variable/inter";
import "@fontsource-variable/noto-sans-arabic";

import "./design/base.css";
import "./design/app.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <LangProvider>
      <StoreProvider>
        <App />
      </StoreProvider>
    </LangProvider>
  </StrictMode>,
);

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";

import App from "./App";
import { queryClient } from "./queryClient";
import "./i18n";
import "./styles/global.css";
import { initTheme } from "./styles/themeBootstrap";

initTheme();

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root is missing from index.html");
}

// Persist TanStack Query cache (including auth status, runs list, etc.) into
// localStorage so the SPA does not flash the login screen on every reload.
// The backend remains the source of truth — cached entries are revalidated
// on mount, but the UI starts from the last known good state.
const persister = createSyncStoragePersister({
  storage: window.localStorage,
  key: "speca.web.queryCache",
  throttleTime: 1000,
});

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        // 24h: cached data older than this is dropped on next boot so we
        // do not surface a long-stale auth identity after a quota change.
        maxAge: 24 * 60 * 60 * 1000,
        buster: "v0",
      }}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </PersistQueryClientProvider>
  </React.StrictMode>,
);

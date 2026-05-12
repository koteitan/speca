// Application shell — header + main + lazy chat panel.
//
// Layout responsibilities:
//   - render the sticky <Header/>
//   - host the route <Outlet/> in the main column
//   - mount the ChatPanel slot on the right (lazy, with a Suspense
//     fallback) so Slice E can land without touching this file
//
// Auth gate:
//   - while the auth probe is in flight: render the shell skeleton so we
//     do not flash the login screen for a logged-in user
//   - resolved + not logged in → <Navigate to="/login" />
//   - resolved + logged in → render Outlet
//
// Chat-panel lazy import:
//   The dynamic import is wrapped in a `.catch` that resolves to an empty
//   component. If Slice E hasn't merged yet (or the chunk fails to load
//   in dev), the panel is empty rather than crashing the whole shell —
//   the catch fallback satisfies the `{ default: ComponentType }`
//   contract React.lazy expects.

import { Suspense, lazy, useState, type ComponentType } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useT } from "@/i18n/useT";

import { useAuthStatusSafe } from "../../features/auth/useAuthStatusSafe";
import Spinner from "../Spinner/Spinner";
import Header from "../Header/Header";
import styles from "./AppShell.module.css";

type ChatPanelComponent = ComponentType<Record<string, never>>;

// Slice E ships `features/chat/ChatPanel.tsx` later. To keep this slice
// independently buildable we wrap the dynamic import in `loadChatPanel`
// and use a `@vite-ignore` annotation so Vite does not try to resolve
// the literal path at build time. The `.catch` resolves to an empty
// component if the chunk fails to load at runtime (Slice E not yet
// merged), satisfying React.lazy's `{ default: ComponentType }` contract.
async function loadChatPanel(): Promise<{ default: ChatPanelComponent }> {
  try {
    const path = "/src/features/chat/ChatPanel.tsx";
    const mod = (await import(/* @vite-ignore */ path)) as {
      default: ChatPanelComponent;
    };
    return { default: mod.default };
  } catch {
    return { default: (() => null) as ChatPanelComponent };
  }
}

const ChatPanel = lazy<ChatPanelComponent>(loadChatPanel);

export function AppShell() {
  const t = useT();
  const auth = useAuthStatusSafe();
  const location = useLocation();
  const [chatOpen, setChatOpen] = useState(false);

  // Don't bounce to /login while the first probe is in flight — that
  // would briefly flash the login form for users who are actually
  // authenticated.
  if (auth.isPending) {
    return (
      <div className={styles.bootstrap}>
        <Spinner size="lg" label={t("common.checking_session")} />
      </div>
    );
  }

  // Resolved + unauthenticated → redirect. We pass the current location
  // in `state.from` so a future Slice can bounce back after login.
  if (!auth.loggedIn) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return (
    <div className={styles.shell} data-chat-open={chatOpen}>
      <Header
        onToggleChat={() => setChatOpen((prev) => !prev)}
        chatOpen={chatOpen}
      />
      <main className={styles.main}>
        <Outlet />
      </main>
      {chatOpen ? (
        <>
          <button
            type="button"
            className={styles.chatBackdrop}
            aria-label={t("header.close_chat")}
            onClick={() => setChatOpen(false)}
          />
          <aside className={styles.chat} aria-label={t("chat.panel.panel_aria")}>
            <Suspense fallback={<Spinner size="md" label={t("common.loading_chat")} />}>
              <ChatPanel />
            </Suspense>
          </aside>
        </>
      ) : null}
    </div>
  );
}

export default AppShell;

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
// Chat-panel lazy import: Slice E's ChatPanel ships with the app, so a
// plain static dynamic import is enough — Vite emits it as its own chunk
// and the Suspense fallback handles the load. The earlier @vite-ignore
// workaround was needed only while Slice E was in flight; it broke the
// production build because the runtime URL `/src/features/chat/...` does
// not exist after `vite build`.

import { Suspense, lazy, useCallback, useMemo, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useT } from "@/i18n/useT";
import { useChatUi } from "@/store/chatUiSlice";
import { useKeyboardShortcuts } from "@/lib/useKeyboardShortcuts";

import { useAuthStatusSafe } from "../../features/auth/useAuthStatusSafe";
import Spinner from "../Spinner/Spinner";
import Header from "../Header/Header";
import ShortcutsHelp from "../ShortcutsHelp/ShortcutsHelp";
import styles from "./AppShell.module.css";

const ChatPanel = lazy(() => import("../../features/chat/ChatPanel"));

export function AppShell() {
  const t = useT();
  const auth = useAuthStatusSafe();
  const location = useLocation();
  const chatOpen = useChatUi((s) => s.open);
  const setChatOpen = useChatUi((s) => s.setOpen);
  const toggleChat = useChatUi((s) => s.toggle);

  // Help-modal visibility lives in the shell so global shortcuts (`?` /
  // `Esc`) can open and close it without threading state through every
  // page. Closing the modal also clears the chat panel — Esc should be
  // the universal "get me out of whatever overlay is open" key.
  const [showHelp, setShowHelp] = useState(false);

  const handleOpenHelp = useCallback(() => setShowHelp(true), []);
  const handleCloseHelp = useCallback(() => setShowHelp(false), []);
  const handleCloseAll = useCallback(() => {
    setShowHelp(false);
    setChatOpen(false);
  }, [setChatOpen]);

  const shortcutHandlers = useMemo(
    () => ({
      onOpenHelp: handleOpenHelp,
      onCloseAll: handleCloseAll,
      onToggleChat: toggleChat,
    }),
    [handleOpenHelp, handleCloseAll, toggleChat],
  );

  useKeyboardShortcuts(shortcutHandlers);

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
      <Header onToggleChat={toggleChat} chatOpen={chatOpen} />
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
      <ShortcutsHelp open={showHelp} onClose={handleCloseHelp} />
    </div>
  );
}

export default AppShell;

// Top app bar.
//
// Layout (left → center → right):
//   - brand: "SPECA" + v0 badge
//   - nav:   Runs only in v0 (Findings is run-scoped, not a top-level)
//   - tools: chat toggle, identity, Settings gear
//
// The Settings link is intentionally rendered even before Slice D ships
// the route — clicking it will hit a 404 until the route is registered,
// which is acceptable for v0 and avoids a follow-up wiring slice.

import { NavLink } from "react-router-dom";

import { useAuthStatusSafe } from "../../features/auth/useAuthStatusSafe";
import styles from "./Header.module.css";

export interface HeaderProps {
  /** Toggle the ChatPanel mounted by <AppShell/>. */
  onToggleChat: () => void;
  /** Whether the chat panel is currently visible (drives aria-pressed). */
  chatOpen: boolean;
}

export function Header({ onToggleChat, chatOpen }: HeaderProps) {
  const auth = useAuthStatusSafe();

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <span className={styles.logo}>SPECA</span>
        <span className={styles.badge} aria-label="version v0">
          v0
        </span>
      </div>

      <nav className={styles.nav} aria-label="Primary">
        <NavLink
          to="/runs"
          className={({ isActive }) =>
            isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
          }
        >
          Runs
        </NavLink>
      </nav>

      <div className={styles.tools}>
        <button
          type="button"
          className={styles.iconButton}
          onClick={onToggleChat}
          aria-pressed={chatOpen}
          aria-label={chatOpen ? "Close chat panel" : "Open chat panel"}
          title={chatOpen ? "Close chat" : "Open chat"}
        >
          <span aria-hidden="true">Chat</span>
        </button>

        <span className={styles.identity}>
          {auth.identity ? (
            <>
              <span className={styles.identityLabel}>signed in as</span>{" "}
              <span className={styles.identityValue}>{auth.identity}</span>
            </>
          ) : auth.loggedIn ? (
            <span className={styles.identityLabel}>signed in</span>
          ) : (
            <span className={styles.identityLabel}>guest</span>
          )}
        </span>

        <NavLink
          to="/settings"
          className={({ isActive }) =>
            isActive ? `${styles.iconButton} ${styles.iconButtonActive}` : styles.iconButton
          }
          aria-label="Settings"
          title="Settings"
        >
          <span aria-hidden="true">Settings</span>
        </NavLink>
      </div>
    </header>
  );
}

export default Header;

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
import { useT } from "@/i18n/useT";
import { useChatApprovals } from "@/store/chatApprovalsSlice";
import LanguageToggle from "../LanguageToggle/LanguageToggle";
import styles from "./Header.module.css";

export interface HeaderProps {
  /** Toggle the ChatPanel mounted by <AppShell/>. */
  onToggleChat: () => void;
  /** Whether the chat panel is currently visible (drives aria-pressed). */
  chatOpen: boolean;
}

export function Header({ onToggleChat, chatOpen }: HeaderProps) {
  const auth = useAuthStatusSafe();
  const t = useT();
  // Subscribe to the *array length* (not a function) so React re-renders
  // when approvals come and go. Calling ``count()`` would only read the
  // value at render time without subscribing.
  const pendingCount = useChatApprovals((s) => s.pending.length);
  // Only nudge the user when the chat panel is closed; while it is open
  // the inline ApprovalCard is already visible and a redundant badge
  // would just add noise.
  const showBadge = pendingCount > 0 && !chatOpen;

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <span className={styles.logo}>{t("app.name")}</span>
        <span className={styles.badge} aria-label={t("header.version_badge_aria")}>
          v0
        </span>
      </div>

      <nav className={styles.nav} aria-label={t("header.nav_runs")}>
        <NavLink
          to="/runs"
          className={({ isActive }) =>
            isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
          }
        >
          {t("header.nav_runs")}
        </NavLink>
      </nav>

      <div className={styles.tools}>
        <button
          type="button"
          className={`${styles.iconButton} ${
            showBadge ? styles.iconButtonAlert : ""
          }`}
          onClick={onToggleChat}
          aria-pressed={chatOpen}
          aria-label={chatOpen ? t("header.close_chat") : t("header.open_chat")}
          title={chatOpen ? t("header.close_chat_title") : t("header.open_chat_title")}
          data-testid="chat-toggle"
        >
          <span aria-hidden="true">{t("header.chat_label")}</span>
          {showBadge && (
            <span
              className={styles.badgePending}
              aria-label={t(
                pendingCount === 1
                  ? "chat.approvals_pending"
                  : "chat.approvals_pending_other",
                { n: pendingCount },
              )}
              data-testid="approvals-pending-badge"
            >
              {pendingCount}
            </span>
          )}
        </button>

        <span className={styles.identity}>
          {auth.identity ? (
            <>
              <span className={styles.identityLabel}>{t("header.signed_in_as")}</span>{" "}
              <span className={styles.identityValue}>{auth.identity}</span>
            </>
          ) : auth.loggedIn ? (
            <span className={styles.identityLabel}>{t("header.signed_in")}</span>
          ) : (
            <span className={styles.identityLabel}>{t("header.guest")}</span>
          )}
        </span>

        {/* === language toggle === */}
        <LanguageToggle compact />

        <NavLink
          to="/settings"
          className={({ isActive }) =>
            isActive ? `${styles.iconButton} ${styles.iconButtonActive}` : styles.iconButton
          }
          aria-label={t("header.settings_label")}
          title={t("header.settings_label")}
        >
          <span aria-hidden="true">{t("header.settings_label")}</span>
        </NavLink>
      </div>
    </header>
  );
}

export default Header;

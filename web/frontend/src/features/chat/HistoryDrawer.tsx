// Collapsible drawer above the message log that lists past conversations
// and lets the user start a fresh one. Kept inside the chat panel rather
// than as a separate sidebar so the layout still fits at 360px width.

import { useT } from "@/i18n/useT";

import { useConversationList } from "./useConversationList";
import styles from "./HistoryDrawer.module.css";

export interface HistoryDrawerProps {
  /** ID of the conversation currently being viewed. */
  activeId: string;
  /** True when the drawer is expanded. */
  open: boolean;
  /** Switch the active conversation. */
  onSelect: (conversationId: string) => void;
  /** Start a fresh conversation (mints a new UUID upstream). */
  onNew: () => void;
}

function formatTimestamp(iso: string): string {
  // No need for a heavy date library; the row only needs a short
  // human-relative form. Use the browser's locale to keep it natural.
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function truncate(s: string | null, max = 60): string | null {
  if (!s) return null;
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

export function HistoryDrawer({
  activeId,
  open,
  onSelect,
  onNew,
}: HistoryDrawerProps) {
  const t = useT();
  const query = useConversationList();

  if (!open) return null;

  const items = query.data ?? [];

  return (
    <div className={styles.drawer} aria-label={t("chat.history.aria")}>
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.newButton}
          onClick={onNew}
          data-testid="chat-new-conversation"
        >
          {t("chat.history.new")}
        </button>
      </div>
      {query.isPending ? (
        <p className={styles.empty}>{t("common.loading")}</p>
      ) : query.isError ? (
        <p className={styles.empty}>{t("common.error")}</p>
      ) : items.length === 0 ? (
        <p className={styles.empty}>{t("chat.history.empty")}</p>
      ) : (
        <ul className={styles.list} role="list">
          {items.map((c) => {
            const isActive = c.conversation_id === activeId;
            return (
              <li key={c.conversation_id}>
                <button
                  type="button"
                  className={`${styles.row} ${isActive ? styles.rowActive : ""}`}
                  onClick={() => onSelect(c.conversation_id)}
                  aria-current={isActive ? "true" : undefined}
                  title={c.conversation_id}
                >
                  <span className={styles.title}>
                    {truncate(c.title) ?? t("chat.history.untitled")}
                  </span>
                  <span className={styles.timestamp}>
                    {formatTimestamp(c.last_message_at)}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default HistoryDrawer;

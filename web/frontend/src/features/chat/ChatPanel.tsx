import { useEffect, useMemo, useRef, useState } from "react";

import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";
import { newConversationId } from "./conversationId";
import { useChatStream } from "./useChatStream";
import styles from "./ChatPanel.module.css";

/**
 * Right-side chat panel (read-only mode in v0).
 *
 * Owns the conversation id (either supplied by the parent via props or
 * minted on first mount) and renders:
 *
 *   - a "Read-only mode (v0)" banner so the user knows side-effects are off
 *   - the scrolling message log (history + live streaming draft)
 *   - the composer
 *
 * Collapsibility lives in local state — see Slice F (AppShell) for the
 * layout-level integration. For Slice E we ship the panel standalone so
 * it can be smoke-tested without the surrounding shell.
 */

export interface ChatPanelProps {
  /**
   * Optional. When omitted, the panel mints a fresh UUID and uses it for
   * the lifetime of the component. Useful for stories / standalone use.
   */
  conversationId?: string;
  /** Whether the panel starts open. Defaults to ``true`` on desktop. */
  defaultOpen?: boolean;
}

export function ChatPanel({ conversationId, defaultOpen = true }: ChatPanelProps) {
  // Memoise so the id is stable across re-renders even if the caller
  // omits it. ``useState`` would also work but ``useMemo`` makes intent
  // clear: we want one id per *prop value*, not per render.
  const effectiveId = useMemo(
    () => conversationId ?? newConversationId(),
    [conversationId],
  );
  const [open, setOpen] = useState(defaultOpen);

  const { messages, streamingDraft, toolCalls, streaming, error, send } =
    useChatStream(effectiveId);

  // Auto-scroll to the latest message on every render. We use a ref +
  // imperative scroll rather than `scrollIntoView` so the page itself
  // does not scroll when the chat updates.
  const scrollRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streamingDraft, toolCalls]);

  if (!open) {
    return (
      <button
        type="button"
        className={styles.fab}
        aria-label="Open chat"
        onClick={() => setOpen(true)}
      >
        Chat
      </button>
    );
  }

  return (
    <aside
      className={styles.panel}
      aria-label="Chat with Claude"
      data-testid="chat-panel"
    >
      <header className={styles.header}>
        <span className={styles.title}>Chat</span>
        <span className={styles.badge} title="v0 — read-only tools only">
          Read-only mode (v0)
        </span>
        <button
          type="button"
          className={styles.collapseButton}
          aria-label="Collapse chat panel"
          onClick={() => setOpen(false)}
        >
          ×
        </button>
      </header>

      <div className={styles.scroll} ref={scrollRef}>
        {messages.length === 0 && !streamingDraft && (
          <p className={styles.empty}>
            Ask Claude about a run, a finding, or a property id.
          </p>
        )}
        {messages.map((m, idx) => (
          <MessageBubble
            key={`${m.timestamp}-${idx}`}
            message={m}
            toolCalls={toolCalls}
          />
        ))}
        {streamingDraft && (
          <MessageBubble
            key="streaming-draft"
            message={streamingDraft}
            toolCalls={toolCalls}
          />
        )}
        {error && (
          <div className={styles.error} role="alert">
            {error}
          </div>
        )}
      </div>

      <ChatInput disabled={streaming} onSubmit={(text) => send(text)} />
    </aside>
  );
}

export default ChatPanel;

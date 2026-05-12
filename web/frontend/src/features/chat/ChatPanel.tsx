import { useEffect, useRef, useState } from "react";

import { useT } from "@/i18n/useT";

import { ApprovalCard } from "./ApprovalCard";
import type { ApprovalCardToolName } from "./ApprovalCard";
import { ChatInput } from "./ChatInput";
import { HistoryDrawer } from "./HistoryDrawer";
import { MessageBubble } from "./MessageBubble";
import { newConversationId } from "./conversationId";
import { useChatStream } from "./useChatStream";
import styles from "./ChatPanel.module.css";
import type { ChatMessage } from "./types";

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
  const t = useT();
  // When the caller does not supply an id we own it via local state so
  // a "new chat" action can swap it without remounting the panel. The
  // initial mint is wrapped in a lazy initializer to avoid generating a
  // UUID per render.
  const [ownedId, setOwnedId] = useState<string>(
    () => conversationId ?? newConversationId(),
  );
  const effectiveId = conversationId ?? ownedId;
  const [open, setOpen] = useState(defaultOpen);
  const [historyOpen, setHistoryOpen] = useState(false);

  const {
    messages,
    streamingDraft,
    toolCalls,
    streaming,
    error,
    send,
    approve,
    cancelApproval,
  } = useChatStream(effectiveId);

  // Track per-card status so the buttons can flip to "Approving..." /
  // "Cancelling..." without waiting for the SSE round-trip. ``resolved``
  // is implicit: once ``tool_use_result`` arrives, ``useChatStream``
  // drops the system meta row and the entry here becomes orphaned but
  // harmless.
  const [cardStatus, setCardStatus] = useState<
    Record<string, "pending" | "approving" | "cancelling">
  >({});
  const [cardError, setCardError] = useState<Record<string, string>>({});

  const handleApprove = async (toolCallId: string) => {
    setCardStatus((prev) => ({ ...prev, [toolCallId]: "approving" }));
    setCardError((prev) => {
      const { [toolCallId]: _ignored, ...rest } = prev;
      return rest;
    });
    try {
      await approve(toolCallId);
    } catch (err) {
      setCardStatus((prev) => ({ ...prev, [toolCallId]: "pending" }));
      setCardError((prev) => ({
        ...prev,
        [toolCallId]: err instanceof Error ? err.message : String(err),
      }));
    }
  };

  const handleCancel = async (toolCallId: string) => {
    setCardStatus((prev) => ({ ...prev, [toolCallId]: "cancelling" }));
    setCardError((prev) => {
      const { [toolCallId]: _ignored, ...rest } = prev;
      return rest;
    });
    try {
      await cancelApproval(toolCallId);
    } catch (err) {
      setCardStatus((prev) => ({ ...prev, [toolCallId]: "pending" }));
      setCardError((prev) => ({
        ...prev,
        [toolCallId]: err instanceof Error ? err.message : String(err),
      }));
    }
  };

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
        aria-label={t("chat.panel.open_chat_aria")}
        onClick={() => setOpen(true)}
      >
        {t("chat.panel.fab_label")}
      </button>
    );
  }

  return (
    <aside
      className={styles.panel}
      aria-label={t("chat.panel.panel_aria")}
      data-testid="chat-panel"
    >
      <header className={styles.header}>
        <span className={styles.title}>{t("chat.panel.title")}</span>
        <span
          className={styles.badge}
          title={t("chat.panel.readonly_badge_title")}
        >
          {t("chat.panel.readonly_badge")}
        </span>
        <button
          type="button"
          className={styles.headerButton}
          aria-pressed={historyOpen}
          aria-label={t("chat.history.toggle_aria")}
          title={t("chat.history.toggle_aria")}
          onClick={() => setHistoryOpen((v) => !v)}
          data-testid="chat-history-toggle"
        >
          {t("chat.history.toggle_label")}
        </button>
        <button
          type="button"
          className={styles.collapseButton}
          aria-label={t("chat.panel.collapse_aria")}
          onClick={() => setOpen(false)}
        >
          ×
        </button>
      </header>

      <HistoryDrawer
        activeId={effectiveId}
        open={historyOpen}
        onSelect={(id) => {
          // Switching is permitted only when the panel owns its id.
          // When a parent passed a fixed `conversationId` prop we can't
          // override it from here — silently no-op in that case.
          if (conversationId === undefined) {
            setOwnedId(id);
            setHistoryOpen(false);
          }
        }}
        onNew={() => {
          if (conversationId === undefined) {
            setOwnedId(newConversationId());
            setHistoryOpen(false);
          }
        }}
      />

      <div className={styles.scroll} ref={scrollRef}>
        {messages.length === 0 && !streamingDraft && (
          <p className={styles.empty}>{t("chat.panel.empty")}</p>
        )}
        {messages.map((m, idx) => {
          // System rows in v1 are exclusively transient "tool_approval_required"
          // meta entries minted by useChatStream — render the ApprovalCard
          // inline rather than the usual bubble.
          const approvalBlock = readApprovalBlock(m);
          if (approvalBlock) {
            const cardKey = `${approvalBlock.tool_call_id}-${idx}`;
            const expired = approvalBlock.expired === true;
            const status = expired
              ? "expired"
              : (cardStatus[approvalBlock.tool_call_id] ?? "pending");
            return (
              <ApprovalCard
                key={cardKey}
                toolCallId={approvalBlock.tool_call_id}
                name={approvalBlock.name as ApprovalCardToolName}
                input={approvalBlock.input ?? {}}
                preview={approvalBlock.preview}
                status={status}
                errorMessage={cardError[approvalBlock.tool_call_id]}
                onApprove={() => handleApprove(approvalBlock.tool_call_id)}
                onCancel={() => handleCancel(approvalBlock.tool_call_id)}
              />
            );
          }
          return (
            <MessageBubble
              key={`${m.timestamp}-${idx}`}
              message={m}
              toolCalls={toolCalls}
            />
          );
        })}
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

/** Extract the ``tool_approval_required`` block from a transient system
 * row, if any. Returns ``null`` for user/assistant rows or system rows
 * that do not match the expected shape. */
function readApprovalBlock(m: ChatMessage): {
  tool_call_id: string;
  name: string;
  input?: Record<string, unknown>;
  preview?: Record<string, unknown>;
  expired?: boolean;
} | null {
  if (m.role !== "system") return null;
  if (!Array.isArray(m.content)) return null;
  const first = m.content[0] as Record<string, unknown> | undefined;
  if (!first || first.type !== "tool_approval_required") return null;
  if (typeof first.tool_call_id !== "string") return null;
  if (typeof first.name !== "string") return null;
  return {
    tool_call_id: first.tool_call_id,
    name: first.name,
    input: (first.input as Record<string, unknown> | undefined) ?? undefined,
    preview: first.preview as Record<string, unknown> | undefined,
    expired: first.expired === true,
  };
}

export default ChatPanel;

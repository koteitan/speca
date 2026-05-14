import type { ChatMessage, ContentBlock, ToolCallView } from "./types";
import { ToolCard } from "./ToolCard";
import styles from "./MessageBubble.module.css";

/**
 * Renders one message bubble.
 *
 * Layout:
 * - ``role="user"``  → right-aligned, subtle bg.
 * - ``role="assistant"`` → left-aligned, plain bg.
 *
 * Content is structurally rich (``ContentBlock[]``) so we walk it and emit:
 * - text → plain prose paragraph
 * - tool_use → ``<ToolCard>`` (status from ``toolCalls`` map)
 * - tool_result → suppressed (already rendered inside the upstream
 *   ``ToolCard`` of the same ``tool_use_id``); showing it twice would
 *   duplicate large JSON blobs.
 */

export interface MessageBubbleProps {
  message: ChatMessage;
  toolCalls: Record<string, ToolCallView>;
}

function getBlocks(message: ChatMessage): ContentBlock[] {
  if (Array.isArray(message.content)) return message.content;
  return [{ type: "text", text: message.content }];
}

export function MessageBubble({ message, toolCalls }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const blocks = getBlocks(message);

  return (
    <div
      className={`${styles.row} ${isUser ? styles.user : styles.assistant}`}
      data-testid={`bubble-${message.role}`}
    >
      <div className={styles.bubble}>
        {blocks.map((block, idx) => {
          if (!block || typeof block !== "object") return null;
          const type = (block as { type?: string }).type;

          if (type === "text") {
            const text = (block as { type: "text"; text: string }).text;
            // Preserve newlines but keep paragraph spacing tight.
            return (
              <p key={idx} className={styles.text}>
                {text}
              </p>
            );
          }

          if (type === "tool_use") {
            const t = block as {
              type: "tool_use";
              id: string;
              name: string;
              input: Record<string, unknown>;
            };
            const view = toolCalls[t.id];
            return (
              <ToolCard
                key={t.id || idx}
                toolName={t.name}
                input={t.input ?? {}}
                result={view?.result}
                status={view?.status ?? "done"}
              />
            );
          }

          if (type === "tool_result") {
            // Suppressed — the corresponding ToolCard above already shows
            // the result. Returning null keeps the layout tidy.
            return null;
          }

          // Unknown block types fall through to a debug pre-block. This
          // is the most forgiving option: a future SDK addition surfaces
          // visibly rather than vanishing silently.
          return (
            <pre key={idx} className={styles.unknown}>
              {JSON.stringify(block)}
            </pre>
          );
        })}
      </div>
    </div>
  );
}

export default MessageBubble;

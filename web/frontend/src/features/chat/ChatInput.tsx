import { useCallback, useRef } from "react";

import styles from "./ChatInput.module.css";

/**
 * Multi-line text input at the bottom of the chat panel.
 *
 * Keyboard semantics match the ChatGPT / Claude.ai conventions:
 *   - Enter         → submit
 *   - Shift+Enter   → newline
 *
 * The textarea auto-grows up to a max height so a long paste does not
 * cover the entire panel. While ``disabled`` (i.e. a turn is streaming)
 * we keep the value visible but greyed out so the user can review what
 * they sent without it being editable.
 */

export interface ChatInputProps {
  disabled: boolean;
  onSubmit: (text: string) => void;
  placeholder?: string;
}

export function ChatInput({ disabled, onSubmit, placeholder }: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const submit = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    const text = ta.value.trim();
    if (!text || disabled) return;
    onSubmit(text);
    ta.value = "";
    // Reset auto-grow.
    ta.style.height = "auto";
  }, [disabled, onSubmit]);

  return (
    <form
      className={styles.form}
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <textarea
        ref={textareaRef}
        className={styles.textarea}
        rows={1}
        disabled={disabled}
        placeholder={placeholder ?? "Message Claude (read-only mode)"}
        aria-label="Chat input"
        onInput={(e) => {
          const el = e.currentTarget;
          el.style.height = "auto";
          el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <button
        type="submit"
        className={styles.sendButton}
        disabled={disabled}
        aria-label="Send message"
      >
        {disabled ? "…" : "Send"}
      </button>
    </form>
  );
}

export default ChatInput;

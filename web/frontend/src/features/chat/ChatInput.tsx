import { useCallback, useEffect, useRef } from "react";

import { useT } from "@/i18n/useT";

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
 *
 * `initialDraft` lets the parent seed the textarea (e.g. "Ask Claude
 * about this finding" prefill). We push it via an effect rather than a
 * `defaultValue` so a *new* prefill while the panel is already mounted
 * also wins — `defaultValue` is sampled only on first render.
 */

export interface ChatInputProps {
  disabled: boolean;
  onSubmit: (text: string) => void;
  placeholder?: string;
  /** One-shot textarea seed. Re-applying the same value is a no-op; the
   * parent should change the value to push a new draft. */
  initialDraft?: string;
}

export function ChatInput({
  disabled,
  onSubmit,
  placeholder,
  initialDraft,
}: ChatInputProps) {
  const t = useT();
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Push a fresh draft into the uncontrolled textarea. Skips empty
  // strings so we never blow away a user-typed draft on first paint.
  useEffect(() => {
    if (!initialDraft) return;
    const ta = textareaRef.current;
    if (!ta) return;
    ta.value = initialDraft;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
    // Park the caret at the end so the user can keep typing.
    ta.focus();
    ta.setSelectionRange(ta.value.length, ta.value.length);
  }, [initialDraft]);

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
        placeholder={placeholder ?? t("chat.input.placeholder_default")}
        aria-label={t("chat.input.input_aria")}
        onInput={(e) => {
          const el = e.currentTarget;
          el.style.height = "auto";
          el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
        }}
        onKeyDown={(e) => {
          // Skip IME composition confirms — Japanese / Chinese / Korean
          // users press Enter to commit the candidate, NOT to send the
          // message. ``isComposing`` (or the legacy ``keyCode === 229``)
          // catches that case in every modern browser. Without this
          // guard the message ships mid-conversion.
          const ime =
            e.nativeEvent.isComposing || e.nativeEvent.keyCode === 229;
          if (e.key === "Enter" && !e.shiftKey && !ime) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <button
        type="submit"
        className={styles.sendButton}
        disabled={disabled}
        aria-label={t("chat.input.send_aria")}
      >
        {disabled ? "…" : t("chat.input.send_label")}
      </button>
    </form>
  );
}

export default ChatInput;

// Slice D1 — sticky log tail for one phase row.
//
// Display-only component: the caller (`useRunStream` via `PhaseRow`)
// owns the rolling buffer and is responsible for capping it. We just
// render and manage auto-scroll / clipboard / download UX here.
//
// Auto-scroll model:
//   - `autoScroll` starts true.
//   - When the user scrolls *up* (away from the bottom), we flip to
//     false so we don't yank their view back on the next log line.
//   - The "Resume auto-scroll" button (visible in the paused state)
//     scrolls back to bottom and re-arms the auto-scroll effect.
//   - When new lines arrive and `autoScroll` is true we set
//     `scrollTop = scrollHeight` inside a layout effect.

import { useEffect, useRef, useState } from "react";

import { useT } from "@/i18n/useT";

import styles from "./LogTail.module.css";

export interface LogTailProps {
  /** Phase id, used as a stable filename for the download action. */
  phaseId?: string;
  /** Log lines in chronological order. May be empty. */
  lines: string[];
}

/** Pixel threshold to consider "the user is at the bottom". */
const STICK_TO_BOTTOM_THRESHOLD_PX = 8;

export function LogTail({ phaseId, lines }: LogTailProps) {
  const t = useT();
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);

  // Stick the viewport to the bottom whenever lines change *and* the
  // user hasn't paused auto-scroll.
  useEffect(() => {
    if (!autoScroll) return;
    const el = containerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [lines, autoScroll]);

  // If the user scrolls away from the bottom, pause auto-scroll. If they
  // scroll back to the bottom, re-arm it. This is intentionally driven
  // off the DOM event (rather than tracking pointer events) so keyboard
  // and trackpad nudges work the same way.
  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const distanceFromBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distanceFromBottom <= STICK_TO_BOTTOM_THRESHOLD_PX) {
      if (!autoScroll) setAutoScroll(true);
    } else {
      if (autoScroll) setAutoScroll(false);
    }
  };

  const handleResume = () => {
    const el = containerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
    setAutoScroll(true);
  };

  const handleCopy = async () => {
    const text = lines.join("\n");
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      }
    } catch {
      // Clipboard access blocked (insecure origin / focus issue). We
      // intentionally swallow — there's no UI affordance to fall back
      // to in v1 beyond the Download button below.
    }
  };

  const handleDownload = () => {
    const text = lines.join("\n");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${phaseId ?? "phase"}.log`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Defer revocation a frame so Safari finishes the download trigger.
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  return (
    <div className={styles.wrapper} data-testid="log-tail">
      <div className={styles.toolbar}>
        <span
          className={`${styles.status} ${autoScroll ? styles.statusOn : styles.statusOff}`}
          aria-live="polite"
        >
          {autoScroll
            ? t("runs.detail.log_tail.auto_scroll")
            : t("runs.detail.log_tail.auto_scroll_paused")}
        </span>
        <span className={styles.spacer} />
        {!autoScroll ? (
          <button
            type="button"
            className={styles.toolbarBtn}
            onClick={handleResume}
          >
            {t("runs.detail.log_tail.auto_scroll")}
          </button>
        ) : null}
        <button
          type="button"
          className={styles.toolbarBtn}
          onClick={handleCopy}
          disabled={lines.length === 0}
        >
          {copied ? "✓" : t("runs.detail.log_tail.copy")}
        </button>
        <button
          type="button"
          className={styles.toolbarBtn}
          onClick={handleDownload}
          disabled={lines.length === 0}
        >
          {t("runs.detail.log_tail.download")}
        </button>
      </div>
      <div
        ref={containerRef}
        className={styles.scroller}
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        aria-relevant="additions"
      >
        {lines.length === 0 ? (
          <div className={styles.empty}>
            {t("runs.detail.log_tail.empty")}
          </div>
        ) : (
          <pre className={styles.pre}>{lines.join("\n")}</pre>
        )}
      </div>
    </div>
  );
}

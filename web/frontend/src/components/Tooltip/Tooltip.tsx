// Term tooltip with built-in glossary.
//
// Usage:
//   <Tooltip term="severity">Severity</Tooltip>
//
// Behaviour:
//   - hovers / focuses the wrapper → bubble appears
//   - mouse leave / blur / Escape → bubble closes
//   - `term` not in glossary → renders children verbatim (no `?`)
//   - if no children, falls back to the `term` text itself, so
//     `<Tooltip term="CWE" />` is a complete display.
//
// A11y: the bubble is `role="tooltip"` and connected via aria-describedby.
// Both pointer and keyboard users can dismiss with Escape.

import {
  useCallback,
  useEffect,
  useId,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { lookupGlossary } from "./glossary";
import styles from "./Tooltip.module.css";

export type TooltipPosition = "top" | "bottom" | "left" | "right";

export interface TooltipProps {
  term: string;
  children?: ReactNode;
  position?: TooltipPosition;
}

export function Tooltip({ term, children, position = "top" }: TooltipProps) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const description = lookupGlossary(term);
  const label = children ?? term;

  // ESC closes the tooltip from anywhere on the document while it's open
  // — covers the case where focus has shifted to an inner control but the
  // user still expects the global "dismiss" affordance.
  useEffect(() => {
    if (!open) return;
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const handleKeyDown = useCallback((event: KeyboardEvent<HTMLSpanElement>) => {
    if (event.key === "Escape") {
      setOpen(false);
    }
  }, []);

  // When the term isn't registered we degrade gracefully: emit the
  // children as-is so callers don't have to guard.
  if (!description) {
    return <>{label}</>;
  }

  return (
    <span
      className={styles.wrapper}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      aria-describedby={open ? id : undefined}
    >
      <span className={styles.label}>{label}</span>
      <span className={styles.marker} aria-hidden="true">
        ?
      </span>
      {open ? (
        <span
          id={id}
          role="tooltip"
          className={styles.bubble}
          data-position={position}
        >
          {description}
        </span>
      ) : null}
    </span>
  );
}

export default Tooltip;

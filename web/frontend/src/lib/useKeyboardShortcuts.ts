// useKeyboardShortcuts — global keyboard binding registry.
//
// Migrates the TUI key bindings spelled out in SPECA_CLI_SPEC §10.3
// ("Every interaction has a keyboard binding") to the Web UI surface,
// adapted for the affordances browsers actually grant us.
//
// Behaviour matrix:
//
//   ?            → opens the keyboard-shortcuts help modal
//   Esc          → onCloseAll (closes the open modal / chat panel)
//   c            → toggles the chat panel
//   g r          → navigate to /runs            (2-key sequence)
//   g s          → navigate to /settings        (2-key sequence)
//   g d          → navigate to /diagnostics     (2-key sequence)
//   /            → focuses the findings filter input on the findings list
//   j / k        → moves keyboard focus to the next / previous finding row
//
// Input-focus guard:
//   When `document.activeElement` is an <input>, <textarea>, <select>, or
//   a `[contenteditable]` element, every shortcut is suppressed **except**
//   `Esc`. This is critical for the chat panel — pressing `?` while typing
//   "?" inside the textarea must insert a literal `?`, not pop a modal.
//
// Modifiers:
//   Shortcuts only fire on bare key-presses (no Ctrl / Meta / Alt).
//   Shift is allowed because `?` is `Shift+/` on US layouts.
//
// 2-key sequence (`g + <next>`):
//   After `g`, the hook holds a pending state for 1.5 s. The next bare
//   keystroke either dispatches the navigation or clears the pending
//   state. Pressing `Esc` cancels the pending sequence.
//
// Registration:
//   The hook attaches a single window-level `keydown` listener (capture
//   phase). It is intentionally idempotent — passing the same handlers
//   object repeatedly is safe. Handlers are read via a ref so callers do
//   not need to memoise them.

import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

/** Selector for finding rows that participate in the `j`/`k` navigation. */
const FINDING_ROW_SELECTOR = "[data-property-id]";

/** Filter input selector — try the SPEC name first, fall back to the
 *  existing FilterInput test id. Whichever matches first wins. */
const FILTER_INPUT_SELECTORS = [
  '[data-testid="findings-filter-input"]',
  '[data-testid="filter-dsl-input"]',
];

const PENDING_G_TIMEOUT_MS = 1500;

export interface KeyboardShortcutHandlers {
  /** Open the keyboard-shortcuts help modal. */
  onOpenHelp?: () => void;
  /** Close any open modal / chat panel. Fires on Esc. */
  onCloseAll?: () => void;
  /** Toggle the chat panel. Fires on `c`. */
  onToggleChat?: () => void;
}

function isEditableTarget(el: Element | null): boolean {
  if (!el) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
    return true;
  }
  // `[contenteditable]` covers contenteditable="" and contenteditable="true".
  if (el instanceof HTMLElement && el.isContentEditable) {
    return true;
  }
  return false;
}

function hasModifier(event: KeyboardEvent): boolean {
  // Shift is allowed (Shift+/ → "?"). Ctrl/Meta/Alt are not.
  return event.ctrlKey || event.metaKey || event.altKey;
}

/**
 * Focus the first findings filter input on the current page.
 * Returns true if an input was found and focused.
 */
function focusFindingsFilter(): boolean {
  for (const selector of FILTER_INPUT_SELECTORS) {
    const el = document.querySelector<HTMLElement>(selector);
    if (el) {
      el.focus();
      // If it's a text-style input, also select existing content so the
      // user can type to replace.
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
        try {
          el.select();
        } catch {
          /* select() can throw on non-text inputs — safe to ignore. */
        }
      }
      return true;
    }
  }
  return false;
}

/**
 * Move focus to the next / previous finding row on the current page.
 * `direction` is +1 for j (next) and -1 for k (prev).
 */
function moveFindingFocus(direction: 1 | -1): boolean {
  const rows = Array.from(
    document.querySelectorAll<HTMLElement>(FINDING_ROW_SELECTOR),
  );
  if (rows.length === 0) return false;

  // Find the index of the row that currently contains focus (if any). A
  // row's `Link` child is the actual focusable element, so we walk up to
  // find which row the active element belongs to.
  const active = document.activeElement as HTMLElement | null;
  let currentIndex = -1;
  if (active) {
    for (let i = 0; i < rows.length; i++) {
      if (rows[i].contains(active)) {
        currentIndex = i;
        break;
      }
    }
  }

  let nextIndex: number;
  if (currentIndex === -1) {
    // No row focused yet — jump to the first (j) or last (k).
    nextIndex = direction === 1 ? 0 : rows.length - 1;
  } else {
    nextIndex = currentIndex + direction;
    if (nextIndex < 0) nextIndex = 0;
    if (nextIndex >= rows.length) nextIndex = rows.length - 1;
  }

  const target = rows[nextIndex];
  // Prefer a focusable descendant (<a> / <button>) so keyboard activation
  // (Enter) navigates correctly.
  const focusable =
    target.querySelector<HTMLElement>("a[href], button:not([disabled])") ??
    target;
  focusable.focus();
  if (typeof focusable.scrollIntoView === "function") {
    focusable.scrollIntoView({ block: "nearest" });
  }
  return true;
}

/**
 * Register the global keyboard-shortcut listener.
 *
 * Pass an object of `on*` callbacks for the surfaces this hook should
 * delegate to (open help modal, close everything, toggle chat). Navigation
 * shortcuts (`g r` / `g s` / `g d`) and findings-list shortcuts
 * (`/`, `j`, `k`) are handled internally — no extra wiring required.
 */
export function useKeyboardShortcuts(
  handlers: KeyboardShortcutHandlers,
): void {
  const navigate = useNavigate();
  // Stash handlers in a ref so the keydown listener always sees the
  // latest closures without re-binding on every render.
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    // Pending "g" state for 2-key sequences.
    let pendingG = false;
    let pendingTimer: number | null = null;

    const clearPending = () => {
      pendingG = false;
      if (pendingTimer !== null) {
        window.clearTimeout(pendingTimer);
        pendingTimer = null;
      }
    };

    const armPending = () => {
      clearPending();
      pendingG = true;
      pendingTimer = window.setTimeout(() => {
        pendingG = false;
        pendingTimer = null;
      }, PENDING_G_TIMEOUT_MS);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      // Esc is always honoured — even while typing in chat — so users can
      // bail out of an open modal / chat panel.
      if (event.key === "Escape") {
        // If a `g` is pending, clear it first; do not also trigger close.
        if (pendingG) {
          clearPending();
          return;
        }
        handlersRef.current.onCloseAll?.();
        return;
      }

      // Suppress everything else when focus is in an input-like element
      // or when a modifier other than Shift is held.
      if (isEditableTarget(document.activeElement)) return;
      if (hasModifier(event)) return;
      // Ignore composition / IME events. `event.isComposing` is true while
      // an IME candidate window is open; key 229 is the legacy fallback.
      if (event.isComposing || event.keyCode === 229) return;

      const key = event.key;

      // --- 2-key sequence: `g` then one of r / s / d ---
      if (pendingG) {
        if (key === "r") {
          event.preventDefault();
          clearPending();
          navigate("/runs");
          return;
        }
        if (key === "s") {
          event.preventDefault();
          clearPending();
          navigate("/settings");
          return;
        }
        if (key === "d") {
          event.preventDefault();
          clearPending();
          navigate("/diagnostics");
          return;
        }
        // Any other key cancels the pending sequence — we still let it
        // fall through so e.g. pressing `g` then `?` opens help.
        clearPending();
      }

      if (key === "g") {
        event.preventDefault();
        armPending();
        return;
      }

      // `?` — open the help modal. On US layouts this is Shift+/, on JP
      // layouts it's Shift+ろ; the resulting `event.key` is "?" on both.
      if (key === "?") {
        event.preventDefault();
        handlersRef.current.onOpenHelp?.();
        return;
      }

      if (key === "c") {
        event.preventDefault();
        handlersRef.current.onToggleChat?.();
        return;
      }

      if (key === "/") {
        if (focusFindingsFilter()) {
          // Only preventDefault when there's actually an input to focus —
          // otherwise let "/" pass through (browser quick-find etc.).
          event.preventDefault();
        }
        return;
      }

      if (key === "j") {
        if (moveFindingFocus(1)) {
          event.preventDefault();
        }
        return;
      }

      if (key === "k") {
        if (moveFindingFocus(-1)) {
          event.preventDefault();
        }
        return;
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      clearPending();
    };
  }, [navigate]);
}

export default useKeyboardShortcuts;

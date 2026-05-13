// chatPrefillSlice — one-shot prefill bus from feature pages → ChatPanel.
//
// When the user clicks "Ask Claude about this finding" on FindingDetailPage,
// we need three things to happen across the React subtree:
//   1. The right-side chat panel must open (handled by `chatUiSlice.setOpen`).
//   2. The ChatPanel must show a "Context attached" badge so the user
//      knows their question is grounded in the selected finding.
//   3. The ChatInput must auto-fill with a starter question that the user
//      can edit or send immediately.
//
// This slice is the bus. The producer (FindingDetailPage) calls
// `setPrefill(...)`. The consumer (ChatPanel) reads it on every mount
// and calls `consume()` once it has wired the prefill into its own
// state — `consume()` clears the slice so a subsequent panel re-open
// (e.g. after the user closes & re-opens chat without leaving the page)
// does not silently reapply stale context.
//
// In-memory only, like `chatUiSlice` — a prefill is a UI affordance, not
// user data; persisting it would be both surprising (carrying across tabs
// or page reloads) and a leak of the finding context onto disk.

import { create } from "zustand";

export interface ChatPrefillContext {
  /** Stable id for de-duplication & display, e.g. `PROP-6a4-inv-042`. */
  contextId: string;
  /** Short human-readable label rendered in the "Context attached" pill. */
  label: string;
  /** Block of text prepended to the first user message. Plain text, NOT
   * rendered as markdown — we want what the user sees to match what gets
   * sent. */
  contextBlock: string;
  /** Suggested first message. The user can edit or wipe before sending. */
  draftMessage: string;
  /** Set by the producer; the consumer uses it to know when a prefill
   * is new vs. one it has already consumed. Wall-clock ms is fine. */
  createdAt: number;
}

export interface ChatPrefillState {
  prefill: ChatPrefillContext | null;
  setPrefill: (prefill: Omit<ChatPrefillContext, "createdAt">) => void;
  consume: () => ChatPrefillContext | null;
  clear: () => void;
}

export const useChatPrefill = create<ChatPrefillState>((set, get) => ({
  prefill: null,
  setPrefill: (prefill) =>
    set({ prefill: { ...prefill, createdAt: Date.now() } }),
  /**
   * Read-and-clear. Returns the current prefill (if any) and atomically
   * wipes the slice so a re-render does not see the same prefill twice.
   */
  consume: () => {
    const current = get().prefill;
    if (current) set({ prefill: null });
    return current;
  },
  clear: () => set({ prefill: null }),
}));

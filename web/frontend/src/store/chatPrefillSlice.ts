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
//
// CLI spec §8.5 — Ask Claude must keep the injected context under a
// 50 KB cap. The default is generous (Claude Sonnet's 200K context can
// fit a few of those) but caps the worst case where someone clicks
// "Ask about this finding" on a property whose evidence_snippet is
// pasted from a 4 MB diff. `setPrefill` here truncates over-budget
// contextBlock values with a clearly-marked tail note so the
// downstream message Claude sees is honest about what was dropped.

import { create } from "zustand";

/** Cap on the byte length of `contextBlock` (CLI spec §8.5). */
export const CHAT_CONTEXT_BYTE_CAP = 50 * 1024;

function byteLen(text: string): number {
  // `TextEncoder` is universal across browsers / jsdom — uses UTF-8.
  return new TextEncoder().encode(text).length;
}

function truncateToBytes(text: string, cap: number): string {
  if (byteLen(text) <= cap) return text;
  // Reserve room for a tail marker so the model sees an explicit
  // "truncated" signal instead of silently dropping evidence.
  const marker = "\n…(context truncated to 50 KB budget; see CLI spec §8.5)";
  const markerBytes = byteLen(marker);
  const budget = Math.max(0, cap - markerBytes);
  // Walk the string from the front by character and keep the longest
  // prefix that fits. We cannot just `slice(0, cap)` because cap is
  // bytes and slice is UTF-16 code units; a 2-byte UTF-8 character can
  // be 1 code unit in JavaScript.
  const encoder = new TextEncoder();
  let lo = 0;
  let hi = text.length;
  while (lo < hi) {
    const mid = (lo + hi + 1) >>> 1;
    if (encoder.encode(text.slice(0, mid)).length <= budget) lo = mid;
    else hi = mid - 1;
  }
  return text.slice(0, lo) + marker;
}

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
    set({
      prefill: {
        ...prefill,
        // Enforce the §8.5 cap at the producer boundary so every consumer
        // (ChatPanel, history persistence) sees the same already-capped
        // string. Callers must not assume their pre-cap text survives.
        contextBlock: truncateToBytes(prefill.contextBlock, CHAT_CONTEXT_BYTE_CAP),
        createdAt: Date.now(),
      },
    }),
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

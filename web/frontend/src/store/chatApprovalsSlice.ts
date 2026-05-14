// chatApprovalsSlice — pending side-effect tool approvals (Slice C3).
//
// The chat runtime suspends an SSE stream when the model proposes a
// side-effecting tool (``launch_pipeline`` / ``stop_pipeline``) and waits
// for the user to ``POST /api/chat/tool_approve``. While the stream is
// suspended, the SPA needs to remember which approvals are outstanding
// so:
//
//   - the Header can show a "{n} approval pending" badge while the chat
//     panel is collapsed, and
//   - a fresh ApprovalCard render (e.g. after a layout reflow) can
//     reconstruct its preview / tool name from the same source rather
//     than relying on the assistant message blocks alone.
//
// Persistence
// -----------
// **In-memory only.** Reloading the tab drops the pending set on purpose:
// the SSE connection that emitted ``tool_approval_required`` is gone too
// (HTTP request closed), and the backend's 10-minute timeout will reap
// the orphaned approval. Persisting to localStorage would resurrect
// "ghost" approvals that nothing can resolve.
//
// Shape
// -----
// The pending list is keyed only by ``tool_call_id`` because Anthropic
// guarantees uniqueness within a turn and v1 surface is single-user /
// single-tab. Two concurrent conversations would still namespace by
// ``conversationId`` so we keep it on the record for future use.

import { create } from "zustand";

/** Tool names that may appear in a pending approval. v1 set only. */
export type ApprovalToolName = "launch_pipeline" | "stop_pipeline";

export interface PendingApproval {
  conversationId: string;
  toolCallId: string;
  name: ApprovalToolName;
  /** Raw tool input as proposed by the model. */
  input: Record<string, unknown>;
  /** Optional preview block built by the backend (``_render_preview``). */
  preview?: Record<string, unknown>;
  /** Wall-clock ms at receive time — useful for "expired (10 min)" UI. */
  receivedAt: number;
}

export interface ChatApprovalsState {
  pending: PendingApproval[];
  add: (approval: PendingApproval) => void;
  remove: (toolCallId: string) => void;
  /** Number of currently-pending approvals. */
  count: () => number;
  /** Look up a pending approval by tool_call_id (or undefined). */
  get: (toolCallId: string) => PendingApproval | undefined;
}

export const useChatApprovals = create<ChatApprovalsState>((set, getStore) => ({
  pending: [],
  add: (approval) =>
    set((state) => {
      // Replace any prior entry with the same tool_call_id rather than
      // accumulating duplicates if the runtime ever re-emits the event.
      const filtered = state.pending.filter(
        (p) => p.toolCallId !== approval.toolCallId,
      );
      return { pending: [...filtered, approval] };
    }),
  remove: (toolCallId) =>
    set((state) => ({
      pending: state.pending.filter((p) => p.toolCallId !== toolCallId),
    })),
  count: () => getStore().pending.length,
  get: (toolCallId) =>
    getStore().pending.find((p) => p.toolCallId === toolCallId),
}));

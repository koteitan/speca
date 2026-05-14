// Wire types for the Chat slice.
//
// 1:1 mirror of web/server/schemas/chat.py and the SSE event shapes defined
// in web/server/services/chat_runtime.py. Keep these in sync by hand — v0
// does not generate types from the OpenAPI schema.

/**
 * ``"system"`` is **client-only** in v1: the backend persists only
 * ``user`` and ``assistant`` messages, but the SPA inserts a transient
 * ``system`` row carrying a ``tool_approval_required`` block when the
 * runtime suspends on a side-effect tool call (Slice C3). On reload the
 * row is gone because chat_history filters non-user/assistant roles —
 * intentionally, since the approval state lives only in memory.
 */
export type ChatRole = "user" | "assistant" | "system";

/** A single Anthropic-style content block (text / tool_use / tool_result / ...). */
export type ContentBlock =
  | { type: "text"; text: string }
  | { type: "tool_use"; id: string; name: string; input: Record<string, unknown> }
  | {
      type: "tool_result";
      tool_use_id: string;
      content: string;
      is_error?: boolean;
    }
  | { type: string; [key: string]: unknown };

export interface ChatMessage {
  role: ChatRole;
  /** Backend may persist either a plain string or a list of structured blocks. */
  content: ContentBlock[] | string;
  timestamp: string;
}

export interface Conversation {
  conversation_id: string;
  messages: ChatMessage[];
  created_at: string;
  last_message_at: string;
}

export interface ConversationSummary {
  conversation_id: string;
  last_message_at: string;
  title: string | null;
}

// --- SSE event shapes --------------------------------------------------------

export type ContentBlockDeltaEvent = {
  type: "content_block_delta";
  delta: { text: string };
};

export type ToolInputPartialEvent = {
  type: "tool_input_partial";
  partial_json: string;
};

export type ToolUseStartEvent = {
  type: "tool_use_start";
  tool_call_id: string;
  name: string;
  input_partial: Record<string, unknown>;
};

export type ToolUseResultEvent = {
  type: "tool_use_result";
  tool_call_id: string;
  result: Record<string, unknown>;
};

export type ErrorEvent = {
  type: "error";
  reason: string;
  /** Present when ``reason === "tool_not_allowed"``. */
  tool?: string;
  /** Present when ``reason === "approval_timeout"`` — see Slice C3. */
  tool_call_id?: string;
  message?: string;
};

/**
 * Backend signals that a side-effecting tool needs explicit user approval
 * before it will run. Emitted by ``_handle_side_effect_call`` in
 * ``web/server/services/chat_runtime.py``. The SSE stream stays open but
 * idle until the SPA POSTs to ``/chat/tool_approve``. See Slice C1+C2.
 */
export type ToolApprovalRequiredEvent = {
  type: "tool_approval_required";
  tool_call_id: string;
  name: string;
  input: Record<string, unknown>;
  preview?: Record<string, unknown>;
};

export type MessageStopEvent = {
  type: "message_stop";
  usage: { input_tokens?: number; output_tokens?: number };
  stop_reason?: string;
};

export type ChatStreamEvent =
  | ContentBlockDeltaEvent
  | ToolInputPartialEvent
  | ToolUseStartEvent
  | ToolUseResultEvent
  | ToolApprovalRequiredEvent
  | ErrorEvent
  | MessageStopEvent;

// --- Tool call render state --------------------------------------------------

export type ToolCallStatus = "running" | "done" | "error";

export interface ToolCallView {
  tool_call_id: string;
  name: string;
  input: Record<string, unknown>;
  result?: Record<string, unknown>;
  status: ToolCallStatus;
}

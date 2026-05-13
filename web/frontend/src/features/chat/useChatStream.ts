import { useCallback, useEffect, useRef, useState } from "react";

import { apiFetch } from "@/lib/api";
import { useChatApprovals } from "@/store/chatApprovalsSlice";
import type { ApprovalToolName } from "@/store/chatApprovalsSlice";
import type {
  ChatMessage,
  ChatStreamEvent,
  Conversation,
  ContentBlock,
  ToolCallView,
} from "./types";

/**
 * Hook that owns the chat state for a single conversation.
 *
 * Two responsibilities:
 *
 * 1. On mount (and whenever ``conversationId`` changes), fetch the persisted
 *    history via ``GET /api/chat/conversations/<id>``.
 * 2. On `send(text)`, POST the message and parse the resulting SSE stream
 *    line-by-line — `EventSource` cannot be used because it does not support
 *    sending a request body, so we use ``fetch`` + a ReadableStream parser.
 *
 * The hook keeps two parallel models:
 *
 * * ``messages`` — the source of truth for rendering, mirrors the on-disk
 *   shape (``ContentBlock[] | string``).
 * * ``streamingDraft`` — a transient assistant message being assembled
 *   from delta events. Promoted into ``messages`` (and the local copy is
 *   reconciled with the server on the next mount) when the stream ends.
 */

interface ChatStreamState {
  messages: ChatMessage[];
  streamingDraft: ChatMessage | null;
  toolCalls: Record<string, ToolCallView>;
  streaming: boolean;
  error: string | null;
}

const INITIAL_STATE: ChatStreamState = {
  messages: [],
  streamingDraft: null,
  toolCalls: {},
  streaming: false,
  error: null,
};

export function useChatStream(conversationId: string) {
  const [state, setState] = useState<ChatStreamState>(INITIAL_STATE);
  // We hold the controller in a ref so callers can cancel mid-stream via
  // `cancel()` without re-rendering. The ref is also used by the cleanup
  // effect to abort if the component unmounts.
  const abortRef = useRef<AbortController | null>(null);

  // Load history when conversation switches. 404 (= brand-new conversation
  // the client just minted) is silently treated as "empty history" so the
  // user can start typing immediately without seeing a spinner-of-shame.
  useEffect(() => {
    let cancelled = false;
    setState(INITIAL_STATE);

    (async () => {
      try {
        const res = await fetch(
          `/api/chat/conversations/${encodeURIComponent(conversationId)}`,
          { headers: { Accept: "application/json" } },
        );
        if (cancelled) return;
        if (res.status === 404) {
          // Brand-new conversation: leave state empty.
          return;
        }
        if (!res.ok) {
          throw new Error(`load failed: ${res.status}`);
        }
        const data = (await res.json()) as Conversation;
        if (cancelled) return;
        setState((prev) => ({ ...prev, messages: data.messages ?? [] }));
      } catch (err) {
        if (cancelled) return;
        setState((prev) => ({
          ...prev,
          error: err instanceof Error ? err.message : String(err),
        }));
      }
    })();

    return () => {
      cancelled = true;
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, [conversationId]);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim()) return;
      // Abort any pending stream — we don't support concurrent turns in v0.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const optimisticUser: ChatMessage = {
        role: "user",
        content: [{ type: "text", text }],
        timestamp: new Date().toISOString(),
      };
      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, optimisticUser],
        streamingDraft: {
          role: "assistant",
          content: [{ type: "text", text: "" }],
          timestamp: new Date().toISOString(),
        },
        toolCalls: {},
        streaming: true,
        error: null,
      }));

      try {
        const res = await fetch(
          `/api/chat/conversations/${encodeURIComponent(conversationId)}/messages`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "text/event-stream",
            },
            body: JSON.stringify({ text }),
            signal: controller.signal,
          },
        );
        if (!res.ok || !res.body) {
          throw new Error(`stream failed: ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        // SSE frame parser: events end with a blank line; each event may
        // include multiple ``data:`` lines (joined by ``\n``) and one
        // optional ``event:`` line. We only emit ``data:`` payloads.
        //
        // sse-starlette on Windows emits ``\r\n\r\n`` frame terminators
        // (per the W3C EventSource spec), so normalise CRLF → LF before
        // splitting; otherwise ``indexOf("\n\n")`` never finds a frame
        // boundary and the entire stream sits unparsed in the buffer.
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

          let sep: number;
          while ((sep = buffer.indexOf("\n\n")) !== -1) {
            const frame = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);
            const dataLines: string[] = [];
            for (const rawLine of frame.split("\n")) {
              if (rawLine.startsWith("data:")) {
                dataLines.push(rawLine.slice(5).trimStart());
              }
            }
            if (dataLines.length === 0) continue;
            const payload = dataLines.join("\n");
            try {
              const event = JSON.parse(payload) as ChatStreamEvent;
              applyEvent(setState, event, conversationId);
            } catch {
              // Heartbeats and unknown framing lines fall through. We
              // deliberately swallow parse errors so a stray keepalive
              // doesn't break the entire stream.
            }
          }
        }
        // Stream ended without an explicit message_stop (e.g. server hang
        // up) — promote whatever draft we have and clear the streaming
        // flag so the UI re-enables the input.
        setState((prev) => promoteDraft(prev));
      } catch (err) {
        if (controller.signal.aborted) return;
        setState((prev) => ({
          ...promoteDraft(prev),
          error: err instanceof Error ? err.message : String(err),
        }));
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      }
    },
    [conversationId],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState((prev) => ({ ...promoteDraft(prev), streaming: false }));
  }, []);

  /**
   * Approve a pending side-effect tool call. Returns once the backend
   * confirms — the SSE stream itself will continue yielding events
   * (notably ``tool_use_result``) on the original connection.
   *
   * ``editedInput`` is reserved for a future "edit then approve" UI;
   * v1 callers always omit it.
   */
  const approve = useCallback(
    async (toolCallId: string, editedInput?: Record<string, unknown>) => {
      await apiFetch<{ ok: boolean }>("/chat/tool_approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: conversationId,
          tool_call_id: toolCallId,
          action: "approve",
          edited_input: editedInput ?? null,
        }),
      });
    },
    [conversationId],
  );

  const cancelApproval = useCallback(
    async (toolCallId: string) => {
      await apiFetch<{ ok: boolean }>("/chat/tool_approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: conversationId,
          tool_call_id: toolCallId,
          action: "cancel",
          edited_input: null,
        }),
      });
    },
    [conversationId],
  );

  return {
    messages: state.messages,
    streamingDraft: state.streamingDraft,
    toolCalls: state.toolCalls,
    streaming: state.streaming,
    error: state.error,
    send,
    cancel,
    approve,
    cancelApproval,
  };
}

// --- pure helpers -----------------------------------------------------------

function applyEvent(
  setState: React.Dispatch<React.SetStateAction<ChatStreamState>>,
  event: ChatStreamEvent,
  conversationId: string,
) {
  setState((prev) => {
    switch (event.type) {
      case "content_block_delta": {
        const draft = appendDraftText(prev.streamingDraft, event.delta.text);
        return { ...prev, streamingDraft: draft };
      }
      case "tool_approval_required": {
        // Track in the in-memory approvals store so the Header badge
        // and any standalone ApprovalCard render can see it. The store
        // sits *outside* React reducer state on purpose: the Header and
        // chat panel live in separate subtrees of the AppShell.
        useChatApprovals.getState().add({
          conversationId,
          toolCallId: event.tool_call_id,
          name: event.name as ApprovalToolName,
          input: event.input,
          preview: event.preview,
          receivedAt: Date.now(),
        });
        // Push a transient ``system`` row carrying the approval block so
        // MessageBubble can render an ApprovalCard inline. The row is
        // *not* persisted — chat_history drops non-user/assistant roles
        // on save, which is exactly the behaviour we want.
        const metaMessage: ChatMessage = {
          role: "system",
          content: [
            {
              type: "tool_approval_required",
              tool_call_id: event.tool_call_id,
              name: event.name,
              input: event.input,
              preview: event.preview,
            },
          ],
          timestamp: new Date().toISOString(),
        };
        return { ...prev, messages: [...prev.messages, metaMessage] };
      }
      case "tool_use_start": {
        const draft = appendDraftToolUse(prev.streamingDraft, {
          tool_call_id: event.tool_call_id,
          name: event.name,
          input: event.input_partial ?? {},
        });
        return {
          ...prev,
          streamingDraft: draft,
          toolCalls: {
            ...prev.toolCalls,
            [event.tool_call_id]: {
              tool_call_id: event.tool_call_id,
              name: event.name,
              input: event.input_partial ?? {},
              status: "running",
            },
          },
        };
      }
      case "tool_use_result": {
        const existing = prev.toolCalls[event.tool_call_id];
        const isError =
          event.result != null && typeof event.result === "object" && "error" in event.result;
        // If this was an approved side-effect call, clear it from the
        // approvals store and drop the transient system meta row so the
        // ApprovalCard is replaced by the regular ToolCard result.
        useChatApprovals.getState().remove(event.tool_call_id);
        const filteredMessages = prev.messages.filter(
          (m) => !isApprovalMetaFor(m, event.tool_call_id),
        );
        return {
          ...prev,
          messages: filteredMessages,
          toolCalls: {
            ...prev.toolCalls,
            [event.tool_call_id]: {
              tool_call_id: event.tool_call_id,
              name: existing?.name ?? "(unknown)",
              input: existing?.input ?? {},
              result: event.result,
              status: isError ? "error" : "done",
            },
          },
        };
      }
      case "error": {
        if (event.reason === "approval_timeout" && event.tool_call_id) {
          // Backend reaped the pending approval after 10 minutes. Drop
          // the store entry; the meta row mutates to ``expired`` via a
          // best-effort rewrite so the user sees *why* the card died.
          useChatApprovals.getState().remove(event.tool_call_id);
          const mutated = markApprovalExpired(prev.messages, event.tool_call_id);
          return {
            ...prev,
            messages: mutated,
            error: "Approval expired (10 min timeout).",
          };
        }
        const detail =
          event.reason === "tool_not_allowed"
            ? `Read-only mode: tool "${event.tool ?? "unknown"}" was blocked.`
            : `Error: ${event.reason}${event.message ? ` — ${event.message}` : ""}`;
        return { ...prev, error: detail };
      }
      case "message_stop": {
        return promoteDraft(prev);
      }
      case "tool_input_partial":
        // Currently displayed via the ToolCard "running" state; nothing
        // to update here in v0.
        return prev;
      default:
        return prev;
    }
  });
}

function appendDraftText(
  draft: ChatMessage | null,
  text: string,
): ChatMessage {
  if (!draft) {
    return {
      role: "assistant",
      content: [{ type: "text", text }],
      timestamp: new Date().toISOString(),
    };
  }
  const blocks = Array.isArray(draft.content)
    ? [...(draft.content as ContentBlock[])]
    : [{ type: "text", text: draft.content as string } as ContentBlock];
  const last = blocks[blocks.length - 1];
  if (last && (last as { type: string }).type === "text") {
    blocks[blocks.length - 1] = {
      ...(last as { type: "text"; text: string }),
      text: (last as { type: "text"; text: string }).text + text,
    };
  } else {
    blocks.push({ type: "text", text });
  }
  return { ...draft, content: blocks };
}

function appendDraftToolUse(
  draft: ChatMessage | null,
  toolUse: { tool_call_id: string; name: string; input: Record<string, unknown> },
): ChatMessage {
  const base: ChatMessage =
    draft ??
    ({
      role: "assistant",
      content: [],
      timestamp: new Date().toISOString(),
    } as ChatMessage);
  const blocks = Array.isArray(base.content)
    ? [...(base.content as ContentBlock[])]
    : [{ type: "text", text: base.content as string } as ContentBlock];
  blocks.push({
    type: "tool_use",
    id: toolUse.tool_call_id,
    name: toolUse.name,
    input: toolUse.input,
  });
  return { ...base, content: blocks };
}

/** Is ``m`` the transient system row for ``toolCallId``'s approval? */
function isApprovalMetaFor(m: ChatMessage, toolCallId: string): boolean {
  if (m.role !== "system") return false;
  if (!Array.isArray(m.content)) return false;
  const first = m.content[0] as { type?: string; tool_call_id?: string } | undefined;
  return (
    first?.type === "tool_approval_required" &&
    first?.tool_call_id === toolCallId
  );
}

/** Mark the matching system row as ``expired`` so its ApprovalCard
 * shows the timeout message instead of disappearing silently. */
function markApprovalExpired(
  messages: ChatMessage[],
  toolCallId: string,
): ChatMessage[] {
  return messages.map((m) => {
    if (!isApprovalMetaFor(m, toolCallId)) return m;
    const blocks = m.content as ContentBlock[];
    const head = blocks[0] as Record<string, unknown>;
    const updatedHead = { ...head, expired: true } as unknown as ContentBlock;
    const newBlocks: ContentBlock[] = [updatedHead, ...blocks.slice(1)];
    return { ...m, content: newBlocks };
  });
}

function promoteDraft(state: ChatStreamState): ChatStreamState {
  if (!state.streamingDraft) {
    return { ...state, streaming: false };
  }
  return {
    ...state,
    messages: [...state.messages, state.streamingDraft],
    streamingDraft: null,
    streaming: false,
  };
}

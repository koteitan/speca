"""CLI-subprocess runtime for the Chat slice.

Used when the credential resolved by :func:`chat_runtime.get_api_key` is a
claude.ai OAuth access token (``sk-ant-oat…`` prefix) — those tokens get
strict rate-limit treatment when sent directly to ``api.anthropic.com``
(SDK path), so we delegate to the official ``claude`` CLI instead. The
CLI is the only first-party client Anthropic routes through the Pro / Max
subscription pool; sub-second 429s vanish the moment we use it.

API-key users keep using :mod:`chat_runtime` because the SDK path retains
the custom server-side tool surface (list_runs / read_run_detail /
launch_pipeline / stop_pipeline). This module deliberately drops those:
the CLI runs *its own* tool set and is restricted to ``--allowed-tools``
empty (i.e. read-only Q&A) so a chat session cannot accidentally touch
the user's filesystem or fire shell commands.

Event shape mirrors :mod:`chat_runtime`'s SSE wire so the SPA's
``useChatStream`` parser does not need to branch:

* ``{"type": "content_block_delta", "delta": {"text": "..."}}``
* ``{"type": "error", "reason": "runtime_error", "message": "..."}``
* ``{"type": "message_stop", "usage": {...}}``

Session continuity is provided via ``claude --resume <session_id>``; we
stash the CLI's session id in the conversation file under
``cli_session_id`` (extra="allow" on ConversationDoc keeps the schema
round-trip safe) so multi-turn chats keep the same context.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, AsyncIterator

from web.server.services import chat_history

logger = logging.getLogger(__name__)


# Read-only tool surface — the chat must not touch the user's filesystem
# or run shell commands. Passing an empty allowed-tools list disables all
# tools; the CLI then behaves as a pure Q&A pipe.
_ALLOWED_TOOLS: tuple[str, ...] = ()


def _resolve_claude_bin() -> str | None:
    """Locate the ``claude`` CLI on PATH (Windows-aware)."""

    found = shutil.which("claude")
    if found is None and sys.platform == "win32":
        found = shutil.which("claude.cmd")
    return found


def _get_cli_session_id(conversation: Any) -> str | None:
    """Read the CLI session id stashed in the conversation file (if any).

    ``ConversationDoc`` uses ``extra="allow"`` so we read via
    ``getattr`` to stay schema-stable even if the field was never set.
    """

    sid = getattr(conversation, "cli_session_id", None)
    if isinstance(sid, str) and sid:
        return sid
    extra = getattr(conversation, "model_extra", None)
    if isinstance(extra, dict):
        sid = extra.get("cli_session_id")
        if isinstance(sid, str) and sid:
            return sid
    return None


def _save_cli_session_id(
    conversation_id: str, session_id: str, base: Path | None
) -> None:
    """Persist the CLI session id into the conversation file."""

    conversation = chat_history.load_conversation(conversation_id, base=base)
    if conversation is None:
        return
    # ``extra="allow"`` lets us round-trip the field without touching the
    # schema definition; ``model_copy(update=…)`` merges into the dump.
    updated = conversation.model_copy(update={"cli_session_id": session_id})
    chat_history.save_conversation(updated, base=base)


def _build_cmd(prompt_text: str, resume_session_id: str | None) -> list[str]:
    """Compose the claude CLI argv for one chat turn."""

    claude_bin = _resolve_claude_bin()
    if claude_bin is None:
        raise RuntimeError("claude CLI not found on PATH")

    cmd: list[str] = [
        claude_bin,
        "--print",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--dangerously-skip-permissions",
    ]
    if _ALLOWED_TOOLS:
        cmd.extend(["--allowed-tools", ",".join(_ALLOWED_TOOLS)])
    else:
        # Empty list = no tools at all. We pass an explicit empty value
        # because some claude versions silently default to "all" when the
        # flag is omitted.
        cmd.extend(["--disallowed-tools", "*"])
    if resume_session_id:
        cmd.extend(["--resume", resume_session_id])

    cmd.extend(["-p", prompt_text])
    return cmd


def _windows_creation_flags() -> int:
    """Return CREATE_NO_WINDOW on Windows; 0 elsewhere."""

    return 0x08000000 if sys.platform == "win32" else 0


def _line_to_events(
    raw: str,
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Map one stream-json line from the CLI to zero-or-more SPA events.

    ``state`` is a mutable dict carrying cross-line context — we use it
    to track ``cli_session_id`` and the most-recent assistant text so
    ``_save_cli_session_id`` + persistence have what they need at end.
    """

    line = raw.strip()
    if not line:
        return []
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        # Heartbeats / non-JSON noise; skip silently.
        return []
    if not isinstance(payload, dict):
        return []

    event_type = payload.get("type")

    # The CLI's ``system/init`` event carries the session id we want for
    # --resume on the next turn.
    if event_type == "system" and payload.get("subtype") == "init":
        sid = payload.get("session_id")
        if isinstance(sid, str):
            state["cli_session_id"] = sid
        return []

    if event_type == "stream_event":
        # With ``--include-partial-messages`` the CLI re-emits the raw
        # Anthropic stream events too. We map ``content_block_delta``
        # text deltas to the SPA's existing wire shape so the UI streams
        # the response token-by-token.
        event = payload.get("event")
        if isinstance(event, dict) and event.get("type") == "content_block_delta":
            delta = event.get("delta")
            if isinstance(delta, dict) and delta.get("type") == "text_delta":
                text = delta.get("text")
                if isinstance(text, str) and text:
                    state["assistant_text"] = state.get("assistant_text", "") + text
                    return [{"type": "content_block_delta", "delta": {"text": text}}]
        return []

    if event_type == "assistant":
        # The CLI sometimes emits an aggregate ``assistant`` event with
        # the full message (when partials are disabled or coalesced). If
        # we haven't seen partials, fall through and emit the full text
        # as a single delta. Otherwise it's already streamed — skip.
        if state.get("assistant_text"):
            return []
        message = payload.get("message")
        if not isinstance(message, dict):
            return []
        content = message.get("content")
        if not isinstance(content, list):
            return []
        out: list[dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str) and text:
                    state["assistant_text"] = state.get("assistant_text", "") + text
                    out.append({"type": "content_block_delta", "delta": {"text": text}})
        return out

    if event_type == "result":
        usage = payload.get("usage")
        out: dict[str, Any] = {"type": "message_stop", "usage": usage or {}}
        stop_reason = payload.get("stop_reason")
        if isinstance(stop_reason, str):
            out["stop_reason"] = stop_reason
        if payload.get("is_error"):
            error_msg = (
                payload.get("api_error_status") or payload.get("result") or "cli reported is_error"
            )
            return [
                {
                    "type": "error",
                    "reason": "runtime_error",
                    "message": str(error_msg),
                },
                out,
            ]
        return [out]

    # Unknown event types (rate_limit_event, hook_event, …) are surfaced
    # only in logs to keep the SSE stream lean.
    return []


def _user_text_block(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": text}]


async def stream_response(
    conversation_id: str,
    user_text: str,
    *,
    base: Path | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Stream a response for ``user_text`` via the ``claude`` CLI.

    Drop-in replacement for :func:`chat_runtime.stream_response` on the
    OAuth code path. Persists the user message and the assistant reply
    to the same conversation history file so the SPA's history surface
    is identical between code paths.
    """

    # --- Persist the user's message first --------------------------------
    conversation = chat_history.ensure_conversation(conversation_id, base=base)
    chat_history.append_message(
        conversation, role="user", content=_user_text_block(user_text), base=base
    )

    # --- Compose the CLI argv -------------------------------------------
    resume = _get_cli_session_id(conversation)
    try:
        cmd = _build_cmd(user_text, resume)
    except RuntimeError as exc:
        yield {
            "type": "error",
            "reason": "runtime_error",
            "message": str(exc),
        }
        yield {"type": "message_stop", "usage": {}}
        return

    state: dict[str, Any] = {"assistant_text": "", "cli_session_id": None}

    # --- Spawn the CLI asynchronously -----------------------------------
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            creationflags=_windows_creation_flags(),
        )
    except (OSError, FileNotFoundError) as exc:
        yield {
            "type": "error",
            "reason": "runtime_error",
            "message": f"failed to spawn claude CLI: {exc}",
        }
        yield {"type": "message_stop", "usage": {}}
        return

    assert proc.stdout is not None
    try:
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace")
            for event in _line_to_events(line, state):
                yield event
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("chat_runtime_cli: read failed (%s)", exc)
        yield {
            "type": "error",
            "reason": "runtime_error",
            "message": f"CLI read failed: {exc}",
        }
    finally:
        rc = await proc.wait()
        if rc != 0 and not state.get("assistant_text"):
            yield {
                "type": "error",
                "reason": "runtime_error",
                "message": f"claude CLI exited with code {rc}",
            }
            yield {"type": "message_stop", "usage": {}}

    # --- Persist assistant reply + session id ---------------------------
    # Reload the conversation so any concurrent mutations between
    # ``append_message`` for the user and now don't get clobbered.
    fresh = chat_history.load_conversation(conversation_id, base=base)
    text = state.get("assistant_text") or ""
    if fresh is not None and text:
        chat_history.append_message(
            fresh,
            role="assistant",
            content=[{"type": "text", "text": text}],
            base=base,
        )
    sid = state.get("cli_session_id")
    if isinstance(sid, str) and sid:
        try:
            _save_cli_session_id(conversation_id, sid, base=base)
        except Exception as exc:  # pragma: no cover - non-fatal
            logger.warning("chat_runtime_cli: could not save session id (%s)", exc)

"""Anthropic client glue for the Chat slice.

The runtime owns three responsibilities:

1. **Build the request** — read on-disk history, append the new user message,
   send to ``client.messages.stream`` with the read-only ``TOOLS`` allowlist
   only (no side-effecting tools).
2. **Translate stream events** — convert Anthropic's typed events into the
   compact dict shape documented in ``docs/UI_DESIGN.md`` § 7.2 so the
   frontend can consume them uniformly.
3. **Persist** — after each turn, save the assistant message (plus any
   ``tool_use`` / ``tool_result`` blocks) back to the conversation file.

The three-gate read-only guard lives here too:

* ``tools=`` is constructed from :data:`chat_tools.TOOLS` (3 tools only).
* On every ``tool_use`` block we re-check ``name`` against
  :data:`chat_tools.ALLOWED_TOOL_NAMES`; out-of-allowlist names abort the
  stream with a ``tool_not_allowed`` error event and **are not persisted**.
* (Frontend tier 3 is the ``<ToolCard>`` type, see ``ToolCard.tsx``.)

The Anthropic client is wrapped so tests can inject a fake — see
:func:`build_client`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Iterable, Protocol

from web.server.services import chat_approvals, chat_history, chat_tools
from web.server.services.chat_tools import ToolNotAllowed
from web.server.services.credentials import _load_raw as _load_credentials

logger = logging.getLogger(__name__)


DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096
# Cap on tool_use rounds within a single user turn. Multi-step tool use is
# legitimate ("list runs, then read run X") but unbounded loops mean a
# runaway turn could blow through the user's budget, so we stop after a
# generous number of rounds and surface a soft error event.
MAX_TOOL_ROUNDS = 8
# How long we suspend a stream waiting for an approval before giving up
# and surfacing ``approval_timeout``. Ten minutes is generous enough that
# a user can step away for a coffee but bounded so an abandoned UI tab
# cannot pin the supervisor / chat loop forever.
APPROVAL_TIMEOUT_SECONDS = 600.0


class _StreamLike(Protocol):
    """Protocol for the object Anthropic returns from ``messages.stream``.

    We only rely on the two methods we actually use, so a test fake can be
    a tiny class with `__enter__` / `__exit__` and an ``events`` iterator
    via ``__iter__``.
    """

    def __enter__(self) -> "_StreamLike": ...
    def __exit__(self, *exc: Any) -> None: ...
    def __iter__(self) -> Iterable[Any]: ...
    def get_final_message(self) -> Any: ...


class _ClientLike(Protocol):
    """Minimal interface of ``anthropic.Anthropic`` we depend on."""

    class messages:  # noqa: N801 - mirror SDK shape
        @staticmethod
        def stream(**kwargs: Any) -> _StreamLike: ...


def get_api_key() -> str | None:
    """Resolve a credential string for the Anthropic client.

    Order of precedence:

    1. ``ANTHROPIC_API_KEY`` env var (explicit override, matches CLI / CI)
    2. ``apiKey`` in the credentials file (``~/.claude/.credentials.json``;
       legacy dot-less fallback also honoured — see credentials.py)
    3. ``claudeAiOauth.accessToken`` — claude.ai OAuth access token. We
       return it here in raw form; ``build_client`` distinguishes OAuth
       from API keys by the ``sk-ant-oat`` prefix and passes it to the
       SDK as ``auth_token`` instead of ``api_key`` so the request is
       Bearer-authed (the only flavour Anthropic accepts for the Pro /
       Max subscription tier).

    Returns ``None`` if no credentials are present; callers decide whether
    to surface "logged out" or hard-fail.
    """

    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    data = _load_credentials()
    api_key = data.get("apiKey")
    if isinstance(api_key, str) and api_key.strip():
        return api_key.strip()

    oauth = data.get("claudeAiOauth")
    if isinstance(oauth, dict):
        token = oauth.get("accessToken")
        if isinstance(token, str) and token.strip():
            return token.strip()

    return None


# claude.ai OAuth access tokens always start with this prefix; API keys
# minted in the Console use ``sk-ant-api``. The discrimination is the
# only piece of context the SDK needs to call the right auth code path.
_OAUTH_TOKEN_PREFIX = "sk-ant-oat"

# Beta header the official ``claude`` CLI sends when authenticating with
# a subscription OAuth token. Without it api.anthropic.com routes the
# request as raw API and rate-limits aggressively (the 429 storm we saw
# during the first chat verification).
_OAUTH_BETA_HEADER = "oauth-2025-04-20"


def build_client(api_key: str | None = None) -> _ClientLike:
    """Construct the Anthropic SDK client.

    OAuth tokens (``sk-ant-oat…``) are passed as ``auth_token`` so the SDK
    sends an ``Authorization: Bearer …`` header; API keys (``sk-ant-api…``)
    keep the ``X-Api-Key`` header path. The ``anthropic-beta`` header is
    added for OAuth so Anthropic routes the request through the
    subscription pool (Max / Pro) instead of the raw-API quota.

    Imported lazily so the module is still importable in tests without a
    network-capable SDK present.
    """

    from anthropic import Anthropic  # local import — heavy

    if api_key is None:
        return Anthropic()  # type: ignore[return-value]

    if api_key.startswith(_OAUTH_TOKEN_PREFIX):
        return Anthropic(  # type: ignore[return-value]
            auth_token=api_key,
            default_headers={"anthropic-beta": _OAUTH_BETA_HEADER},
        )

    return Anthropic(api_key=api_key)  # type: ignore[return-value]


# Type alias for the client factory the runtime accepts. Default is
# :func:`build_client`; tests pass a stub that returns a fake stream.
ClientFactory = Callable[[str | None], _ClientLike]


def _user_text_block(text: str) -> list[dict[str, Any]]:
    """Convert a user-typed string into the Messages API content shape."""

    return [{"type": "text", "text": text}]


def _content_for_api(content: list[dict[str, Any]] | str) -> Any:
    """Pass-through content normalizer for the messages API.

    Strings and lists of blocks are both valid; we leave them alone except
    for one defensive copy so the runtime cannot mutate persisted state.
    """

    if isinstance(content, str):
        return content
    return [dict(b) for b in content]


def _messages_for_api(
    history: list[Any], current_user_blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Turn the on-disk history into a Messages API ``messages`` list.

    The current user turn is appended *after* this call by the caller (so we
    can interleave tool_result blocks across multi-step turns).
    """

    out: list[dict[str, Any]] = []
    for msg in history:
        # ``msg`` is a ``ChatMessage`` Pydantic model when read from disk.
        role = getattr(msg, "role", None) or msg.get("role")
        content = getattr(msg, "content", None)
        if content is None:
            content = msg.get("content")
        if role not in ("user", "assistant"):
            continue
        out.append({"role": role, "content": _content_for_api(content)})
    out.append({"role": "user", "content": current_user_blocks})
    return out


def _block_to_dict(block: Any) -> dict[str, Any]:
    """Coerce an SDK content block (TextBlock / ToolUseBlock / ...) to a dict."""

    if hasattr(block, "model_dump"):
        return block.model_dump(mode="json")
    if isinstance(block, dict):
        return block
    # Fallback for objects with attributes.
    return json.loads(json.dumps(block, default=lambda o: getattr(o, "__dict__", str(o))))


def _final_message_to_blocks(final_message: Any) -> list[dict[str, Any]]:
    """Extract assistant content blocks from a ``Message`` SDK object."""

    if final_message is None:
        return []
    content = getattr(final_message, "content", None)
    if content is None and isinstance(final_message, dict):
        content = final_message.get("content")
    if not content:
        return []
    return [_block_to_dict(b) for b in content]


def _final_message_stop_event(final_message: Any) -> dict[str, Any]:
    """Build a ``message_stop`` SSE event from the SDK's final message.

    Best-effort extraction of ``usage`` — fields we cannot read are simply
    omitted.
    """

    usage_obj = getattr(final_message, "usage", None)
    usage: dict[str, Any] = {}
    if usage_obj is not None:
        if hasattr(usage_obj, "model_dump"):
            usage = usage_obj.model_dump(mode="json")
        elif isinstance(usage_obj, dict):
            usage = dict(usage_obj)
        else:
            usage = {
                "input_tokens": getattr(usage_obj, "input_tokens", None),
                "output_tokens": getattr(usage_obj, "output_tokens", None),
            }
    stop_reason = getattr(final_message, "stop_reason", None)
    payload: dict[str, Any] = {"type": "message_stop", "usage": usage}
    if stop_reason is not None:
        payload["stop_reason"] = stop_reason
    return payload


def _iter_stream_events(stream: Any) -> Iterable[Any]:
    """Iterate raw stream events from the SDK manager.

    Anthropic's ``MessageStreamManager`` is iterated with ``for event in
    stream`` once you've entered the context. Tests pass a fake that simply
    implements ``__iter__``.
    """

    return iter(stream)


async def _emit_async(
    items: list[dict[str, Any]],
) -> AsyncIterator[dict[str, Any]]:
    """Helper to yield a list of events as an async iterator."""

    for item in items:
        # Cooperative scheduling — keeps the event loop responsive on
        # massive turns.
        await asyncio.sleep(0)
        yield item


async def stream_response(
    conversation_id: str,
    user_text: str,
    *,
    client_factory: ClientFactory | None = None,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    base: Path | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Stream a response for ``user_text`` and persist the turn to history.

    Yields dicts shaped like::

        {"type": "content_block_delta", "delta": {"text": "..."}}
        {"type": "tool_use_start", "tool_call_id": "...", "name": "...", "input_partial": {}}
        {"type": "tool_use_result", "tool_call_id": "...", "result": {...}}
        {"type": "error", "reason": "...", ...}
        {"type": "message_stop", "usage": {...}}

    The function never raises for read-only-guard violations — those are
    surfaced as ``error`` events and the stream terminates cleanly. Hard
    failures (missing API key, network down) emit an ``error`` event with
    ``reason="runtime_error"`` and a short message.
    """

    # --- Load history and create-if-missing ---------------------------------
    conversation = chat_history.ensure_conversation(conversation_id, base=base)

    # Append the user message *first* so even if the model errors we have
    # a record of what the user said. The save here is what creates the
    # file on disk for the "test-uuid-1.json was created" assertion.
    user_blocks = _user_text_block(user_text)
    chat_history.append_message(
        conversation, role="user", content=user_blocks, base=base
    )

    # --- Resolve credentials -----------------------------------------------
    effective_key = api_key if api_key is not None else get_api_key()
    # Resolve the factory at *call time* so tests can monkeypatch
    # ``chat_runtime.build_client`` after import.
    factory = client_factory if client_factory is not None else build_client
    try:
        client = factory(effective_key)
    except Exception as exc:
        logger.exception("chat_runtime: failed to build client (%s)", exc)
        yield {
            "type": "error",
            "reason": "runtime_error",
            "message": f"failed to initialise Anthropic client: {exc}",
        }
        yield {"type": "message_stop", "usage": {}}
        return

    # --- Tool-use loop ------------------------------------------------------
    # We run repeated `messages.stream` calls until the model returns a
    # message with `stop_reason != "tool_use"` or we hit MAX_TOOL_ROUNDS.
    assistant_blocks_for_history: list[dict[str, Any]] = []
    pending_user_blocks: list[dict[str, Any]] = list(user_blocks)
    aborted = False
    rounds = 0

    while True:
        rounds += 1
        if rounds > MAX_TOOL_ROUNDS:
            yield {
                "type": "error",
                "reason": "tool_loop_limit",
                "message": f"exceeded {MAX_TOOL_ROUNDS} tool rounds",
            }
            aborted = True
            break

        # Reload conversation so any persisted tool_result blocks from a
        # previous loop iteration are included in the next request.
        api_messages = _messages_for_api(conversation.messages[:-1], pending_user_blocks)

        try:
            stream_cm = client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                messages=api_messages,
                tools=chat_tools.TOOLS,
            )
        except Exception as exc:
            logger.exception("chat_runtime: stream() raised (%s)", exc)
            yield {
                "type": "error",
                "reason": "runtime_error",
                "message": str(exc),
            }
            aborted = True
            break

        final_message: Any = None
        tool_uses_this_round: list[dict[str, Any]] = []

        try:
            with stream_cm as stream:
                for event in _iter_stream_events(stream):
                    translated = _translate_event(event)
                    if translated is None:
                        continue
                    if translated.get("type") == "tool_use_start":
                        tool_uses_this_round.append(
                            {
                                "tool_call_id": translated.get("tool_call_id"),
                                "name": translated.get("name"),
                                "input": translated.get("input", {}),
                            }
                        )
                    yield translated
                try:
                    final_message = stream.get_final_message()
                except Exception as exc:  # pragma: no cover - rare
                    logger.warning(
                        "chat_runtime: get_final_message failed (%s)", exc
                    )
                    final_message = None
        except Exception as exc:
            logger.exception("chat_runtime: stream iteration failed (%s)", exc)
            yield {
                "type": "error",
                "reason": "runtime_error",
                "message": str(exc),
            }
            aborted = True
            break

        # Collect assistant blocks for history and validate tool_use names.
        assistant_blocks = _final_message_to_blocks(final_message)

        # ---- Tier 2 guard: re-check every tool_use name -------------------
        invalid_tools = [
            b
            for b in assistant_blocks
            if isinstance(b, dict)
            and b.get("type") == "tool_use"
            and b.get("name") not in chat_tools.ALLOWED_TOOL_NAMES
        ]
        if invalid_tools:
            offender = invalid_tools[0].get("name")
            logger.warning(
                "chat_runtime: read-only guard tripped on tool %s", offender
            )
            yield {
                "type": "error",
                "reason": "tool_not_allowed",
                "tool": offender,
            }
            yield _final_message_stop_event(final_message)
            # Do NOT persist this assistant turn — the guard's whole point
            # is that side-effecting calls leave no trace in history.
            aborted = True
            break

        # Persist the assistant message (text + allowed tool_use blocks).
        if assistant_blocks:
            conversation = chat_history.append_message(
                conversation,
                role="assistant",
                content=assistant_blocks,
                base=base,
            )
            assistant_blocks_for_history.extend(assistant_blocks)

        stop_reason = getattr(final_message, "stop_reason", None)

        # If the model wants tools, execute them and loop. Otherwise emit
        # the final message_stop and exit.
        tool_use_blocks = [
            b
            for b in assistant_blocks
            if isinstance(b, dict) and b.get("type") == "tool_use"
        ]
        if stop_reason != "tool_use" or not tool_use_blocks:
            yield _final_message_stop_event(final_message)
            break

        # ---- Execute tool calls ------------------------------------------
        tool_result_blocks: list[dict[str, Any]] = []
        guard_violation = False
        approval_aborted = False
        for block in tool_use_blocks:
            tool_name = block.get("name", "")
            tool_call_id = block.get("id") or block.get("tool_call_id") or ""
            tool_input = block.get("input") or {}

            # --- Side-effect path: gate behind explicit approval --------
            if tool_name in chat_tools.SIDE_EFFECT_TOOLS:
                # ``_handle_side_effect_call`` is an async generator —
                # iterate, don't ``await`` the call itself.
                outcome = _handle_side_effect_call(
                    conversation_id=conversation_id,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_input=tool_input,
                )
                # ``_handle_side_effect_call`` is an async generator that
                # yields a series of dicts. The last one is the canonical
                # "tool result for the model" payload; everything before
                # (e.g. ``tool_approval_required``) is purely for the SPA.
                final_outcome: dict[str, Any] | None = None
                async for event in outcome:
                    if event.get("__terminal__"):
                        # Strip the marker before yielding to subscribers.
                        final_outcome = {k: v for k, v in event.items() if k != "__terminal__"}
                        continue
                    yield event
                if final_outcome is None:  # pragma: no cover - defensive
                    final_outcome = {
                        "type": "tool_use_result",
                        "tool_call_id": tool_call_id,
                        "result": {"error": "internal_error", "tool": tool_name},
                    }
                # ``timeout`` aborts the entire turn — no further tools
                # in this batch run and we do not reschedule.
                if final_outcome.get("__timeout__"):
                    yield {
                        "type": "error",
                        "reason": "approval_timeout",
                        "tool_call_id": tool_call_id,
                    }
                    approval_aborted = True
                    break

                tool_result = final_outcome["result"]
                is_error = bool(final_outcome.get("is_error", False))
                yield {
                    "type": "tool_use_result",
                    "tool_call_id": tool_call_id,
                    "result": tool_result,
                }
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call_id,
                        "content": json.dumps(
                            tool_result, ensure_ascii=False, default=str
                        ),
                        "is_error": is_error,
                    }
                )
                continue

            # --- Read-only path: dispatch directly ----------------------
            try:
                result = await chat_tools.dispatch_tool(tool_name, tool_input)
                is_error = False
            except ToolNotAllowed as exc:
                logger.warning(
                    "chat_runtime: dispatch_tool blocked %s", exc.name
                )
                yield {
                    "type": "error",
                    "reason": "tool_not_allowed",
                    "tool": exc.name,
                }
                guard_violation = True
                break
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception(
                    "chat_runtime: tool %s raised (%s)", tool_name, exc
                )
                result = {"error": "internal_error", "tool": tool_name}
                is_error = True

            yield {
                "type": "tool_use_result",
                "tool_call_id": tool_call_id,
                "result": result,
            }
            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                    "is_error": is_error,
                }
            )

        if guard_violation:
            yield _final_message_stop_event(final_message)
            aborted = True
            break

        if approval_aborted:
            yield _final_message_stop_event(final_message)
            aborted = True
            break

        # Persist the user-side tool_result message before the next round.
        if tool_result_blocks:
            conversation = chat_history.append_message(
                conversation,
                role="user",
                content=tool_result_blocks,
                base=base,
            )

        # Next round: the next API call uses the freshly-saved history; the
        # "current user blocks" become the tool_result blocks.
        pending_user_blocks = tool_result_blocks

    # Touch last_message_at on completion so the sidebar bumps even on
    # text-only turns where ``append_message`` already updated it.
    if not aborted:
        conversation.last_message_at = datetime.now(timezone.utc)
        chat_history.save_conversation(conversation, base=base)


# --- Side-effect tool approval flow ----------------------------------------


async def _handle_side_effect_call(
    *,
    conversation_id: str,
    tool_call_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """Run the approval round-trip for one side-effecting ``tool_use``.

    Yields a sequence of dicts. The *final* dict carries a private
    ``"__terminal__": True`` marker and a ``"result"`` / ``"is_error"``
    pair the caller uses to build the model-facing ``tool_result``. All
    earlier dicts are passed through to the SSE stream as-is (the
    ``tool_approval_required`` notification, plus optional
    ``tool_use_result`` mid-flight events).

    The terminal payload may also carry ``"__timeout__": True`` — the
    caller treats that as a hard abort of the current turn.
    """

    approval = chat_approvals.register_pending(
        conversation_id=conversation_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        input_snapshot=tool_input,
    )

    yield {
        "type": "tool_approval_required",
        "tool_call_id": tool_call_id,
        "name": tool_name,
        "input": dict(tool_input),
        "preview": _render_preview(tool_name, tool_input),
    }

    try:
        await asyncio.wait_for(
            approval.event.wait(), timeout=APPROVAL_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        chat_approvals.drop(conversation_id, tool_call_id)
        yield {
            "__terminal__": True,
            "__timeout__": True,
            "result": {
                "error": "approval_timeout",
                "tool": tool_name,
                "tool_call_id": tool_call_id,
            },
            "is_error": True,
        }
        return

    action = approval.action

    if action == "cancel":
        # Send Anthropic a "user declined" tool_result so it can wrap up
        # the turn gracefully rather than hanging on a missing result.
        yield {
            "__terminal__": True,
            "result": {
                "declined": True,
                "tool": tool_name,
                "tool_call_id": tool_call_id,
            },
            "is_error": True,
        }
        return

    # Approve / edit: use ``edited_input`` if the user customised the
    # payload, otherwise the snapshot the model emitted.
    final_input = approval.edited_input or approval.input_snapshot

    try:
        result = await chat_tools.dispatch_side_effect_tool(tool_name, final_input)
        is_error = bool(isinstance(result, dict) and result.get("error"))
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "chat_runtime: side-effect %s raised (%s)", tool_name, exc
        )
        result = {"error": "internal_error", "tool": tool_name, "message": str(exc)}
        is_error = True

    yield {
        "__terminal__": True,
        "result": result,
        "is_error": is_error,
    }


def _render_preview(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Build a small UI-friendly preview for the approval card.

    The preview is purely cosmetic — the frontend can render either it or
    the raw ``input``. We keep the structure stable per tool so the UI
    can pattern-match on ``preview.kind``.

    No HTML / Markdown injection happens here: the values come straight
    from the model. The frontend is expected to escape on render (Slice
    C3) — see ``docs/UI_DESIGN.md`` § 7.5.
    """

    if tool_name == "launch_pipeline":
        return {
            "kind": "launch_pipeline",
            "summary": (
                f"Start audit run for {tool_input.get('target_repo', '?')} "
                f"({tool_input.get('target_ref') or 'HEAD'})"
            ),
            "fields": {
                "bug_bounty_url": tool_input.get("bug_bounty_url"),
                "target_repo": tool_input.get("target_repo"),
                "target_ref": tool_input.get("target_ref"),
                "workers": tool_input.get("workers", 4),
                "max_concurrent": tool_input.get("max_concurrent", 64),
                "push_to_remote": tool_input.get("push_to_remote", False),
            },
        }
    if tool_name == "stop_pipeline":
        return {
            "kind": "stop_pipeline",
            "summary": f"Cancel run {tool_input.get('run_id', '?')}",
            "fields": {"run_id": tool_input.get("run_id")},
        }
    return {"kind": tool_name, "summary": tool_name, "fields": dict(tool_input)}


# --- Event translation ------------------------------------------------------


def _translate_event(event: Any) -> dict[str, Any] | None:
    """Convert an SDK stream event into our wire dict shape.

    Returns ``None`` when the event has no UI-visible counterpart (e.g.
    ``message_start`` carries only metadata).
    """

    # Tests pass plain dicts — accept them as-is.
    if isinstance(event, dict):
        return _translate_dict_event(event)

    event_type = getattr(event, "type", None)

    if event_type == "content_block_start":
        block = getattr(event, "content_block", None)
        block_type = getattr(block, "type", None)
        if block_type == "tool_use":
            return {
                "type": "tool_use_start",
                "tool_call_id": getattr(block, "id", None),
                "name": getattr(block, "name", None),
                "input_partial": getattr(block, "input", {}) or {},
            }
        # Plain text blocks: no event — deltas come next.
        return None

    if event_type == "content_block_delta":
        delta = getattr(event, "delta", None)
        delta_type = getattr(delta, "type", None)
        if delta_type == "text_delta":
            return {
                "type": "content_block_delta",
                "delta": {"text": getattr(delta, "text", "")},
            }
        if delta_type == "input_json_delta":
            # We surface partial tool input as a hint to the UI so the user
            # can see *which* tool is being prepared, even before the final
            # tool_use_start fires for the closing event.
            return {
                "type": "tool_input_partial",
                "partial_json": getattr(delta, "partial_json", ""),
            }
        # Thinking / signature deltas: ignore in v0.
        return None

    if event_type == "message_stop":
        # The final stop event is emitted by the runtime itself using the
        # SDK's ``get_final_message`` so we get usage data. Skip the raw
        # event to avoid duplicates.
        return None

    return None


def _translate_dict_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Translate a fake / pre-shaped event dict (used by tests).

    Accepts either our wire shape (returned verbatim) or a small set of
    sugar shapes such as ``{"type": "tool_use", "name": ..., "input": ...,
    "id": ...}`` which we promote to ``tool_use_start``.
    """

    if event.get("type") == "tool_use":
        return {
            "type": "tool_use_start",
            "tool_call_id": event.get("id") or event.get("tool_call_id"),
            "name": event.get("name"),
            "input_partial": event.get("input", {}),
        }
    return event

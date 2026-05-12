"""Read-only guard for the Chat slice.

The chat surface is designed to be *strictly* read-only in v0: even if the
upstream model decides to emit a side-effecting tool_use (e.g. due to a
prompt-injection attack on conversation history, or a future SDK quirk),
the backend must:

1. Refuse to dispatch the call.
2. Surface an ``error`` event with ``reason="tool_not_allowed"``.
3. NOT persist the offending assistant turn to conversation history.

This module is the regression test for that contract. It does **not** hit
the Anthropic API — it injects a fake stream that the runtime drives just
like a real one.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Iterable

import pytest

from web.server.services import chat_history, chat_runtime, chat_tools


# --- Fake Anthropic SDK -----------------------------------------------------


class _FakeContent:
    """Stand-in for ``ToolUseBlock`` / ``TextBlock`` SDK objects."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        return dict(self.__dict__)


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


class _FakeMessage:
    def __init__(
        self,
        content: list[_FakeContent],
        *,
        stop_reason: str = "end_turn",
        usage: _FakeUsage | None = None,
    ) -> None:
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage or _FakeUsage(input_tokens=10, output_tokens=5)


class _FakeStream:
    def __init__(
        self,
        events: Iterable[Any],
        final_message: _FakeMessage,
    ) -> None:
        self._events = list(events)
        self._final = final_message

    def __enter__(self) -> "_FakeStream":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def __iter__(self):
        return iter(self._events)

    def get_final_message(self) -> _FakeMessage:
        return self._final


class _FakeMessages:
    def __init__(self, parent: "_FakeClient") -> None:
        self._parent = parent

    def stream(self, **kwargs: Any) -> _FakeStream:  # noqa: D401
        return self._parent._next_stream()


class _FakeClient:
    """Returns pre-canned stream responses in order."""

    def __init__(self, streams: list[_FakeStream]) -> None:
        self._streams = list(streams)
        self.messages = _FakeMessages(self)

    def _next_stream(self) -> _FakeStream:
        if not self._streams:
            raise AssertionError("FakeClient: no more streams queued")
        return self._streams.pop(0)


# --- Tests -------------------------------------------------------------------


async def _collect(stream: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    async for event in stream:
        out.append(event)
    return out


def test_allowed_tools_match_spec() -> None:
    """The allowlist contract.

    Updated in Slice C1 + C2: the allowlist now contains the three v0
    read-only tools plus the C1/C2 additions (``fetch_bounty_url`` and
    the two side-effect tools). The original invariants the v0 test was
    encoding still hold:

    * Every entry in ``TOOLS`` is in ``ALLOWED_TOOL_NAMES`` (no drift).
    * The three v0 read-only tools are still present.
    * Side-effect tools, when present, are **flagged** in
      :data:`SIDE_EFFECT_TOOLS` so the runtime knows to gate them. (The
      v0 test asserted they were *absent* — that invariant was relaxed in
      v1 in favour of an explicit approval gate.)
    """

    expected_readonly = {
        "read_run_status",
        "list_findings",
        "read_finding",
        "fetch_bounty_url",
    }
    expected_side_effects = {"launch_pipeline", "stop_pipeline"}
    expected_all = expected_readonly | expected_side_effects

    assert {t["name"] for t in chat_tools.TOOLS} == expected_all
    assert chat_tools.ALLOWED_TOOL_NAMES == frozenset(expected_all)
    assert chat_tools.SIDE_EFFECT_TOOLS == frozenset(expected_side_effects)
    # Every side-effect tool must also be in the global allowlist — the
    # runtime relies on that overlap when distinguishing "block at the
    # allowlist edge" from "route through approval gate".
    assert chat_tools.SIDE_EFFECT_TOOLS <= chat_tools.ALLOWED_TOOL_NAMES


def test_dispatch_rejects_unknown_tool() -> None:
    """Dispatch must raise :class:`ToolNotAllowed` for unknown names.

    ``launch_pipeline`` is no longer unknown (it is in the allowlist) but
    it is now refused via ``RuntimeError`` if dispatched directly,
    because the runtime is expected to route it through the approval
    gate instead. We assert *some* exception is raised here, asserting
    on type for the truly-unknown case.
    """

    with pytest.raises(chat_tools.ToolNotAllowed):
        asyncio.run(chat_tools.dispatch_tool("erase_all_runs", {}))

    # Side-effect tools must NOT be dispatchable via dispatch_tool —
    # the runtime is expected to go through dispatch_side_effect_tool
    # after an approval round-trip instead.
    with pytest.raises(RuntimeError):
        asyncio.run(chat_tools.dispatch_tool("launch_pipeline", {}))


def test_readonly_guard_blocks_forced_side_effect(tmp_path: Path) -> None:
    """End-to-end: a forged ``tool_use`` for an unknown tool is blocked.

    We simulate a malicious / buggy SDK that emits a ``tool_use`` block
    for a name *not* on the allowlist. The runtime must:

    * Yield an ``error`` event with ``reason="tool_not_allowed"``.
    * NOT add the assistant turn to conversation history.
    * Still emit a terminal ``message_stop`` so SSE clients can clean up.

    Slice C1 + C2 note: ``launch_pipeline`` is now on the allowlist (it
    gates behind an explicit approval), so the canonical "evil" tool
    name in this test is something *no* slice declares.
    """

    conversation_id = "test-readonly-guard"
    base = tmp_path

    # Craft a fake assistant turn that includes a forbidden tool_use.
    bad_block = _FakeContent(
        type="tool_use",
        id="tu_evil",
        name="erase_all_runs",
        input={"confirm": True},
    )
    text_block = _FakeContent(type="text", text="I will erase everything.")

    final = _FakeMessage(
        content=[text_block, bad_block],
        stop_reason="tool_use",
    )
    # Pre-shape events: a text delta and a tool_use_start dict.
    events = [
        {"type": "content_block_delta", "delta": {"text": "I will erase everything."}},
        {
            "type": "tool_use",
            "id": "tu_evil",
            "name": "erase_all_runs",
            "input": {"confirm": True},
        },
    ]
    fake_stream = _FakeStream(events=events, final_message=final)
    client = _FakeClient(streams=[fake_stream])

    async def run() -> list[dict[str, Any]]:
        stream = chat_runtime.stream_response(
            conversation_id=conversation_id,
            user_text="please launch a pipeline",
            client_factory=lambda _key: client,
            api_key="dummy-key-not-used",
            base=base,
        )
        return await _collect(stream)

    events_out = asyncio.run(run())

    # --- Assertion 1: an error event was emitted. -------------------------
    error_events = [e for e in events_out if e.get("type") == "error"]
    assert error_events, f"expected an error event, got: {events_out}"
    assert error_events[0]["reason"] == "tool_not_allowed"
    assert error_events[0]["tool"] == "erase_all_runs"

    # --- Assertion 2: history has user turn only, NO assistant turn. -----
    convo = chat_history.load_conversation(conversation_id, base=base)
    assert convo is not None
    roles = [m.role for m in convo.messages]
    assert "user" in roles, "user turn must always be recorded"
    assert "assistant" not in roles, (
        "forbidden tool_use must NOT be persisted as an assistant turn; "
        f"actual roles: {roles}"
    )

    # --- Assertion 3: a terminal message_stop was emitted. ---------------
    stop_events = [e for e in events_out if e.get("type") == "message_stop"]
    assert stop_events, "stream must terminate with a message_stop event"


def test_allowed_tool_dispatch_passes_through_to_service(tmp_path: Path) -> None:
    """Sanity check: allowed tools that have services succeed.

    The service may be missing (Slice B/C still in flight) — in that case
    we accept either a normal result or a ``service_not_ready`` envelope.
    The key invariant is that ``ToolNotAllowed`` is **not** raised.
    """

    result = asyncio.run(chat_tools.dispatch_tool("read_run_status", {"run_id": "nope"}))
    assert isinstance(result, dict)
    # Either the service returned a not_found / detail dict, or signalled it
    # isn't wired up yet — both are valid intermediate states for v0.
    assert "error" in result or "run_id" in result or "status" in result

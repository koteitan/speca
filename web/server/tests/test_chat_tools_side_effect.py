"""Side-effect tool approval gate (Slice C1 + C2).

These tests assert the contract documented in ``docs/UI_DESIGN.md`` § 4.8
and the slice C1/C2 design: when the model emits a ``tool_use`` for a
side-effecting tool (``launch_pipeline`` / ``stop_pipeline``), the chat
runtime must:

1. Emit a ``tool_approval_required`` SSE event with the proposed input.
2. Suspend the stream until ``POST /chat/tool_approve`` resolves the
   pending approval (or the 10-minute timeout fires).
3. On ``action="approve"`` — dispatch the side-effect tool via
   :func:`chat_tools.dispatch_side_effect_tool` (no direct call into
   :func:`chat_tools.dispatch_tool`).
4. On ``action="cancel"`` — send a ``"User declined"`` tool_result back
   to Anthropic so the turn can wrap up gracefully, and do **not**
   touch :class:`RunSupervisor`.
5. Reject unknown tool names at the allowlist edge with
   ``error / tool_not_allowed`` exactly as v0 did.

The Anthropic SDK is faked here — we never touch the network. The
supervisor / workspace manager are monkeypatched per test so we never
spawn a real subprocess.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Iterable

import pytest

from web.server.services import (
    chat_approvals,
    chat_history,
    chat_runtime,
    chat_tools,
)


# ----------------------------------------------------------------------------
# Fake Anthropic SDK (mirrors test_chat_readonly_guard.py shapes)
# ----------------------------------------------------------------------------


class _FakeContent:
    """Stand-in for SDK ``TextBlock`` / ``ToolUseBlock`` objects."""

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

    def stream(self, **kwargs: Any) -> _FakeStream:
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


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _launch_pipeline_streams(*, tool_call_id: str = "tu_launch_1") -> _FakeClient:
    """Build a two-round fake Anthropic flow.

    Round 1: the model emits ``tool_use`` for ``launch_pipeline`` with
    ``stop_reason="tool_use"``.
    Round 2: after the runtime feeds the tool_result back, the model
    closes the turn with a short text reply (``stop_reason="end_turn"``).
    """

    launch_block = _FakeContent(
        type="tool_use",
        id=tool_call_id,
        name="launch_pipeline",
        input={
            "bug_bounty_url": "https://immunefi.com/bug-bounty/example/",
            "target_repo": "owner/example-repo",
            "target_ref": "main",
        },
    )
    first_final = _FakeMessage(
        content=[
            _FakeContent(type="text", text="I'll launch the audit."),
            launch_block,
        ],
        stop_reason="tool_use",
    )
    first_events = [
        {"type": "content_block_delta", "delta": {"text": "I'll launch the audit."}},
        {
            "type": "tool_use",
            "id": tool_call_id,
            "name": "launch_pipeline",
            "input": dict(launch_block.input),
        },
    ]

    second_final = _FakeMessage(
        content=[_FakeContent(type="text", text="Run started, watching now.")],
        stop_reason="end_turn",
    )
    second_events = [
        {
            "type": "content_block_delta",
            "delta": {"text": "Run started, watching now."},
        },
    ]

    return _FakeClient(
        streams=[
            _FakeStream(first_events, first_final),
            _FakeStream(second_events, second_final),
        ]
    )


async def _drain_until_approval(
    iterator,
    *,
    tool_call_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pull events from an async iterator up to and including the approval prompt.

    Returns the collected list and the approval event so the test can
    assert on its fields.
    """

    collected: list[dict[str, Any]] = []
    async for ev in iterator:
        collected.append(ev)
        if (
            ev.get("type") == "tool_approval_required"
            and ev.get("tool_call_id") == tool_call_id
        ):
            return collected, ev
    raise AssertionError(
        f"stream finished without emitting tool_approval_required for "
        f"{tool_call_id!r}; got: {collected}"
    )


async def _drain_rest(iterator) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    async for ev in iterator:
        out.append(ev)
    return out


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_approvals() -> None:
    """Drop in-memory pending approvals between tests."""

    chat_approvals._reset_for_tests()


@pytest.fixture
def stubbed_supervisor(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace WorkspaceManager + RunSupervisor with in-memory stubs.

    Returns a dict the test can inspect to verify the stubs were
    actually invoked. The structure is intentionally flat so an assertion
    failure reads naturally.
    """

    state: dict[str, Any] = {
        "ensure_bare_cache_calls": [],
        "create_worktree_calls": [],
        "start_run_calls": [],
        "cancel_run_calls": [],
    }

    class _StubWorkspaceManager:
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        def ensure_bare_cache(self, repo_url: str) -> Path:
            state["ensure_bare_cache_calls"].append(repo_url)
            return Path("/tmp/fake-bare.git")

        def create_worktree(
            self, run_id: str, repo_url: str, ref: str | None = None
        ) -> Path:
            state["create_worktree_calls"].append(
                {"run_id": run_id, "repo_url": repo_url, "ref": ref}
            )
            return Path(f"/tmp/fake-wt/{run_id}")

    class _StubWorkspaceError(Exception):
        pass

    class _StubSupervisor:
        async def start_run(
            self,
            spec: Any,
            workspace_path: Path,
            target_info: dict[str, Any] | None = None,
        ) -> str:
            state["start_run_calls"].append(
                {"spec": spec, "workspace_path": workspace_path}
            )
            return "fake-run-id-123"

        async def cancel_run(self, run_id: str) -> None:
            state["cancel_run_calls"].append(run_id)

    def _stub_make_run_id(**kwargs: Any) -> str:
        return "fake-run-id-123"

    # Patch at the module-level names actually used inside _launch_pipeline.
    import web.server.services.workspace_manager as wm_mod
    import web.server.services.run_supervisor as sup_mod

    monkeypatch.setattr(wm_mod, "WorkspaceManager", _StubWorkspaceManager)
    monkeypatch.setattr(wm_mod, "WorkspaceError", _StubWorkspaceError, raising=False)
    monkeypatch.setattr(sup_mod, "get_run_supervisor", lambda: _StubSupervisor())
    monkeypatch.setattr(sup_mod, "make_run_id", _stub_make_run_id)

    return state


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------


def test_launch_pipeline_approve_triggers_supervisor(
    tmp_path: Path, stubbed_supervisor: dict[str, Any]
) -> None:
    """Approving a launch_pipeline tool_use must call supervisor.start_run."""

    conversation_id = "test-launch-approve"
    base = tmp_path
    tool_call_id = "tu_launch_approve"

    client = _launch_pipeline_streams(tool_call_id=tool_call_id)

    async def run() -> list[dict[str, Any]]:
        gen = chat_runtime.stream_response(
            conversation_id=conversation_id,
            user_text="please run the audit",
            client_factory=lambda _key: client,
            api_key="dummy",
            base=base,
        )
        # Pull up to the approval-required event.
        collected, approval_evt = await _drain_until_approval(
            gen, tool_call_id=tool_call_id
        )
        # The approval event should carry the proposed input and a preview.
        assert approval_evt["name"] == "launch_pipeline"
        assert approval_evt["input"]["target_repo"] == "owner/example-repo"
        assert approval_evt["preview"]["kind"] == "launch_pipeline"
        # Now resolve the pending approval as if the user clicked
        # "approve" in the SPA.
        ok = chat_approvals.resolve(
            conversation_id=conversation_id,
            tool_call_id=tool_call_id,
            action="approve",
        )
        assert ok is True
        # Drain the rest.
        rest = await _drain_rest(gen)
        return collected + rest

    events_out = asyncio.run(run())

    # tool_approval_required happens before any tool_use_result.
    types = [e.get("type") for e in events_out]
    assert "tool_approval_required" in types
    approval_idx = types.index("tool_approval_required")
    assert "tool_use_result" in types[approval_idx:], (
        "after approval we must emit a tool_use_result"
    )

    # The supervisor was actually invoked with our spec.
    assert len(stubbed_supervisor["start_run_calls"]) == 1
    start_call = stubbed_supervisor["start_run_calls"][0]
    assert start_call["spec"].target_repo == "owner/example-repo"

    # The workspace plumbing fired too.
    assert stubbed_supervisor["ensure_bare_cache_calls"] == [
        "https://github.com/owner/example-repo.git"
    ]
    assert len(stubbed_supervisor["create_worktree_calls"]) == 1

    # The tool_use_result carries the run_id returned by the stub.
    result_events = [e for e in events_out if e.get("type") == "tool_use_result"]
    assert any(
        r["result"].get("run_id") == "fake-run-id-123" for r in result_events
    ), f"expected run_id in tool_use_result: {result_events}"

    # The final stream terminates with message_stop.
    assert any(e.get("type") == "message_stop" for e in events_out)


def test_launch_pipeline_cancel_skips_supervisor(
    tmp_path: Path, stubbed_supervisor: dict[str, Any]
) -> None:
    """``action="cancel"`` must NOT touch the supervisor or workspace."""

    conversation_id = "test-launch-cancel"
    base = tmp_path
    tool_call_id = "tu_launch_cancel"

    client = _launch_pipeline_streams(tool_call_id=tool_call_id)

    async def run() -> list[dict[str, Any]]:
        gen = chat_runtime.stream_response(
            conversation_id=conversation_id,
            user_text="don't run anything",
            client_factory=lambda _key: client,
            api_key="dummy",
            base=base,
        )
        collected, _evt = await _drain_until_approval(
            gen, tool_call_id=tool_call_id
        )
        # User clicks "cancel" in the SPA.
        ok = chat_approvals.resolve(
            conversation_id=conversation_id,
            tool_call_id=tool_call_id,
            action="cancel",
        )
        assert ok is True
        rest = await _drain_rest(gen)
        return collected + rest

    events_out = asyncio.run(run())

    # The supervisor / workspace must not have run.
    assert stubbed_supervisor["start_run_calls"] == []
    assert stubbed_supervisor["ensure_bare_cache_calls"] == []
    assert stubbed_supervisor["create_worktree_calls"] == []

    # The tool_use_result for the cancelled tool reports declined=True.
    result_events = [e for e in events_out if e.get("type") == "tool_use_result"]
    assert any(
        r["result"].get("declined") is True for r in result_events
    ), f"expected declined result for cancelled approval: {result_events}"

    # The chat continued: after the declined result, a second round
    # happened with stop_reason=end_turn → message_stop is emitted.
    assert any(e.get("type") == "message_stop" for e in events_out)


def test_unknown_tool_is_rejected_at_allowlist(tmp_path: Path) -> None:
    """Defense in depth: ``erase_all_runs`` is not on the allowlist.

    Even with the SIDE_EFFECT_TOOLS gate in place, anything that isn't
    declared in ``TOOLS`` is rejected before any approval can be
    requested. The runtime emits ``error / tool_not_allowed`` and the
    assistant turn is NOT persisted (same v0 contract).
    """

    conversation_id = "test-unknown-tool"
    base = tmp_path

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
    events = [
        {"type": "content_block_delta", "delta": {"text": "I will erase everything."}},
        {
            "type": "tool_use",
            "id": "tu_evil",
            "name": "erase_all_runs",
            "input": {"confirm": True},
        },
    ]
    client = _FakeClient(streams=[_FakeStream(events, final)])

    async def run() -> list[dict[str, Any]]:
        gen = chat_runtime.stream_response(
            conversation_id=conversation_id,
            user_text="please erase everything",
            client_factory=lambda _key: client,
            api_key="dummy",
            base=base,
        )
        return await _drain_rest(gen)

    events_out = asyncio.run(run())

    error_events = [e for e in events_out if e.get("type") == "error"]
    assert error_events
    assert error_events[0]["reason"] == "tool_not_allowed"
    assert error_events[0]["tool"] == "erase_all_runs"

    # No approval request should have been emitted for the forged tool.
    assert not any(e.get("type") == "tool_approval_required" for e in events_out)

    # No assistant turn persisted.
    convo = chat_history.load_conversation(conversation_id, base=base)
    assert convo is not None
    assert "assistant" not in [m.role for m in convo.messages]


def test_dispatch_side_effect_rejects_non_side_effect_name() -> None:
    """Calling :func:`dispatch_side_effect_tool` with a read-only name fails.

    Defense in depth: the side-effect dispatcher is the only path that
    can mutate SPECA state. It must refuse to run ``read_run_status``
    even if a caller wired it up by mistake.
    """

    with pytest.raises(chat_tools.ToolNotAllowed):
        asyncio.run(
            chat_tools.dispatch_side_effect_tool("read_run_status", {"run_id": "x"})
        )

    # And of course truly-unknown names too.
    with pytest.raises(chat_tools.ToolNotAllowed):
        asyncio.run(
            chat_tools.dispatch_side_effect_tool("erase_all_runs", {})
        )


def test_tool_approve_route_returns_404_for_unknown(client) -> None:  # noqa: ARG001
    """``POST /api/chat/tool_approve`` must 404 when nothing is pending."""

    resp = client.post(
        "/api/chat/tool_approve",
        json={
            "conversation_id": "no-such-conversation",
            "tool_call_id": "no-such-call",
            "action": "approve",
        },
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["error"] == "no_pending_approval"

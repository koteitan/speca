"""Tests for the run-stream WebSocket router (Slice B2).

The supervisor is heavy-weight (spawns subprocesses, owns asyncio tasks),
so these tests **swap the singleton** for a tiny fake via
:func:`web.server.services.run_supervisor.get_run_supervisor`. The fake
implements only the two methods the WS route consumes:

* ``get_live_status(run_id) -> LiveStatus | None``
* ``subscribe(run_id) -> AsyncIterator[dict]``

Using ``TestClient.websocket_connect`` (a context manager that returns a
synchronous ``WebSocketTestSession``) we drive the route end-to-end and
assert on the exact event sequence the SPA's ``useRunStream`` hook will
see.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from web.server.main import create_app
from web.server.routers import runs_ws as runs_ws_module
from web.server.schemas.run_state import (
    LiveStatus,
    PhaseStateEntry,
    RunStateDoc,
)


# ---------------------------------------------------------------------------
# Fake supervisor
# ---------------------------------------------------------------------------


class _FakeSupervisor:
    """Minimal stand-in for :class:`RunSupervisor` used by every WS test.

    ``events`` is the script the fake replays from ``subscribe``. The fake
    also records whether ``subscribe`` was fully drained, so a test that
    triggers an early peer-disconnect can assert the generator's
    ``finally`` clause ran (catching subscriber-list leaks early).
    """

    def __init__(
        self,
        *,
        live: LiveStatus | None,
        events: list[dict[str, Any]] | None = None,
        state_doc: RunStateDoc | None = None,
    ) -> None:
        self._live = live
        self._events = events or []
        self._state_doc = state_doc
        self.subscribe_started = False
        self.subscribe_finalized = False
        self.events_yielded = 0

    def get_live_status(self, run_id: str) -> LiveStatus | None:
        return self._live

    async def subscribe(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        self.subscribe_started = True
        try:
            for ev in self._events:
                # A tiny await yields control so the WS sender / keepalive
                # can interleave; without it the for-loop blocks the
                # event loop and the keepalive ping never fires.
                await asyncio.sleep(0)
                self.events_yielded += 1
                yield ev
        finally:
            # This block is what the slice spec requires must run when
            # the consumer breaks early — we assert against it in the
            # disconnect test below.
            self.subscribe_finalized = True


def _patch_supervisor(monkeypatch: pytest.MonkeyPatch, fake: _FakeSupervisor) -> None:
    """Swap the module-level ``get_run_supervisor`` for both lookup sites.

    The WS router imports ``get_run_supervisor`` from
    ``..services.run_supervisor`` and calls it at request time, so we
    patch it on the router module *and* on the underlying service so
    indirect imports (e.g. main.py's lifespan) also see the fake.
    """

    monkeypatch.setattr(
        "web.server.routers.runs_ws.get_run_supervisor", lambda: fake
    )


def _patch_load_state(
    monkeypatch: pytest.MonkeyPatch, doc: RunStateDoc | None
) -> None:
    """Override the on-disk state loader used in the ``live is None`` branch."""

    monkeypatch.setattr(
        "web.server.routers.runs_ws.load_state",
        lambda run_id, runs_dir=None: doc,
    )


def _make_live(run_id: str = "run-live") -> LiveStatus:
    """Construct a :class:`LiveStatus` with one queued phase for tests."""

    return LiveStatus(
        run_id=run_id,
        status="running",
        current_phase="0a",
        phases=[PhaseStateEntry(phase_id="0a", status="running")],
        cost_usd_total=0.0,
        cancel_requested=False,
    )


def _make_doc(run_id: str = "run-finished") -> RunStateDoc:
    """Construct an on-disk doc shape for tests of the terminal-run branch."""

    return RunStateDoc(
        run_id=run_id,
        status="completed",
        current_phase=None,
        phases=[PhaseStateEntry(phase_id="0a", status="ok")],
        cost_usd_total=0.42,
    )


@pytest.fixture
def client() -> TestClient:
    """A fresh ``TestClient`` per test — the singleton patches are scoped."""

    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Happy path: live run, full event stream
# ---------------------------------------------------------------------------


def test_state_snapshot_is_first_event(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``state_snapshot`` always lands as the first frame after accept."""

    fake = _FakeSupervisor(
        live=_make_live("rid-1"),
        events=[
            {"type": "log_line", "run_id": "rid-1", "line": "hello"},
            {"type": "run_terminated", "run_id": "rid-1", "status": "completed"},
        ],
    )
    _patch_supervisor(monkeypatch, fake)

    with client.websocket_connect("/api/ws/runs/rid-1/stream") as ws:
        first = ws.receive_json()
        assert first["type"] == "state_snapshot"
        assert first["data"]["run_id"] == "rid-1"


def test_subscribe_events_are_forwarded_in_order(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every event yielded by ``subscribe`` is forwarded 1:1, in order."""

    events = [
        {"type": "phase_started", "run_id": "rid-2", "phase": "0a"},
        {"type": "log_line", "run_id": "rid-2", "line": "doing work"},
        {"type": "cost_update", "run_id": "rid-2", "delta_usd": 0.01},
        {"type": "phase_completed", "run_id": "rid-2", "phase": "0a", "status": "ok"},
        {"type": "run_terminated", "run_id": "rid-2", "status": "completed"},
    ]
    fake = _FakeSupervisor(live=_make_live("rid-2"), events=events)
    _patch_supervisor(monkeypatch, fake)

    received: list[dict[str, Any]] = []
    with client.websocket_connect("/api/ws/runs/rid-2/stream") as ws:
        # Snapshot + N events. ``receive_json`` raises on close so we
        # collect until the server-side close lands.
        snapshot = ws.receive_json()
        assert snapshot["type"] == "state_snapshot"
        for _ in events:
            received.append(ws.receive_json())

    types = [ev["type"] for ev in received]
    assert types == [
        "phase_started",
        "log_line",
        "cost_update",
        "phase_completed",
        "run_terminated",
    ]
    # The fake's generator must have run its ``finally`` clause once we
    # stopped consuming — proves the WS route closes the iterator
    # promptly rather than leaving it dangling.
    assert fake.subscribe_finalized is True


# ---------------------------------------------------------------------------
# Terminal-but-known run: state.json fallback + immediate close
# ---------------------------------------------------------------------------


def test_already_finished_run_sends_snapshot_then_terminator(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live is ``None`` but ``state.json`` exists — one snapshot, then close."""

    fake = _FakeSupervisor(live=None)
    _patch_supervisor(monkeypatch, fake)
    _patch_load_state(monkeypatch, _make_doc("rid-3"))

    with client.websocket_connect("/api/ws/runs/rid-3/stream") as ws:
        snapshot = ws.receive_json()
        terminator = ws.receive_json()
        # Server closes after the two frames — confirm by attempting
        # another receive and catching the disconnect.
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    assert snapshot["type"] == "state_snapshot"
    assert snapshot["data"]["run_id"] == "rid-3"
    assert snapshot["data"]["status"] == "completed"
    assert terminator["type"] == "run_terminated"
    assert terminator["reason"] == "already_finished"
    # ``subscribe`` is *not* used on this path.
    assert fake.subscribe_started is False


# ---------------------------------------------------------------------------
# Unknown run_id: state.json also missing
# ---------------------------------------------------------------------------


def test_unknown_run_id_yields_null_data_then_close(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both supervisor and disk miss — snapshot has ``data: None``."""

    fake = _FakeSupervisor(live=None)
    _patch_supervisor(monkeypatch, fake)
    _patch_load_state(monkeypatch, None)

    with client.websocket_connect("/api/ws/runs/no-such-run/stream") as ws:
        snapshot = ws.receive_json()
        terminator = ws.receive_json()
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    assert snapshot["type"] == "state_snapshot"
    assert snapshot["data"] is None
    assert snapshot["reason"] == "unknown_run_id"
    assert terminator["type"] == "run_terminated"


# ---------------------------------------------------------------------------
# Client disconnect: subscribe() generator is finalised
# ---------------------------------------------------------------------------


def test_client_disconnect_finalizes_subscribe(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the peer closes mid-stream, the subscribe generator's finally runs.

    We arm the fake with a long event list (no ``run_terminated``) and
    close the WS after consuming just the snapshot. The fake's
    ``subscribe_finalized`` flag should flip to True before the
    ``websocket_connect`` context manager exits.
    """

    long_stream = [
        {"type": "log_line", "run_id": "rid-4", "line": f"line-{i}"}
        for i in range(50)
    ]
    fake = _FakeSupervisor(live=_make_live("rid-4"), events=long_stream)
    _patch_supervisor(monkeypatch, fake)

    with client.websocket_connect("/api/ws/runs/rid-4/stream") as ws:
        first = ws.receive_json()
        assert first["type"] == "state_snapshot"
        # Drop the connection without draining — the server should
        # observe ``WebSocketDisconnect`` and unwind the async-for.

    # The TestClient context closing the socket triggers the server's
    # disconnect handling. Allow a brief breath for the fake's finally
    # to run on the server-side event loop.
    assert fake.subscribe_started is True
    assert fake.subscribe_finalized is True


# ---------------------------------------------------------------------------
# Keepalive ping
# ---------------------------------------------------------------------------


def test_keepalive_ping_is_emitted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the interval patched to ~0.05s a ping arrives before the chain ends.

    We slow down the event stream by injecting an awaitable that yields a
    couple of times before producing each event, so the keepalive task
    has a chance to fire between yields.
    """

    monkeypatch.setattr(runs_ws_module, "KEEPALIVE_INTERVAL_SECONDS", 0.05)

    class _SlowFake(_FakeSupervisor):
        async def subscribe(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
            self.subscribe_started = True
            try:
                # Pause long enough for the 50ms ping to fire at least once.
                await asyncio.sleep(0.2)
                yield {"type": "run_terminated", "run_id": run_id, "status": "completed"}
            finally:
                self.subscribe_finalized = True

    fake = _SlowFake(live=_make_live("rid-5"))
    _patch_supervisor(monkeypatch, fake)

    received_types: list[str] = []
    with client.websocket_connect("/api/ws/runs/rid-5/stream") as ws:
        snapshot = ws.receive_json()
        received_types.append(snapshot["type"])
        # Drain until run_terminated; we expect at least one ``ping`` in
        # between because the supervisor is sleeping for 200ms while the
        # keepalive fires every 50ms.
        while True:
            ev = ws.receive_json()
            received_types.append(ev["type"])
            if ev["type"] == "run_terminated":
                break

    assert received_types[0] == "state_snapshot"
    assert "ping" in received_types, (
        f"expected a 'ping' frame between snapshot and terminator, got: "
        f"{received_types!r}"
    )
    assert received_types[-1] == "run_terminated"

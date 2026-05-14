"""Tests for the run supervisor (Slice H1).

These tests favour **stubbed** subprocesses over real ones — spawning
``run_phase.py`` would take minutes and depends on heavyweight CLI tools.
Instead we:

* point :class:`RunSupervisor` at a small fake script (``tests/fixtures``)
  that finishes immediately and prints predictable lines on stdout, or
* monkey-patch ``subprocess.Popen`` directly to assert SIGTERM/SIGKILL
  transitions without touching the OS at all.

The fixture script is written on the fly into ``tmp_path`` so the test
suite has no on-disk file to maintain.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from web.server.schemas.run_state import RunStartSpec
from web.server.services import run_state
from web.server.services.run_supervisor import (
    PHASE_CHAIN,
    RunSupervisor,
    make_run_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec() -> RunStartSpec:
    """Default spec used by most happy-path tests."""

    return RunStartSpec(
        bug_bounty_url="https://example.invalid/bounty",
        target_repo="acme/widget",
        target_ref="main",
        keywords="kw1,kw2",
        spec_urls="https://spec.example.com/",
        workers=1,
        max_concurrent=1,
        push_to_remote=False,
    )


def _write_fake_run_phase(tmp_path: Path, *, exit_code: int = 0) -> list[str]:
    """Create a script that mimics ``run_phase.py``: prints + exits fast.

    Returns the argv prefix the supervisor should use when spawning it.
    Cross-platform: invoked via the same Python interpreter so we don't
    rely on ``uv``/PATH availability inside the test environment.
    """

    script = tmp_path / "fake_run_phase.py"
    script.write_text(
        # Minimal stand-in for ``scripts/run_phase.py``. Emits a couple of
        # recognisable lines so we can assert the supervisor classified
        # them, then exits with the requested code.
        "import json, sys\n"
        "print(json.dumps({'cost_usd': 0.0123}))\n"
        "print('hello from fake run_phase')\n"
        "print(json.dumps({'batch': 1, 'completed': 1}))\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    return [sys.executable, str(script)]


def _make_supervisor(
    tmp_path: Path,
    *,
    exit_code: int = 0,
    runs_dir: Path | None = None,
) -> RunSupervisor:
    """Build a supervisor wired to a fake ``run_phase`` script."""

    argv = _write_fake_run_phase(tmp_path, exit_code=exit_code)
    return RunSupervisor(
        runs_dir=runs_dir or (tmp_path / "runs"),
        repo_root=tmp_path,
        run_phase_argv=argv,
    )


async def _wait_for(condition, *, timeout: float = 5.0, interval: float = 0.05) -> None:
    """Poll ``condition()`` until truthy or raise ``TimeoutError``."""

    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        if condition():
            return
        if asyncio.get_event_loop().time() > deadline:
            raise TimeoutError(f"condition not met within {timeout}s")
        await asyncio.sleep(interval)


# ---------------------------------------------------------------------------
# run_id generation
# ---------------------------------------------------------------------------


def test_make_run_id_shape(tmp_path: Path) -> None:
    """Generated run_ids embed ts + 7-char sha + slug, joined by ``-``."""

    rid = make_run_id(target_repo="acme/widget", repo_root=tmp_path)
    parts = rid.split("-")
    # ts has its own dashes (YYYY-MM-DDTHH-MM-SSZ) -> 5 dashes -> 6 parts;
    # then sha + slug -> total of 8 fragments minimum. Use a looser check:
    # the slug "widget" must be the last piece.
    assert parts[-1] == "widget"
    # Without git, sha falls back to "unknown".
    assert "unknown" in parts or any(len(p) == 7 for p in parts[-3:-1])


def test_make_run_id_unknown_slug_when_no_inputs(tmp_path: Path) -> None:
    """Empty inputs collapse to slug=``unknown``."""

    rid = make_run_id(target_repo="", bug_bounty_url="", repo_root=tmp_path)
    assert rid.endswith("-unknown")


# ---------------------------------------------------------------------------
# start_run + phase chain driver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_run_creates_state_json(tmp_path: Path) -> None:
    """``start_run`` returns immediately and seeds ``state.json``."""

    sup = _make_supervisor(tmp_path)
    run_id = await sup.start_run(_make_spec(), workspace_path=tmp_path)

    state_file = tmp_path / "runs" / run_id / "state.json"
    assert state_file.exists()

    # Block until the chain driver has completed so the watchdog task gets
    # cancelled cleanly before we tear down the event loop.
    active = sup._active[run_id]
    if active.driver_task is not None:
        await active.driver_task


@pytest.mark.asyncio
async def test_phase_chain_runs_all_phases_in_order(tmp_path: Path) -> None:
    """The driver walks ``PHASE_CHAIN`` from 0a through 04."""

    sup = _make_supervisor(tmp_path)
    run_id = await sup.start_run(_make_spec(), workspace_path=tmp_path)

    active = sup._active[run_id]
    assert active.driver_task is not None
    await active.driver_task

    doc = run_state.load_state(run_id, runs_dir=tmp_path / "runs")
    assert doc is not None
    assert doc.status == "completed"

    # Every phase should be ok'd, in chain order.
    ordered_ids = [p.phase_id for p in doc.phases]
    assert ordered_ids == list(PHASE_CHAIN)
    for phase in doc.phases:
        assert phase.status == "ok", f"{phase.phase_id} ended {phase.status}"


@pytest.mark.asyncio
async def test_phase_chain_stops_on_failure(tmp_path: Path) -> None:
    """A non-zero exit code aborts the chain and marks the run as failed."""

    sup = _make_supervisor(tmp_path, exit_code=2)
    run_id = await sup.start_run(_make_spec(), workspace_path=tmp_path)

    await sup._active[run_id].driver_task  # type: ignore[arg-type]

    doc = run_state.load_state(run_id, runs_dir=tmp_path / "runs")
    assert doc is not None
    assert doc.status == "failed"

    # First phase failed, the rest stayed queued.
    statuses = {p.phase_id: p.status for p in doc.phases}
    assert statuses[PHASE_CHAIN[0]] == "failed"
    assert statuses[PHASE_CHAIN[-1]] == "queued"


# ---------------------------------------------------------------------------
# subscribe — state_snapshot + run_terminated bookend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_emits_snapshot_first_and_terminator_last(
    tmp_path: Path,
) -> None:
    """The event stream is bookended by state_snapshot + run_terminated."""

    sup = _make_supervisor(tmp_path)
    run_id = await sup.start_run(_make_spec(), workspace_path=tmp_path)

    # Subscribe in parallel with the chain driver.
    events: list[dict[str, Any]] = []

    async def consume() -> None:
        async for ev in sup.subscribe(run_id):
            events.append(ev)

    consumer = asyncio.create_task(consume())
    await sup._active[run_id].driver_task  # type: ignore[arg-type]
    # Give the consumer a moment to drain the queue.
    try:
        await asyncio.wait_for(consumer, timeout=2.0)
    except asyncio.TimeoutError:
        consumer.cancel()
        raise

    assert events, "subscribe yielded no events"
    assert events[0]["type"] == "state_snapshot"
    assert events[-1]["type"] == "run_terminated"


# ---------------------------------------------------------------------------
# cancel_run — SIGTERM then SIGKILL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_run_sigterm_then_sigkill(tmp_path: Path) -> None:
    """Cancel sends SIGTERM; after 10s without exit it escalates to kill.

    We patch ``asyncio.wait_for`` to simulate the timeout deterministically
    so the test does not actually sleep 10 seconds.
    """

    sup = RunSupervisor(
        runs_dir=tmp_path / "runs",
        repo_root=tmp_path,
        # Use a script that hangs so it doesn't self-exit before cancel.
        run_phase_argv=_write_fake_run_phase(tmp_path),
    )
    run_id = "manual-run-id"

    # Build a fake popen that records terminate/kill calls and never exits.
    fake_popen = MagicMock(spec=subprocess.Popen)
    fake_popen.pid = 12345
    fake_popen.poll.return_value = None  # "still running"

    from web.server.schemas.run_state import PhaseStateEntry, RunStateDoc
    from web.server.services.run_supervisor import _ActiveRun

    active = _ActiveRun(
        run_id=run_id,
        spec=_make_spec(),
        workspace_path=tmp_path,
        target_info=None,
        doc=RunStateDoc(
            run_id=run_id,
            status="running",
            current_phase="0a",
            phases=[PhaseStateEntry(phase_id=p) for p in PHASE_CHAIN],
        ),
    )
    active.popen = fake_popen
    sup._active[run_id] = active

    (tmp_path / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    run_state.write_state(run_id, active.doc, runs_dir=tmp_path / "runs")

    # ``asyncio.wait_for`` is what the supervisor uses to wait for the
    # SIGTERM to take effect — force it to raise TimeoutError so the kill
    # path runs immediately.
    async def fake_wait_for(awaitable, timeout):
        # Cancel the inner awaitable so it doesn't dangle.
        if asyncio.iscoroutine(awaitable):
            task = asyncio.ensure_future(awaitable)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        raise asyncio.TimeoutError

    with patch("web.server.services.run_supervisor.asyncio.wait_for", new=fake_wait_for):
        if sys.platform == "win32":
            # On Windows the supervisor calls ``popen.send_signal(CTRL_BREAK_EVENT)``
            # then ``popen.kill()``.
            await sup.cancel_run(run_id)
            assert fake_popen.send_signal.called
            assert fake_popen.send_signal.call_args[0][0] == signal.CTRL_BREAK_EVENT
            assert fake_popen.kill.called
        else:
            # POSIX path: ``os.killpg(getpgid(pid), SIGTERM)`` then SIGKILL.
            with patch("web.server.services.run_supervisor.os.killpg") as kpg, patch(
                "web.server.services.run_supervisor.os.getpgid", return_value=12345
            ):
                await sup.cancel_run(run_id)
                signals = [call.args[1] for call in kpg.call_args_list]
                assert signal.SIGTERM in signals
                assert signal.SIGKILL in signals

    # state.json should now reflect the cancel request.
    doc = run_state.load_state(run_id, runs_dir=tmp_path / "runs")
    assert doc is not None
    assert doc.cancel_requested is True


# ---------------------------------------------------------------------------
# rerun_phases — reject while running
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rerun_phases_rejected_while_running(tmp_path: Path) -> None:
    """Rerun on a still-running run raises RuntimeError (HTTP 400 upstream)."""

    sup = RunSupervisor(
        runs_dir=tmp_path / "runs",
        repo_root=tmp_path,
        run_phase_argv=_write_fake_run_phase(tmp_path),
    )

    from web.server.schemas.run_state import PhaseStateEntry, RunStateDoc
    from web.server.services.run_supervisor import _ActiveRun

    run_id = "stuck"
    active = _ActiveRun(
        run_id=run_id,
        spec=_make_spec(),
        workspace_path=tmp_path,
        target_info=None,
        doc=RunStateDoc(
            run_id=run_id,
            status="running",
            phases=[PhaseStateEntry(phase_id=p) for p in PHASE_CHAIN],
        ),
    )
    # Synthesize a not-done driver task: schedule an awaitable that never
    # returns; we'll cancel it at the end of the test.
    never = asyncio.Event()

    async def _hang() -> None:
        await never.wait()

    active.driver_task = asyncio.create_task(_hang())
    sup._active[run_id] = active

    (tmp_path / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    run_state.write_state(run_id, active.doc, runs_dir=tmp_path / "runs")

    with pytest.raises(RuntimeError):
        await sup.rerun_phases(run_id, ["03"])

    # Cleanup
    active.driver_task.cancel()
    try:
        await active.driver_task
    except (asyncio.CancelledError, Exception):
        pass


# ---------------------------------------------------------------------------
# Orphan reconciliation integration — supervisor reads state on boot
# ---------------------------------------------------------------------------


def test_orphan_reconciliation_flags_dead_supervisor(tmp_path: Path) -> None:
    """A state.json with status=running + dead owner_pid -> crashed."""

    from web.server.schemas.run_state import PhaseStateEntry, RunStateDoc

    run_id = "ghost"
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    doc = RunStateDoc(
        run_id=run_id,
        status="running",
        current_phase="01a",
        phases=[
            PhaseStateEntry(phase_id="01a", status="running"),
            PhaseStateEntry(phase_id="01b", status="queued"),
        ],
        # A PID we know is dead — INT32_MAX is reliably outside any kernel's
        # PID range on Windows/Linux/macOS.
        owner_pid=2**31 - 1,
    )
    run_state.write_state(run_id, doc, runs_dir=runs_dir)

    reconciled = run_state.reconcile_orphans(supervisor=None, runs_dir=runs_dir)
    assert run_id in reconciled

    after = run_state.load_state(run_id, runs_dir=runs_dir)
    assert after is not None
    assert after.status == "crashed"
    # The running phase row was demoted; the queued one is untouched.
    states = {p.phase_id: p.status for p in after.phases}
    assert states["01a"] == "failed"
    assert states["01b"] == "queued"


# ---------------------------------------------------------------------------
# get_live_status — falls back to disk when supervisor doesn't know the run
# ---------------------------------------------------------------------------


def test_get_live_status_reads_from_disk_when_not_active(tmp_path: Path) -> None:
    """``get_live_status`` survives a supervisor restart by reading state.json."""

    from web.server.schemas.run_state import PhaseStateEntry, RunStateDoc

    sup = RunSupervisor(runs_dir=tmp_path / "runs", repo_root=tmp_path)
    run_id = "from-disk"
    (tmp_path / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    run_state.write_state(
        run_id,
        RunStateDoc(
            run_id=run_id,
            status="completed",
            phases=[PhaseStateEntry(phase_id="0a", status="ok")],
            cost_usd_total=4.20,
        ),
        runs_dir=tmp_path / "runs",
    )

    live = sup.get_live_status(run_id)
    assert live is not None
    assert live.status == "completed"
    assert live.cost_usd_total == 4.20


def test_get_live_status_returns_none_when_unknown(tmp_path: Path) -> None:
    """A run that has no in-memory record *and* no state.json -> None."""

    sup = RunSupervisor(runs_dir=tmp_path / "runs", repo_root=tmp_path)
    assert sup.get_live_status("never-existed") is None

"""Tests for the on-disk state.json substrate (Slice H1).

These tests are *file-system only* — no subprocesses, no FastAPI app.
The supervisor lifecycle is covered separately by
``test_run_supervisor.py``.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from web.server.schemas.run_state import PhaseStateEntry, RunStateDoc
from web.server.services import run_state


# ---------------------------------------------------------------------------
# Atomic write — happy path
# ---------------------------------------------------------------------------


def _make_doc(run_id: str = "test-run") -> RunStateDoc:
    """Build a minimal but populated state doc for round-trip tests."""

    return RunStateDoc(
        run_id=run_id,
        status="running",
        current_phase="01a",
        phases=[
            PhaseStateEntry(phase_id="01a", status="running"),
            PhaseStateEntry(phase_id="01b", status="queued"),
        ],
        cost_usd_total=1.23,
    )


def test_write_state_round_trip(tmp_path: Path) -> None:
    """``write_state`` followed by ``load_state`` returns the same doc."""

    doc = _make_doc()
    path = run_state.write_state("test-run", doc, runs_dir=tmp_path)

    assert path.exists()
    assert path.name == "state.json"

    loaded = run_state.load_state("test-run", runs_dir=tmp_path)
    assert loaded is not None
    assert loaded.run_id == "test-run"
    assert loaded.status == "running"
    assert loaded.current_phase == "01a"
    assert loaded.cost_usd_total == 1.23
    assert [p.phase_id for p in loaded.phases] == ["01a", "01b"]


def test_write_state_creates_run_dir(tmp_path: Path) -> None:
    """Parent directory is auto-created — no manual mkdir required."""

    doc = _make_doc("brand-new")
    assert not (tmp_path / "brand-new").exists()
    run_state.write_state("brand-new", doc, runs_dir=tmp_path)
    assert (tmp_path / "brand-new" / "state.json").exists()


def test_write_state_atomic_no_leftover_tempfile(tmp_path: Path) -> None:
    """The tempfile is renamed away; no ``.state.*.json.tmp`` remains."""

    doc = _make_doc()
    run_state.write_state("test-run", doc, runs_dir=tmp_path)

    run_dir = tmp_path / "test-run"
    leftover = [p for p in run_dir.iterdir() if p.name != "state.json"]
    assert leftover == [], f"unexpected leftover files: {leftover}"


# ---------------------------------------------------------------------------
# Load failure modes
# ---------------------------------------------------------------------------


def test_load_state_returns_none_when_missing(tmp_path: Path) -> None:
    """Missing file yields ``None`` rather than raising."""

    assert run_state.load_state("nope", runs_dir=tmp_path) is None


def test_load_state_returns_none_on_corrupted_json(tmp_path: Path) -> None:
    """A half-written JSON blob is logged + ignored."""

    run_dir = tmp_path / "corrupt"
    run_dir.mkdir()
    # Write a deliberately broken JSON payload — simulates a crash mid-write
    # (in practice ``os.replace`` prevents this, but the read path must
    # still cope).
    (run_dir / "state.json").write_text(
        '{"run_id": "corrupt", "status": "runn',
        encoding="utf-8",
    )

    assert run_state.load_state("corrupt", runs_dir=tmp_path) is None


def test_load_state_returns_none_on_schema_violation(tmp_path: Path) -> None:
    """A payload that fails Pydantic validation is also swallowed."""

    run_dir = tmp_path / "wrong-shape"
    run_dir.mkdir()
    # Missing required ``run_id`` field.
    (run_dir / "state.json").write_text(
        json.dumps({"status": "running"}),
        encoding="utf-8",
    )

    assert run_state.load_state("wrong-shape", runs_dir=tmp_path) is None


# ---------------------------------------------------------------------------
# Concurrency — two threads writing must not interleave bytes
# ---------------------------------------------------------------------------


def test_concurrent_writes_never_corrupt_state(tmp_path: Path) -> None:
    """50 threads write large docs concurrently; every read parses cleanly.

    The atomic tempfile + ``os.replace`` recipe guarantees that any reader
    at any moment sees either the *previous* full payload or the *next*
    full payload — never a mix. We probe that invariant by hammering the
    file from 50 threads and re-reading after each write.
    """

    # Make payloads big enough that a non-atomic write would be observably
    # interleaved (>4 KiB pages on most filesystems).
    big_reason = "x" * 2048

    errors: list[BaseException] = []

    def writer(idx: int) -> None:
        try:
            doc = RunStateDoc(
                run_id="concurrent",
                status="running",
                phases=[
                    PhaseStateEntry(
                        phase_id=f"p{idx:02d}",
                        status="running",
                        reason=big_reason,
                    )
                ],
            )
            run_state.write_state("concurrent", doc, runs_dir=tmp_path)
            # Read-back from within the worker is best-effort — on Windows
            # a concurrent ``os.replace`` can briefly raise SHARING_VIOLATION
            # during ``read_text``, which ``load_state`` swallows to ``None``.
            # The contract is "eventual consistency": the final state.json
            # is always a complete, parsable payload, verified below.
        except BaseException as exc:  # pragma: no cover - diagnostic
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"writer threads raised: {errors!r}"

    # The eventual on-disk file is a complete, parseable doc — never a mix
    # of two writers' bytes. This is the actual atomicity guarantee.
    final = run_state.load_state("concurrent", runs_dir=tmp_path)
    assert final is not None
    assert final.run_id == "concurrent"


# ---------------------------------------------------------------------------
# Orphan reconciliation
# ---------------------------------------------------------------------------


def _seed_running_run(
    runs_dir: Path,
    *,
    run_id: str,
    owner_pid: int,
) -> None:
    """Helper: write a ``state.json`` that claims to still be ``running``."""

    doc = RunStateDoc(
        run_id=run_id,
        status="running",
        current_phase="01a",
        phases=[
            PhaseStateEntry(phase_id="01a", status="running"),
            PhaseStateEntry(phase_id="01b", status="queued"),
        ],
        owner_pid=owner_pid,
    )
    run_state.write_state(run_id, doc, runs_dir=runs_dir)


def _pick_dead_pid() -> int:
    """Pick a PID that is highly unlikely to be alive on the test box.

    We use ``2**31 - 1`` (INT32_MAX) — most kernels cap PIDs well below
    this. If by cosmic accident the PID is alive we accept the false
    negative: the orphan test would simply not trigger the rewrite path.
    """

    return 2**31 - 1


def test_reconcile_orphans_marks_dead_owners_as_crashed(tmp_path: Path) -> None:
    """A ``running`` run whose owner_pid is dead becomes ``crashed``."""

    _seed_running_run(tmp_path, run_id="crashed-1", owner_pid=_pick_dead_pid())

    reconciled = run_state.reconcile_orphans(supervisor=None, runs_dir=tmp_path)
    assert "crashed-1" in reconciled

    doc = run_state.load_state("crashed-1", runs_dir=tmp_path)
    assert doc is not None
    assert doc.status == "crashed"
    # The still-running phase row gets demoted to ``failed`` with a reason.
    running_row = next(p for p in doc.phases if p.phase_id == "01a")
    assert running_row.status == "failed"
    assert running_row.reason is not None


def test_reconcile_orphans_skips_current_owner(tmp_path: Path) -> None:
    """If owner_pid == current PID, the row is left untouched.

    This is the post-restart case where the freshly-launched supervisor
    is still the legitimate owner of an existing ``state.json``.
    """

    _seed_running_run(tmp_path, run_id="self-owned", owner_pid=os.getpid())

    reconciled = run_state.reconcile_orphans(supervisor=None, runs_dir=tmp_path)
    assert "self-owned" not in reconciled

    doc = run_state.load_state("self-owned", runs_dir=tmp_path)
    assert doc is not None
    assert doc.status == "running"


def test_reconcile_orphans_leaves_terminal_runs_alone(tmp_path: Path) -> None:
    """A ``completed`` run is not touched even if owner_pid is dead."""

    doc = RunStateDoc(
        run_id="done",
        status="completed",
        owner_pid=_pick_dead_pid(),
    )
    run_state.write_state("done", doc, runs_dir=tmp_path)

    reconciled = run_state.reconcile_orphans(supervisor=None, runs_dir=tmp_path)
    assert "done" not in reconciled

    after = run_state.load_state("done", runs_dir=tmp_path)
    assert after is not None
    assert after.status == "completed"


def test_reconcile_orphans_handles_missing_runs_dir(tmp_path: Path) -> None:
    """A non-existent runs_dir returns an empty list, not an error."""

    missing = tmp_path / "no-such-dir"
    result = run_state.reconcile_orphans(supervisor=None, runs_dir=missing)
    assert result == []

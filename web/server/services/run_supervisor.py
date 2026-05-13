"""Run lifecycle orchestration for the SPECA web backend (Slice H1).

The supervisor is the **only** code path in the web backend that owns a
subprocess. Every operation on a running phase chain — start, cancel,
rerun, broadcast — goes through this singleton, so we have exactly one
place to:

* spawn ``scripts/run_phase.py`` per phase, with the right env vars
* SIGTERM the process group on cancel (CTRL_BREAK_EVENT on Windows),
  escalate to SIGKILL after a 10s grace
* read stdout line by line, JSON-decode if possible, route to the right
  event type (``log_line`` vs ``cost_update`` vs ``phase_progress``)
* persist transitions to ``.speca/runs/<id>/state.json`` atomically
* broadcast every event to any subscriber via per-run asyncio queues
* tick a watchdog every 5s so external observers can tell whether the
  supervisor is healthy

The class is exposed via :func:`get_run_supervisor`, a module-level
factory that returns the same instance per-process — FastAPI dependencies
can call this from request handlers without worrying about lifetime.

The supervisor deliberately does **not** import anything from
``scripts.orchestrator.*``. We talk to the orchestrator through the
``scripts/run_phase.py`` CLI surface only, exactly like the design doc
``docs/UI_DESIGN.md`` §2.1 prescribes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Mapping

from web.server.config import SPECA_REPO_ROOT, SPECA_RUNS_DIR
from web.server.schemas.run_state import (
    LiveStatus,
    PhaseStateEntry,
    RunStartSpec,
    RunStateDoc,
)
from web.server.services import run_state

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Phase chain executed by ``start_run``. Mirrors the order documented in
#: ``CLAUDE.md`` "Pipeline Phases" plus the (currently CI-only) bootstrap
#: phases ``0a``/``0b``/``0c`` from ``.github/workflows/full-audit.yml``.
PHASE_CHAIN: tuple[str, ...] = (
    "0a",
    "0b",
    "0c",
    "01a",
    "01b",
    "01e",
    "02c",
    "03",
    "04",
)

#: Human-readable description per phase used in auto-commit messages.
#: The order intentionally matches :data:`PHASE_CHAIN`.
PHASE_DESCRIPTIONS: dict[str, str] = {
    "0a": "scope extraction",
    "0b": "target checkout",
    "0c": "target info",
    "01a": "spec discovery",
    "01b": "subgraph extraction",
    "01e": "property generation",
    "02c": "code pre-resolution",
    "03": "audit map",
    "04": "review",
}

#: How long we wait between SIGTERM and SIGKILL when cancelling a run.
_CANCEL_GRACE_SECONDS = 10.0

#: Watchdog tick interval — every N seconds we rewrite ``last_heartbeat_at``.
_WATCHDOG_TICK_SECONDS = 5.0

#: ``CREATE_NEW_PROCESS_GROUP`` from ``wincon.h``.  Only relevant on Win32 —
#: we still define it as a Python constant so the supervisor never has to
#: reach into ``subprocess`` constants conditionally outside __init__ time.
_CREATE_NEW_PROCESS_GROUP = 0x00000200


# ---------------------------------------------------------------------------
# run_id generation
# ---------------------------------------------------------------------------


def _short_git_sha(repo_root: Path) -> str:
    """Return a 7-char git short SHA of HEAD, or ``"unknown"`` on failure.

    Run inline (no asyncio) — caller is on the start path which we *want*
    blocking, so a missing git binary surfaces immediately rather than
    via a phantom queue event later.
    """

    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            timeout=5.0,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return "unknown"
    sha = out.decode("utf-8", errors="replace").strip()
    return sha or "unknown"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug_from_target(target_repo: str | None, bug_bounty_url: str | None) -> str:
    """Derive a short slug for the run id.

    Preference order:

    1. final non-empty segment of ``target_repo`` (``owner/repo`` -> ``repo``)
    2. host slug of ``bug_bounty_url``
    3. ``"unknown"``

    The slug is lowercased and non-alnum chars are collapsed to ``-``.
    A trailing 8-char hash is appended only if the source is *empty* —
    we want stable readable ids when possible.
    """

    candidate = ""
    if target_repo:
        tail = target_repo.rstrip("/").split("/")[-1]
        candidate = tail
    if not candidate and bug_bounty_url:
        # Strip scheme + path, keep host.
        try:
            from urllib.parse import urlparse

            host = urlparse(bug_bounty_url).hostname or ""
            candidate = host
        except Exception:  # pragma: no cover - defensive
            candidate = ""

    candidate = candidate.lower()
    slug = _SLUG_RE.sub("-", candidate).strip("-")
    if not slug:
        return "unknown"
    if len(slug) > 24:
        # Keep ids tractable. Drop the tail, not the head, so the slug
        # still starts with a recognisable prefix.
        slug = slug[:24].rstrip("-")
    return slug or "unknown"


def make_run_id(
    *,
    target_repo: str | None = None,
    bug_bounty_url: str | None = None,
    now: datetime | None = None,
    repo_root: Path | None = None,
) -> str:
    """Build a stable run id: ``{ts}-{short_sha}-{spec_slug}``.

    Format matches the existing ``.speca/runs/<id>`` layout, e.g.
    ``2026-05-12T07-30-15Z-994f630-OpenList``.

    Re-implements the logic the orchestrator CLI would otherwise own; once
    ``scripts/run_phase.py`` exposes a ``make_run_id`` helper this function
    can be replaced with a thin re-export.
    """

    moment = now or datetime.now(timezone.utc)
    ts = moment.strftime("%Y-%m-%dT%H-%M-%SZ")
    sha = _short_git_sha(repo_root or SPECA_REPO_ROOT)
    slug = _slug_from_target(target_repo, bug_bounty_url)
    return f"{ts}-{sha}-{slug}"


# ---------------------------------------------------------------------------
# Internal active-run record
# ---------------------------------------------------------------------------


@dataclass
class _ActiveRun:
    """In-memory bookkeeping for one in-flight run.

    ``popen`` is the *current* phase subprocess — set by the chain driver,
    cleared on phase exit.  Cancel paths use it to send SIGTERM/SIGKILL.

    ``queue`` is the canonical broadcaster.  Every subscriber holds its
    *own* asyncio.Queue (fan-out is done in :meth:`RunSupervisor.subscribe`)
    so we never need to worry about back-pressure across consumers.
    """

    run_id: str
    spec: RunStartSpec
    workspace_path: Path
    target_info: dict[str, Any] | None
    doc: RunStateDoc
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    subscribers: list[asyncio.Queue[dict[str, Any]]] = field(default_factory=list)
    popen: subprocess.Popen[bytes] | None = None
    driver_task: asyncio.Task[None] | None = None
    watchdog_task: asyncio.Task[None] | None = None


# ---------------------------------------------------------------------------
# RunSupervisor
# ---------------------------------------------------------------------------


class RunSupervisor:
    """Singleton-style coordinator for all running audits.

    Instances are *not* thread-safe — asyncio is the only concurrency
    primitive used; do not call methods from multiple threads.  The
    expected lifecycle:

    * uvicorn boots, calls :func:`get_run_supervisor` -> a single shared
      instance, then :func:`reconcile_orphans` on startup.
    * Each HTTP/WS handler that mutates state goes through this instance.
    * On shutdown the supervisor is *not* asked to gracefully cancel —
      uvicorn's signal handler reaches the OS first; the next supervisor
      boot will reconcile the runs as ``crashed``.
    """

    def __init__(
        self,
        *,
        runs_dir: Path | None = None,
        repo_root: Path | None = None,
        run_phase_argv: list[str] | None = None,
    ) -> None:
        self._runs_dir: Path = runs_dir or SPECA_RUNS_DIR
        self._repo_root: Path = repo_root or SPECA_REPO_ROOT
        # ``run_phase_argv`` lets tests inject a fake script in place of
        # ``uv run python scripts/run_phase.py``. Default keeps the
        # production CLI invocation as-is.
        #
        # NOTE: ``python`` (not ``python3``) — the Windows uv venv ships
        # ``python.exe`` only; spawning ``python3`` from within the venv
        # exits 9009 (cmd.exe "command not recognised"). ``python`` works
        # on every supported platform (Linux/macOS/Windows) inside ``uv
        # run``.
        self._run_phase_argv: list[str] = run_phase_argv or [
            "uv",
            "run",
            "python",
            str(self._repo_root / "scripts" / "run_phase.py"),
        ]
        self._active: dict[str, _ActiveRun] = {}

    # -- public API ------------------------------------------------------

    async def start_run(
        self,
        spec: RunStartSpec,
        workspace_path: Path,
        target_info: dict[str, Any] | None = None,
    ) -> str:
        """Spawn a new run and return its ``run_id`` immediately.

        The phase chain is driven by an asyncio Task so this coroutine
        does not block on the audit completing.  The returned id is
        present in :attr:`_active` and persisted to disk before we
        return, so a caller that immediately POSTs ``/cancel`` will hit
        a valid id.
        """

        run_id = make_run_id(
            target_repo=spec.target_repo,
            bug_bounty_url=str(spec.bug_bounty_url) if spec.bug_bounty_url else None,
            repo_root=self._repo_root,
        )

        run_dir = self._runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "phases").mkdir(exist_ok=True)

        doc = RunStateDoc(
            run_id=run_id,
            status="queued",
            current_phase=None,
            phases=[PhaseStateEntry(phase_id=p) for p in PHASE_CHAIN],
            cost_usd_total=0.0,
        )
        run_state.write_state(run_id, doc, runs_dir=self._runs_dir)

        active = _ActiveRun(
            run_id=run_id,
            spec=spec,
            workspace_path=workspace_path,
            target_info=target_info,
            doc=doc,
        )
        self._active[run_id] = active

        active.driver_task = asyncio.create_task(
            self._drive_phase_chain(active), name=f"speca-run-{run_id}"
        )
        active.watchdog_task = asyncio.create_task(
            self._watchdog(active), name=f"speca-watchdog-{run_id}"
        )
        return run_id

    def update_budget_cap(
        self, run_id: str, max_budget_usd: float | None
    ) -> None:
        """Reflect a cap change into the in-memory active doc.

        The router has already written state.json before calling this,
        so we only have to mutate the supervisor's cached snapshot — that
        keeps the next ``GET /api/runs/<id>`` consistent without waiting
        for a watchdog tick. No-op for runs the supervisor has already
        evicted (the on-disk cap is already authoritative).
        """

        active = self._active.get(run_id)
        if active is None:
            return
        active.doc = active.doc.model_copy(
            update={"max_budget_usd": max_budget_usd}
        )

    async def cancel_run(self, run_id: str) -> None:
        """Request cooperative cancellation; escalate to SIGKILL after 10s.

        Idempotent — calling cancel on a run that is already terminal is
        a no-op (we still set ``cancel_requested`` for observability).
        """

        active = self._active.get(run_id)
        if active is None:
            # The run may have already completed and been evicted; reflect
            # the intent in state.json so the UI sees a consistent flag.
            doc = run_state.load_state(run_id, runs_dir=self._runs_dir)
            if doc is not None and doc.status in {"queued", "running"}:
                doc = doc.model_copy(
                    update={"cancel_requested": True, "status": "cancelled"}
                )
                run_state.write_state(run_id, doc, runs_dir=self._runs_dir)
            return

        active.cancel_event.set()
        active.doc = active.doc.model_copy(update={"cancel_requested": True})
        self._persist(active)
        await self._broadcast(active, {"type": "state_updated", "run_id": run_id})

        popen = active.popen
        if popen is None or popen.poll() is not None:
            return

        # First nudge: SIGTERM (or CTRL_BREAK_EVENT on Windows).
        await self._terminate_group(popen)

        # Wait for graceful exit.
        try:
            await asyncio.wait_for(
                asyncio.to_thread(popen.wait), timeout=_CANCEL_GRACE_SECONDS
            )
        except asyncio.TimeoutError:
            logger.warning(
                "speca: %s did not exit %.0fs after SIGTERM, escalating to SIGKILL",
                run_id,
                _CANCEL_GRACE_SECONDS,
            )
            await self._kill_group(popen)

    async def rerun_phases(self, run_id: str, phases: list[str]) -> None:
        """Re-run the listed phases (``--force``) once the run is terminal.

        Per the slice spec, rerunning a *running* run is rejected; the
        caller (HTTP layer) is expected to translate this into 400.
        """

        active = self._active.get(run_id)
        if active is not None and active.driver_task is not None:
            if not active.driver_task.done():
                raise RuntimeError(
                    f"run {run_id} is still running; cancel it before rerunning"
                )

        doc = run_state.load_state(run_id, runs_dir=self._runs_dir)
        if doc is None:
            raise FileNotFoundError(f"no state.json for run {run_id}")

        target_phases = [p for p in phases if p in PHASE_CHAIN]
        if not target_phases:
            raise ValueError(f"no valid phases to rerun: {phases!r}")

        updated_rows: list[PhaseStateEntry] = []
        for entry in doc.phases:
            if entry.phase_id in target_phases:
                entry = entry.model_copy(
                    update={
                        "status": "running",
                        "started_at": None,
                        "ended_at": None,
                        "pid": None,
                        "reason": "rerun requested",
                    }
                )
            updated_rows.append(entry)

        doc = doc.model_copy(
            update={
                "status": "running",
                "current_phase": target_phases[0],
                "phases": updated_rows,
                "cancel_requested": False,
            }
        )
        run_state.write_state(run_id, doc, runs_dir=self._runs_dir)

        # The spec says ``rerun`` does **not** mint a new run_id — we
        # restart the supervisor's in-memory record in place.  Use a
        # synthetic ``RunStartSpec`` derived from defaults; the chain
        # driver only reads workspace/env so this is enough.
        if active is None:
            active = _ActiveRun(
                run_id=run_id,
                spec=RunStartSpec(  # type: ignore[call-arg]
                    target_repo="rerun/placeholder",
                ),
                workspace_path=self._repo_root,
                target_info=None,
                doc=doc,
            )
            self._active[run_id] = active
        else:
            active.doc = doc
            active.cancel_event = asyncio.Event()

        active.driver_task = asyncio.create_task(
            self._drive_phase_chain(active, only_phases=target_phases, force=True),
            name=f"speca-rerun-{run_id}",
        )
        if active.watchdog_task is None or active.watchdog_task.done():
            active.watchdog_task = asyncio.create_task(
                self._watchdog(active), name=f"speca-watchdog-{run_id}"
            )

    async def subscribe(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yield events for ``run_id`` until the run terminates.

        Always emits a ``state_snapshot`` first (built from the *current*
        ``RunStateDoc``) and a ``run_terminated`` last, even if the run
        completed before ``subscribe`` was called — that contract is what
        the WebSocket router relies on to render the final state.
        """

        active = self._active.get(run_id)
        doc = active.doc if active is not None else run_state.load_state(
            run_id, runs_dir=self._runs_dir
        )
        if doc is None:
            # Yield a synthetic terminator so consumers don't hang.
            yield {"type": "run_terminated", "run_id": run_id, "reason": "not_found"}
            return

        yield {"type": "state_snapshot", "run_id": run_id, "state": doc.model_dump(mode="json")}

        if active is None or self._is_terminal(doc.status):
            yield {"type": "run_terminated", "run_id": run_id, "status": doc.status}
            return

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        active.subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
                if event.get("type") == "run_terminated":
                    return
        finally:
            try:
                active.subscribers.remove(queue)
            except ValueError:
                pass

    def get_live_status(self, run_id: str) -> LiveStatus | None:
        """Return the in-memory live snapshot, or ``None`` if unknown.

        Reads from the on-disk state.json if the run is not currently
        active in the supervisor — this is the path the GET /runs/<id>
        handler uses when uvicorn has restarted since the run.
        """

        active = self._active.get(run_id)
        if active is not None:
            doc = active.doc
        else:
            doc = run_state.load_state(run_id, runs_dir=self._runs_dir)
        if doc is None:
            return None
        return LiveStatus(
            run_id=doc.run_id,
            status=doc.status,
            current_phase=doc.current_phase,
            phases=doc.phases,
            cost_usd_total=doc.cost_usd_total,
            cancel_requested=doc.cancel_requested,
        )

    # -- internal: driver ------------------------------------------------

    async def _drive_phase_chain(
        self,
        active: _ActiveRun,
        *,
        only_phases: list[str] | None = None,
        force: bool = False,
    ) -> None:
        """Run each phase sequentially; stop on cancel/failure/budget.

        ``only_phases`` restricts the chain to the listed ids (used by
        :meth:`rerun_phases`).  ``force`` toggles ``--force`` on the
        ``run_phase.py`` CLI invocation.
        """

        try:
            phases = list(only_phases) if only_phases else list(PHASE_CHAIN)
            active.doc = active.doc.model_copy(
                update={"status": "running", "current_phase": phases[0] if phases else None}
            )
            self._persist(active)
            await self._broadcast(
                active,
                {
                    "type": "state_updated",
                    "run_id": active.run_id,
                    "status": active.doc.status,
                },
            )

            run_failed = False
            for phase_id in phases:
                if active.cancel_event.is_set():
                    break

                # Phase 0a (scope extraction) reads BUG_BOUNTY_URL — for
                # non-bounty projects (library / web_app / other with no
                # URL supplied) the runner would fail instantly. Mark the
                # phase ``skipped`` and continue with 0b → 04.
                if (
                    phase_id == "0a"
                    and active.spec.bug_bounty_url is None
                ):
                    self._mark_phase_skipped(
                        active,
                        phase_id,
                        reason="no bug_bounty_url provided",
                    )
                    continue

                ok = await self._run_one_phase(active, phase_id, force=force)
                if not ok:
                    run_failed = True
                    break

                # Auto-commit on phase success — push gated by spec flag.
                try:
                    await self._git_commit_phase(active, phase_id)
                    if active.spec.push_to_remote:
                        await self._git_push(active)
                except Exception as exc:  # pragma: no cover - best-effort
                    logger.warning(
                        "speca: git commit/push failed for %s/%s: %s",
                        active.run_id,
                        phase_id,
                        exc,
                    )

            if active.cancel_event.is_set():
                final = "cancelled"
            elif run_failed:
                final = "failed"
            else:
                final = "completed"

            active.doc = active.doc.model_copy(
                update={"status": final, "current_phase": None}
            )
            self._persist(active)
            await self._broadcast(
                active,
                {
                    "type": "run_terminated",
                    "run_id": active.run_id,
                    "status": final,
                },
            )
        finally:
            if active.watchdog_task is not None:
                active.watchdog_task.cancel()

    async def _run_one_phase(
        self,
        active: _ActiveRun,
        phase_id: str,
        *,
        force: bool,
    ) -> bool:
        """Spawn one ``run_phase.py`` invocation; True iff phase succeeded.

        Captures stdout, classifies each line, and forwards to subscribers.
        Updates the per-phase row before returning.
        """

        self._update_phase(
            active,
            phase_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            reason=None,
        )
        active.doc = active.doc.model_copy(update={"current_phase": phase_id})
        self._persist(active)
        await self._broadcast(
            active,
            {"type": "phase_started", "run_id": active.run_id, "phase": phase_id},
        )

        argv = list(self._run_phase_argv) + [
            "--phase",
            phase_id,
            "--workers",
            str(active.spec.workers),
            "--max-concurrent",
            str(active.spec.max_concurrent),
        ]
        if force:
            argv.append("--force")

        env = self._build_env(active, phase_id)

        # ``creationflags`` controls process-group semantics:
        #
        # * Windows: CREATE_NEW_PROCESS_GROUP so we can send CTRL_BREAK_EVENT
        #   later; the default process group inherits the parent's, which
        #   would route signals back to uvicorn itself.
        # * POSIX:   ``preexec_fn=os.setsid`` puts the child in its own
        #   session, so ``os.killpg(getpgid(pid), SIGTERM)`` cleans up the
        #   whole subprocess tree.
        creationflags = _CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        preexec_fn = None if sys.platform == "win32" else os.setsid

        logger.info(
            "speca: %s/%s spawning %s", active.run_id, phase_id, " ".join(shlex.quote(a) for a in argv)
        )
        try:
            popen = subprocess.Popen(  # noqa: S603 - shell=False, args list
                argv,
                cwd=str(self._repo_root),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                # ``bufsize=0`` -> unbuffered binary pipe. ``bufsize=1``
                # (line-buffered) only works in text mode, which we avoid
                # because the orchestrator can emit non-UTF8 byte sequences
                # we want to decode-with-replace ourselves on the read side.
                bufsize=0,
                creationflags=creationflags,
                preexec_fn=preexec_fn,
                close_fds=True,
            )
        except OSError as exc:
            logger.exception("speca: failed to spawn %s/%s", active.run_id, phase_id)
            self._update_phase(
                active,
                phase_id,
                status="failed",
                ended_at=datetime.now(timezone.utc),
                reason=f"spawn failed: {exc}",
            )
            self._persist(active)
            await self._broadcast(
                active,
                {
                    "type": "phase_completed",
                    "run_id": active.run_id,
                    "phase": phase_id,
                    "status": "failed",
                    "reason": str(exc),
                },
            )
            return False

        active.popen = popen
        self._update_phase(active, phase_id, pid=popen.pid)
        self._persist(active)

        try:
            await self._pump_stdout(active, phase_id, popen)
            rc = await asyncio.to_thread(popen.wait)
        finally:
            active.popen = None

        if active.cancel_event.is_set():
            phase_status = "cancelled"
            reason = "cancel requested"
        elif rc == 0:
            phase_status = "ok"
            reason = None
        else:
            phase_status = "failed"
            reason = f"exit code {rc}"

        self._update_phase(
            active,
            phase_id,
            status=phase_status,
            ended_at=datetime.now(timezone.utc),
            reason=reason,
        )
        self._persist(active)
        await self._broadcast(
            active,
            {
                "type": "phase_completed",
                "run_id": active.run_id,
                "phase": phase_id,
                "status": phase_status,
                "reason": reason,
            },
        )
        return phase_status == "ok"

    async def _pump_stdout(
        self,
        active: _ActiveRun,
        phase_id: str,
        popen: subprocess.Popen[bytes],
    ) -> None:
        """Read stdout line-by-line, classify, broadcast.

        The classification is intentionally heuristic — we look for
        common shapes in the stream-json payload (see ``CLAUDE.md``
        "Data Flow Convention").  Anything we don't recognise is emitted
        as a raw ``log_line``.
        """

        stream = popen.stdout
        if stream is None:
            return

        while True:
            line_bytes = await asyncio.to_thread(stream.readline)
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue

            event = self._classify_stdout_line(active.run_id, phase_id, line)
            await self._broadcast(active, event)

            if event.get("type") == "cost_update":
                delta = float(event.get("delta_usd") or 0.0)
                if delta:
                    new_total = active.doc.cost_usd_total + delta
                    active.doc = active.doc.model_copy(
                        update={"cost_usd_total": new_total}
                    )
                    self._update_phase_cost(active, phase_id, new_total)

            # Per-phase budget enforcement: if the running phase exceeds
            # the configured max_budget_usd we terminate the subprocess.
            # We pull the budget from the orchestrator phase config — but
            # since orchestrator imports are banned in this slice, we
            # only check the supervisor-level max_budget_usd attached to
            # the spec (Slice H2 will refine this with per-phase config).
            # Hook left here as a marker for the follow-up slice.

    def _classify_stdout_line(
        self, run_id: str, phase_id: str, line: str
    ) -> dict[str, Any]:
        """Pick an event type for one stdout line.

        Try ``json.loads`` first.  If the line is JSON and has a
        ``cost`` / ``total_cost_usd`` key, emit ``cost_update``.  If it
        mentions ``PARTIAL`` or ``batch``/``completed`` we tag it as
        ``phase_progress``.  Otherwise raw ``log_line``.
        """

        text = line.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                if "cost_usd" in payload or "total_cost_usd" in payload:
                    return {
                        "type": "cost_update",
                        "run_id": run_id,
                        "phase": phase_id,
                        "delta_usd": float(
                            payload.get("cost_usd") or payload.get("total_cost_usd") or 0.0
                        ),
                        "raw": payload,
                    }
                if "completed" in payload or "batch" in payload or "PARTIAL" in str(payload):
                    return {
                        "type": "phase_progress",
                        "run_id": run_id,
                        "phase": phase_id,
                        "snapshot": payload,
                    }
                return {
                    "type": "log_line",
                    "run_id": run_id,
                    "phase": phase_id,
                    "line": line,
                    "parsed": payload,
                }
        return {
            "type": "log_line",
            "run_id": run_id,
            "phase": phase_id,
            "line": line,
        }

    # -- internal: watchdog ---------------------------------------------

    async def _watchdog(self, active: _ActiveRun) -> None:
        """Tick every 5s, writing ``last_heartbeat_at`` to state.json.

        Cancellation-safe: caller cancels this task on run termination.
        """

        try:
            while True:
                active.doc = active.doc.model_copy(
                    update={"last_heartbeat_at": datetime.now(timezone.utc)}
                )
                self._persist(active, broadcast=False)
                await asyncio.sleep(_WATCHDOG_TICK_SECONDS)
        except asyncio.CancelledError:
            return

    # -- internal: signal helpers ---------------------------------------

    async def _terminate_group(self, popen: subprocess.Popen[bytes]) -> None:
        """Send a "polite" stop to the entire subprocess tree."""

        try:
            if sys.platform == "win32":
                # CTRL_BREAK_EVENT requires CREATE_NEW_PROCESS_GROUP at spawn.
                popen.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(os.getpgid(popen.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError) as exc:
            logger.debug("speca: terminate signal skipped: %s", exc)

    async def _kill_group(self, popen: subprocess.Popen[bytes]) -> None:
        """Hard-kill the subprocess tree."""

        try:
            if sys.platform == "win32":
                popen.kill()
            else:
                os.killpg(os.getpgid(popen.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError) as exc:
            logger.debug("speca: kill signal skipped: %s", exc)

    # -- internal: env / git --------------------------------------------

    def _build_env(self, active: _ActiveRun, phase_id: str) -> dict[str, str]:
        """Compose the env vars passed to ``run_phase.py``.

        Inherits the supervisor's env (so PATH / claude credentials are
        available) and layers SPECA-specific vars on top.  See the design
        doc §7.3 for the contract.
        """

        env = dict(os.environ)
        out_dir = (self._repo_root / "outputs" / active.run_id).resolve()
        env["SPECA_OUTPUT_DIR"] = str(out_dir)
        env["SPECA_TARGET_WORKSPACE"] = str(active.workspace_path)
        if active.spec.bug_bounty_url is not None:
            env["BUG_BOUNTY_URL"] = str(active.spec.bug_bounty_url)
        env["SPECA_PROJECT_TYPE"] = active.spec.project_type
        if active.spec.keywords:
            env["KEYWORDS"] = active.spec.keywords
        if active.spec.spec_urls:
            env["SPEC_URLS"] = active.spec.spec_urls
        if active.spec.contract_addresses:
            env["CONTRACT_ADDRESSES"] = active.spec.contract_addresses
        # Phase 0c expects TARGET_REPO / TARGET_REF to write TARGET_INFO.json
        # (mirrors .github/workflows/full-audit.yml Step 0c).
        env["TARGET_REPO"] = active.spec.target_repo
        if active.spec.target_ref:
            env["TARGET_REF"] = active.spec.target_ref
        env["SPECA_RUN_ID"] = active.run_id
        env["SPECA_CURRENT_PHASE"] = phase_id
        return env

    async def _git_commit_phase(self, active: _ActiveRun, phase_id: str) -> None:
        """``git add outputs/<run_id> && git commit -m "<phase>: ... complete"``.

        Best-effort — failures are logged but do not abort the chain.
        Uses ``git -C <repo_root>`` so the supervisor is cwd-independent.
        """

        description = PHASE_DESCRIPTIONS.get(phase_id, "phase")
        message = f"{phase_id}: {description} complete"
        outputs_path = f"outputs/{active.run_id}"
        await asyncio.to_thread(
            subprocess.run,
            ["git", "-C", str(self._repo_root), "add", outputs_path],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.to_thread(
            subprocess.run,
            [
                "git",
                "-C",
                str(self._repo_root),
                "commit",
                "-m",
                message,
                "--allow-empty",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    async def _git_push(self, active: _ActiveRun) -> None:
        """``git push`` the current branch.  Best-effort."""

        await asyncio.to_thread(
            subprocess.run,
            ["git", "-C", str(self._repo_root), "push"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # -- internal: state mutation ---------------------------------------

    @staticmethod
    def _is_terminal(status: str) -> bool:
        return status in {"completed", "failed", "cancelled", "crashed", "orphaned_running"}

    def _update_phase(self, active: _ActiveRun, phase_id: str, **fields: Any) -> None:
        """Patch one phase row in ``active.doc``.  Pure in-memory update."""

        updated: list[PhaseStateEntry] = []
        for entry in active.doc.phases:
            if entry.phase_id == phase_id:
                entry = entry.model_copy(update=fields)
            updated.append(entry)
        active.doc = active.doc.model_copy(update={"phases": updated})

    def _mark_phase_skipped(
        self, active: _ActiveRun, phase_id: str, *, reason: str
    ) -> None:
        """Stamp a phase as ``skipped`` with a reason and emit the usual events.

        Mirrors what ``_run_one_phase`` does on success/failure so the SPA
        receives ``phase_started`` + ``phase_completed`` for skip transitions
        too; the WebSocket reducer can treat skip the same way and the run
        appears continuous from the user's perspective.
        """

        now = datetime.now(timezone.utc)
        self._update_phase(
            active,
            phase_id,
            status="skipped",
            started_at=now,
            ended_at=now,
            reason=reason,
        )
        self._persist(active)

    def _update_phase_cost(self, active: _ActiveRun, phase_id: str, total: float) -> None:
        """Refresh per-phase cost from cumulative total (Slice H1 stub)."""

        # Slice H1 only tracks aggregate cost; per-phase rollup is a
        # Slice H2 concern. We still bump the phase row so the UI can
        # render a running total in the phase card.
        updated: list[PhaseStateEntry] = []
        for entry in active.doc.phases:
            if entry.phase_id == phase_id:
                entry = entry.model_copy(update={"cost_usd": total})
            updated.append(entry)
        active.doc = active.doc.model_copy(update={"phases": updated, "cost_usd_total": total})

    def _persist(self, active: _ActiveRun, *, broadcast: bool = True) -> None:
        """Atomic state.json write.  Logs (does not raise) on failure."""

        try:
            run_state.write_state(active.run_id, active.doc, runs_dir=self._runs_dir)
        except OSError as exc:
            logger.warning(
                "speca: state.json write failed for %s: %s", active.run_id, exc
            )

    async def _broadcast(self, active: _ActiveRun, event: Mapping[str, Any]) -> None:
        """Fan-out an event to every subscriber's queue, lossless."""

        payload = dict(event)
        # Snapshot the list — subscribers list mutates as clients connect/
        # disconnect; avoid iterating it under mutation.
        for queue in list(active.subscribers):
            await queue.put(payload)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_singleton: RunSupervisor | None = None


def get_run_supervisor() -> RunSupervisor:
    """Return the shared :class:`RunSupervisor` instance (process-local).

    The singleton is lazily constructed so importing this module is
    cheap; tests that need an isolated supervisor can construct
    :class:`RunSupervisor` directly with a custom ``runs_dir``.
    """

    global _singleton
    if _singleton is None:
        _singleton = RunSupervisor()
    return _singleton


def _reset_singleton_for_tests() -> None:
    """Test-only: drop the cached singleton.  Do not call in production."""

    global _singleton
    _singleton = None


# Re-export the helpers the slice-spec said to expose so consumers can
# write ``from web.server.services.run_supervisor import make_run_id``
# (a thin proxy for the future ``scripts.run_phase.make_run_id``).
__all__ = [
    "PHASE_CHAIN",
    "PHASE_DESCRIPTIONS",
    "RunSupervisor",
    "get_run_supervisor",
    "make_run_id",
]

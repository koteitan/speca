"""HTTP routes for the Runs slice.

Slice G + Slice B1 endpoints:

* ``GET  /api/runs``                       — list of :class:`RunSummary`, newest first
* ``GET  /api/runs/{run_id}``              — full :class:`RunDetail`
* ``POST /api/runs``                       — spawn a new run (202 Accepted)
* ``POST /api/runs/{run_id}/cancel``       — cooperative cancel
* ``POST /api/runs/{run_id}/rerun``        — rerun a subset of phases

The actual indexing/parsing is done in
:mod:`web.server.services.run_index`; the mutating endpoints delegate to
:mod:`web.server.services.run_supervisor` (subprocess + branch ownership)
and :mod:`web.server.services.workspace_manager` (bare cache + worktree).
Router code stays thin — its job is to validate, dispatch, and map
domain exceptions to the canonical ``{"error": "...", ...}`` envelope.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from web.server.schemas.run_state import RunStartSpec
from web.server.schemas.runs import (
    CancelResponse,
    RerunRequest,
    RerunResponse,
    RunDetail,
    RunStartResponse,
    RunSummary,
)
from web.server.services import run_state as run_state_svc
from web.server.services import run_supervisor as run_supervisor_svc
from web.server.services import workspace_manager as workspace_manager_svc
from web.server.services.run_index import get_run_detail, list_runs
from web.server.services.workspace_manager import (
    CloneFailed,
    RefNotFound,
    WorkspaceError,
)

# We register the router under ``/api`` and define explicit paths so each
# endpoint reads top-down with its full URL — easier to grep than relying
# on a ``/api/runs`` prefix.
router = APIRouter(prefix="/api", tags=["runs"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ``owner/repo`` (or ``owner/repo.git``) — matches the GitHub canonical
# shape. We deliberately reject full URLs at this layer; the supervisor
# composes the ``https://github.com/<x>.git`` URL itself, and accepting
# both shapes here would let a caller smuggle e.g. an ``ssh://`` URL past
# the URL forbidden-char check inside :class:`WorkspaceManager`.
_TARGET_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(?:\.git)?$")

# Canonical phase set accepted by ``POST /api/runs/<id>/rerun``. Kept in
# sync with :data:`run_supervisor_svc.PHASE_CHAIN`; declared here as a
# frozenset so a typo'd ``--rerun bogus`` aborts at the router boundary.
_ALLOWED_PHASES: frozenset[str] = frozenset(run_supervisor_svc.PHASE_CHAIN)


def _target_slug(target_repo: str) -> str:
    """``owner/repo`` -> ``owner-repo`` (filesystem-safe slug).

    Used for the branch name (``audit/<slug>/<run_id>``) so a glance at
    ``git branch --list`` reveals which target the run belongs to without
    cross-referencing state.json.
    """

    return re.sub(r"[^A-Za-z0-9._-]", "-", target_repo)


def _validate_target_repo(target_repo: str) -> None:
    """422 if ``target_repo`` is not ``owner/repo`` shaped.

    Raised *before* we touch the WorkspaceManager so a typo never spawns
    a doomed ``git clone --bare``.
    """

    if not _TARGET_REPO_RE.match(target_repo):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_target_repo",
                "message": (
                    "target_repo must match 'owner/repo' (optionally '.git')"
                ),
            },
        )


# ---------------------------------------------------------------------------
# Read endpoints (Slice G — unchanged)
# ---------------------------------------------------------------------------


@router.get("/runs", response_model=list[RunSummary])
def get_runs() -> list[RunSummary]:
    """Return the most recent runs (capped, newest first)."""

    return list_runs()


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str) -> RunDetail:
    """Return the detail payload for a single run."""

    detail = get_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return detail


# ---------------------------------------------------------------------------
# Write endpoints (Slice B1)
# ---------------------------------------------------------------------------


@router.post("/runs", response_model=RunStartResponse, status_code=202)
async def start_run(spec: RunStartSpec) -> RunStartResponse:
    """Spawn a new audit run and return its identifiers (202 Accepted).

    Flow:

    1. Validate ``target_repo`` shape (router-side; cheap).
    2. ``ensure_bare_cache`` — idempotent ``git clone --bare`` (or fetch).
    3. ``create_worktree`` — materialise a worktree for the new run.
    4. ``supervisor.start_run`` — spawn the phase-chain driver task.
    5. Return the run_id immediately; the chain runs in the background.

    Errors are translated to the canonical ``{"error": "...", ...}``
    envelope: 422 for invalid spec shape, 502 for upstream clone failure,
    422 again for an unknown ``target_ref``.
    """

    _validate_target_repo(spec.target_repo)

    supervisor = run_supervisor_svc.get_run_supervisor()
    workspace_mgr = workspace_manager_svc.WorkspaceManager()

    # The supervisor needs the *workspace path*, not the manager itself;
    # we own the bare-cache + worktree lifecycle in the router so the
    # supervisor stays single-purpose (process / state).
    target_url = f"https://github.com/{spec.target_repo}.git"
    try:
        workspace_mgr.ensure_bare_cache(target_url)
    except CloneFailed as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "clone_failed", "message": str(exc)},
        ) from exc
    except WorkspaceError as exc:
        # Any other validation/parse error from the workspace layer is
        # caller-fault (bad URL chars, empty fields, ...).
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_workspace_input", "message": str(exc)},
        ) from exc

    # Mint the run_id *before* the worktree call so the worktree path is
    # bound to the supervisor's view of the run from the very first step.
    run_id = run_supervisor_svc.make_run_id(
        target_repo=spec.target_repo,
        bug_bounty_url=str(spec.bug_bounty_url) if spec.bug_bounty_url else None,
    )

    try:
        workspace_path = workspace_mgr.create_worktree(
            run_id=run_id,
            repo_url=target_url,
            ref=spec.target_ref,
        )
    except RefNotFound as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "ref_not_found", "message": str(exc)},
        ) from exc
    except CloneFailed as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "worktree_failed", "message": str(exc)},
        ) from exc

    # NB: ``RunSupervisor.start_run`` (H1) takes ``(spec, workspace_path,
    # target_info=None)`` — *not* the WorkspaceManager. It also mints its
    # own run_id internally, so the id we computed above is **only** used
    # for the worktree path. We surface the supervisor's id in the
    # response so the UI is talking about the same run going forward.
    supervisor_run_id = await supervisor.start_run(
        spec, workspace_path=workspace_path
    )

    branch_name = f"audit/{_target_slug(spec.target_repo)}/{supervisor_run_id}"

    state = run_state_svc.load_state(supervisor_run_id)
    started_at = (
        state.last_heartbeat_at
        if state is not None and state.last_heartbeat_at is not None
        else datetime.now(timezone.utc)
    )

    return RunStartResponse(
        run_id=supervisor_run_id,
        branch_name=branch_name,
        workspace_path=str(workspace_path),
        started_at=started_at,
    )


@router.post("/runs/{run_id}/cancel", response_model=CancelResponse)
async def cancel_run(run_id: str) -> CancelResponse:
    """Request cooperative cancellation of ``run_id``.

    Returns:

    * 200 ``cancel_requested`` if the supervisor still owns the run
      (SIGTERM dispatched, will escalate to SIGKILL after 10s).
    * 200 ``already_finished`` if the run is on disk but terminal —
      idempotent; UI can show "already finished" without re-fetching.
    * 404 ``run_not_found`` if no ``state.json`` exists at all.
    """

    supervisor = run_supervisor_svc.get_run_supervisor()
    live = supervisor.get_live_status(run_id)
    if live is None:
        # No supervisor entry and no state.json. Fall back to the
        # manifest-derived index — if a legacy run exists on disk we
        # treat cancel as a no-op success ("already finished") rather
        # than 404, so the UI does not block on idempotent retries.
        if get_run_detail(run_id) is not None:
            return CancelResponse(run_id=run_id, status="already_finished")
        raise HTTPException(
            status_code=404,
            detail={"error": "run_not_found", "run_id": run_id},
        )

    # If the run is on disk but no longer active (e.g. completed before
    # the cancel POST hit us), report ``already_finished`` rather than
    # spawning a phantom cancel.
    if run_id not in supervisor._active:  # noqa: SLF001 - read-only check
        return CancelResponse(run_id=run_id, status="already_finished")

    await supervisor.cancel_run(run_id)
    return CancelResponse(run_id=run_id, status="cancel_requested")


@router.post("/runs/{run_id}/rerun", response_model=RerunResponse)
async def rerun_run(run_id: str, req: RerunRequest) -> RerunResponse:
    """Re-execute the listed phases (``--force``) for a terminal run.

    422 when any requested phase is unknown; 404 if the run does not
    exist; 409 if the run is still executing (the caller must cancel
    first). On success the supervisor schedules a fresh phase-chain task
    against the same ``run_id`` (no new id is minted on rerun).
    """

    invalid = [p for p in req.phases if p not in _ALLOWED_PHASES]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_phases", "invalid": invalid},
        )

    state = run_state_svc.load_state(run_id)
    if state is None:
        # Legacy runs created before the H1 RunSupervisor only have a
        # ``manifest.json``. Promote them on first rerun so the supervisor
        # has the state.json it needs to drive a fresh phase chain.
        legacy_detail = get_run_detail(run_id)
        if legacy_detail is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "run_not_found", "run_id": run_id},
            )

        from ..schemas.run_state import RunStateDoc

        state = RunStateDoc(
            run_id=run_id,
            status="completed",
            last_heartbeat_at=datetime.now(timezone.utc),
        )
        run_state_svc.write_state(run_id, state)

    if state.status == "running":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "still_running",
                "message": "cancel the run before rerunning",
            },
        )

    supervisor = run_supervisor_svc.get_run_supervisor()
    await supervisor.rerun_phases(run_id, req.phases)
    return RerunResponse(run_id=run_id, rerun_phases=req.phases)

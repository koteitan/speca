"""Pydantic schemas for the Runs API.

These models mirror the lenient JSON shape produced by
``scripts/run_phase.py`` writing to ``.speca/runs/<run_id>/manifest.json``.
Backwards/forwards compatibility is achieved by:

* defaulting every field, so a half-written manifest still validates
* deriving ``status`` / ``target_slug`` from heuristics (see
  :mod:`web.server.services.run_status`) rather than requiring orchestrator
  to populate explicit fields the manifest schema does not yet carry
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RunStatus = Literal["ok", "running", "failed", "cancelled"]
PhaseStatus = Literal["ok", "running", "pending", "failed", "cancelled", "skipped"]


class RunSummary(BaseModel):
    """One row in ``GET /api/runs``.

    Mirrors the manifest at a high level — only fields the list view needs.
    """

    model_config = ConfigDict(extra="allow")

    run_id: str
    started_at: datetime
    ended_at: datetime | None = None
    target_slug: str | None = None
    status: RunStatus
    cost_usd_total: float = 0.0
    phases_completed: list[str] = Field(default_factory=list)


class PhaseRow(BaseModel):
    """One phase row in ``GET /api/runs/<id>``.

    ``status`` is derived from ``phases_completed`` + the manifest's current
    state; durations are best-effort and may be ``None`` for phases that
    never started.
    """

    model_config = ConfigDict(extra="allow")

    phase_id: str
    status: PhaseStatus
    duration_seconds: float | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class RunDetail(RunSummary):
    """Run detail payload — superset of :class:`RunSummary`.

    Adds the per-phase rows + spec/prompt provenance for the detail page.
    """

    phases: list[PhaseRow] = Field(default_factory=list)
    target_info: dict | None = None
    spec_sources: list[str] = Field(default_factory=list)
    prompt_shas: dict[str, str] = Field(default_factory=dict)
    branch_name: str | None = None


# ---------------------------------------------------------------------------
# Slice B1: POST /api/runs + cancel + rerun
# ---------------------------------------------------------------------------
#
# ``RunStartSpec`` (the *input* payload for POST /api/runs) lives in
# :mod:`web.server.schemas.run_state` because the supervisor also accepts
# it directly. Routers import that schema for the request body and the
# response models defined below for the response body.


class RunStartResponse(BaseModel):
    """Body returned by ``POST /api/runs`` on a successful spawn.

    202 Accepted — the subprocess chain is driven in the background, this
    response only carries the freshly minted ``run_id`` plus the metadata
    the UI needs to render the "run started" toast (branch name +
    workspace path) without round-tripping ``GET /api/runs/<id>``.
    """

    model_config = ConfigDict(extra="allow")

    run_id: str
    branch_name: str
    workspace_path: str
    started_at: datetime


class RerunRequest(BaseModel):
    """Body accepted by ``POST /api/runs/<run_id>/rerun``.

    The supervisor's :meth:`rerun_phases` enforces that the run is
    terminal; the router performs additional validation (``phases`` must
    be a non-empty subset of the canonical phase set) so we 422 *before*
    touching the supervisor.
    """

    phases: list[str] = Field(
        min_length=1,
        description="phase ids to rerun, e.g. ['03','04']",
    )
    force: bool = True


class RerunResponse(BaseModel):
    """Body returned by ``POST /api/runs/<run_id>/rerun``."""

    run_id: str
    rerun_phases: list[str]


class CancelResponse(BaseModel):
    """Body returned by ``POST /api/runs/<run_id>/cancel``.

    ``status`` distinguishes the three observable cancel outcomes:

    * ``cancel_requested`` — SIGTERM dispatched, supervisor is acting on it.
    * ``cancelled``        — already terminal as cancelled (rare race).
    * ``already_finished`` — run completed/failed before cancel arrived.
    """

    run_id: str
    status: str

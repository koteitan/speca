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

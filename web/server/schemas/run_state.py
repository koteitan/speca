"""Pydantic schemas for the run lifecycle / state machine (Slice H1).

``RunStateDoc`` is the on-disk shape persisted at
``.speca/runs/<run_id>/state.json`` by :mod:`web.server.services.run_state`.
``RunStartSpec`` is the input payload accepted by the (future, Slice H3)
``POST /api/runs`` endpoint and used internally by
:class:`web.server.services.run_supervisor.RunSupervisor` when spawning a
phase chain.

The schemas are deliberately additive to :mod:`web.server.schemas.runs` —
``runs.py`` mirrors the legacy ``manifest.json`` shape (lenient, every
field optional), whereas this module describes the *new* state.json
substrate used by the supervisor. They overlap conceptually but the on-
disk roles are distinct so we keep them in separate files to make
migration easier later.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# ---------------------------------------------------------------------------
# Status enums
# ---------------------------------------------------------------------------

PhaseState = Literal[
    "queued",
    "running",
    "ok",
    "failed",
    "cancelled",
    "skipped",
]

RunState = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "crashed",
    "orphaned_running",
]


# ---------------------------------------------------------------------------
# Per-phase state row
# ---------------------------------------------------------------------------


class PhaseStateEntry(BaseModel):
    """One row in :class:`RunStateDoc.phases`.

    ``pid`` is filled while the phase is ``running`` and intentionally
    preserved on terminate so post-hoc tooling can correlate the
    ``state.json`` row with stream-json log files (the orchestrator embeds
    PID in some log lines).
    """

    model_config = ConfigDict(extra="allow")

    phase_id: str
    status: PhaseState = "queued"
    pid: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    cost_usd: float = 0.0
    reason: str | None = None


# ---------------------------------------------------------------------------
# Run state document — persisted as state.json
# ---------------------------------------------------------------------------


class RunStateDoc(BaseModel):
    """Full state.json payload for a single run.

    The supervisor writes this file at every significant transition
    (phase start/end, cancel request, watchdog tick).  Reads at startup
    are tolerant of partial / missing fields — see
    :func:`web.server.services.run_state.load_state`.

    ``owner_pid`` lets a freshly started supervisor reconcile orphan runs:
    if a state.json says ``status="running"`` but ``owner_pid`` is dead,
    the run is re-tagged as ``"crashed"``.
    """

    model_config = ConfigDict(extra="allow")

    run_id: str
    status: RunState = "queued"
    current_phase: str | None = None
    phases: list[PhaseStateEntry] = Field(default_factory=list)
    cost_usd_total: float = 0.0
    cancel_requested: bool = False
    owner_pid: int = Field(default_factory=os.getpid)
    last_heartbeat_at: datetime | None = None
    schema_version: int = 1


# ---------------------------------------------------------------------------
# Inputs accepted by the supervisor's start_run() / future POST /api/runs
# ---------------------------------------------------------------------------


ProjectType = Literal["smart_contract", "web_app", "library", "other"]


class RunStartSpec(BaseModel):
    """Form payload that kicks off a new audit run.

    Mirrors the ``workflow_dispatch`` inputs of ``.github/workflows/full-
    audit.yml`` (see ``docs/UI_DESIGN.md`` §4.3) — keep the field names /
    defaults in sync so the form is portable between UI and CI.

    ``project_type`` widens SPECA beyond smart-contract audits. The default
    keeps backward compatibility; ``contract_addresses`` is repurposed as
    generic "in-scope assets" text for non-contract projects so the field
    survives the broader vocabulary without a schema rename.

    ``bug_bounty_url`` is optional because non-bounty audits (internal
    reviews, OSS libraries with no formal program) still need a way to
    start.
    """

    model_config = ConfigDict(extra="ignore")

    project_type: ProjectType = "smart_contract"
    bug_bounty_url: HttpUrl | None = None
    target_repo: str
    target_ref: str | None = None
    contract_addresses: str | None = None
    spec_urls: str | None = None
    keywords: str | None = None
    workers: int = Field(default=4, ge=1, le=32)
    max_concurrent: int = Field(default=64, ge=1, le=256)
    push_to_remote: bool = False


# ---------------------------------------------------------------------------
# Live snapshot returned by GET /api/runs/<id> (supervisor-side complement
# to the manifest-based RunDetail in schemas/runs.py)
# ---------------------------------------------------------------------------


class LiveStatus(BaseModel):
    """Lightweight liveness snapshot the supervisor can return in-memory.

    Composed only of fields the supervisor maintains in RAM — file-system
    fields like ``branch_name`` / ``target_info`` live on
    :class:`web.server.schemas.runs.RunDetail` instead.
    """

    model_config = ConfigDict(extra="allow")

    run_id: str
    status: RunState
    current_phase: str | None
    phases: list[PhaseStateEntry]
    cost_usd_total: float = 0.0
    cancel_requested: bool = False


# ---------------------------------------------------------------------------
# WebSocket / SSE stream events (kept flat as the design doc prescribes —
# discriminated union would force schema churn whenever a new event type
# is added)
# ---------------------------------------------------------------------------


class StreamEvent(BaseModel):
    """Envelope for every event broadcast to subscribers.

    The ``type`` field is the discriminator the SPA branches on. Concrete
    payload fields are intentionally ``extra="allow"`` so that adding a
    new event variant in the supervisor does not require updating this
    schema first.

    Canonical types emitted by Slice H1:

    * ``state_snapshot``     — initial event on subscribe()
    * ``phase_started``      — current_phase transition
    * ``phase_progress``     — PARTIAL counter / batch ticks
    * ``phase_completed``    — phase reached terminal status
    * ``log_line``           — raw or parsed stdout line
    * ``cost_update``        — running cost_usd_total delta
    * ``state_updated``      — generic state.json change (post-write)
    * ``run_terminated``     — last event before queue is drained
    """

    model_config = ConfigDict(extra="allow")

    type: str

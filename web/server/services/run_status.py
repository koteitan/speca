"""Heuristic status derivation for SPECA run manifests.

The manifest schema is intentionally lenient (see
``web/server/schemas/runs.py``) — fields like ``status`` and per-phase
durations are not part of the on-disk contract. We derive them here from
the few fields the orchestrator does write (``phases_completed``, ``notes``,
``ended_at``, ``started_at``, ``target_info``).

Keep this module **pure** (no I/O, no orchestrator imports) so it stays
trivially testable and the JSON shape from ``run_index.py`` is the only
input it consumes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from web.server.schemas.runs import PhaseRow, PhaseStatus, RunStatus

# Canonical ordering used when we have to fill in missing phases. Mirrors
# CLAUDE.md "Pipeline Phases" — keep in sync if a new phase is added.
KNOWN_PHASE_ORDER: tuple[str, ...] = ("01a", "01b", "01e", "02c", "03", "04")

# A run that started this long ago without an ``ended_at`` is considered
# stale (orchestrator crashed, machine rebooted, ...). One hour matches the
# typical full-pipeline ceiling — anything longer is almost certainly dead.
_RUNNING_FRESHNESS = timedelta(hours=1)


def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    """Case-insensitive substring match against any needle."""

    lowered = haystack.lower()
    return any(needle in lowered for needle in needles)


def derive_run_status(
    *,
    phases_completed: list[str],
    notes: str | None,
    ended_at: datetime | None,
    started_at: datetime | None,
    now: datetime | None = None,
) -> RunStatus:
    """Decide one of ``ok | running | failed | cancelled`` for a run.

    Priority (highest first):

    1. ``notes`` mentions an error/exception/failure -> ``failed``
    2. ``notes`` mentions cancellation -> ``cancelled``
    3. ``ended_at`` is set -> ``ok``
    4. ``started_at`` is within the freshness window -> ``running``
    5. fallback -> ``cancelled`` (assume the orchestrator crashed silently)
    """

    notes_text = notes or ""
    if _contains_any(notes_text, ("error", "exception", "fail")):
        return "failed"
    if _contains_any(notes_text, ("cancelled", "canceled", "abort")):
        return "cancelled"
    if ended_at is not None:
        return "ok"

    if started_at is not None:
        anchor = now or datetime.now(timezone.utc)
        # Normalise naive datetimes to UTC so subtraction never raises.
        started_utc = started_at if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
        anchor_utc = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)
        if anchor_utc - started_utc <= _RUNNING_FRESHNESS:
            return "running"

    # Started but no ``ended_at`` and not fresh -> the orchestrator silently
    # died. Treating this as cancelled is friendlier in the list view than
    # "failed" (which implies an explicit failure mode).
    return "cancelled"


def derive_target_slug(
    *,
    run_id: str,
    target_info: dict[str, Any] | None,
) -> str | None:
    """Pick a human-friendly target label.

    ``target_info.target_repo`` is preferred — it is the explicit field the
    orchestrator writes for runs that resolved a target. Otherwise we fall
    back to the trailing segment of the run id (e.g.
    ``2026-05-11T13-11-49Z-994f630-unknown`` -> ``unknown``).
    """

    if target_info and isinstance(target_info, dict):
        repo = target_info.get("target_repo")
        if isinstance(repo, str) and repo:
            return repo

    if "-" in run_id:
        return run_id.rsplit("-", 1)[-1] or None
    return run_id or None


def derive_branch_name(*, target_slug: str | None, run_id: str) -> str | None:
    """Reconstruct the ``audit/<target>/<run-id>`` branch name.

    The orchestrator does not record this in the manifest, but it is a
    pure function of (target_slug, run_id), so we recompute it here to
    avoid a schema migration.
    """

    if not target_slug:
        return None
    # Slashes inside a repo slug (``foo/bar``) are part of the branch shape
    # and intentionally preserved; git treats nested refs as separate
    # directories under ``refs/heads/``.
    slug = target_slug.replace(" ", "-")
    return f"audit/{slug}/{run_id}"


def derive_phase_rows(
    *,
    phases_completed: list[str],
    run_status: RunStatus,
    known_phases: tuple[str, ...] = KNOWN_PHASE_ORDER,
) -> list[PhaseRow]:
    """Build the per-phase rows for ``RunDetail``.

    Algorithm:

    * Every phase listed in ``phases_completed`` is ``ok``.
    * The first phase not in ``phases_completed`` is ``running`` iff the
      run itself is ``running``, otherwise it inherits the run status
      (failed -> failed, cancelled -> cancelled).
    * Phases after that are ``pending``.

    The union of ``known_phases`` and ``phases_completed`` is used as the
    full row set, so manifests that reference an out-of-band phase (e.g.
    a future ``05``) still render.
    """

    completed = list(dict.fromkeys(phases_completed))  # preserve order, dedupe
    extras = [p for p in completed if p not in known_phases]
    full_order = list(known_phases) + extras
    seen_completed = set(completed)

    rows: list[PhaseRow] = []
    next_status: PhaseStatus
    found_running = False
    for phase_id in full_order:
        if phase_id in seen_completed:
            rows.append(PhaseRow(phase_id=phase_id, status="ok"))
            continue

        if not found_running:
            found_running = True
            if run_status == "running":
                next_status = "running"
            elif run_status == "failed":
                next_status = "failed"
            elif run_status == "cancelled":
                next_status = "cancelled"
            else:
                # ``ok`` with un-completed phases shouldn't happen, but if
                # it does we mark the gap as ``skipped`` so the UI still
                # explains what the user is looking at.
                next_status = "skipped"
            rows.append(PhaseRow(phase_id=phase_id, status=next_status))
            continue

        rows.append(PhaseRow(phase_id=phase_id, status="pending"))

    return rows

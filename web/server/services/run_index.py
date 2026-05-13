"""Read-only index over ``.speca/runs/<run_id>/manifest.json``.

This module is the **single** place the web backend touches the on-disk
runs tree. It is deliberately decoupled from ``scripts/orchestrator/`` —
we read manifests as plain JSON so an orchestrator refactor cannot break
the API contract.

The functions return Pydantic models from :mod:`web.server.schemas.runs`,
already enriched with derived status / phase rows via
:mod:`web.server.services.run_status`.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Optional 4-hex nonce suffix introduced by the orchestrator's
# ``make_run_id`` to disambiguate same-second runs (issue #32). We strip it
# before splitting off the trailing slug so the SPA still shows e.g.
# "openlist" rather than "0a1b" for a non-bounty audit.
_NONCE_SUFFIX = re.compile(r"-([0-9a-f]{4})$")


def _extract_target_slug(run_id: str) -> str | None:
    """Return the slug portion of a run id, tolerant of either format.

    ``<ts>-<7hex>-<slug>``         (legacy)
    ``<ts>-<7hex>-<slug>-<4hex>``  (current — nonce suffix)
    """

    if not run_id:
        return None
    base = _NONCE_SUFFIX.sub("", run_id)
    last = base.rsplit("-", 1)[-1]
    return last or None

from pydantic import ValidationError

from web.server.config import SPECA_RUNS_DIR
from web.server.schemas.runs import PhaseRow, RunDetail, RunSummary
from web.server.services.run_status import (
    derive_branch_name,
    derive_phase_rows,
    derive_run_status,
    derive_target_slug,
)

logger = logging.getLogger(__name__)

# Hard upper bound on the list endpoint. The on-disk tree can grow without
# bound, but the UI only renders the most recent rows; clipping in the
# service keeps JSON payloads predictable.
MAX_LIST_ROWS = 200


def _parse_iso(value: Any) -> datetime | None:
    """Best-effort ISO-8601 parser that tolerates trailing ``Z`` and Nones."""

    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    text = value.rstrip()
    # ``datetime.fromisoformat`` only learned to handle ``Z`` in 3.11+ but
    # we want to support the older orchestrator output as well.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _load_manifest(run_dir: Path) -> dict[str, Any] | None:
    """Read ``manifest.json``, returning ``None`` on any error.

    Errors are *logged*, not raised — a corrupt manifest should not take
    down the whole list endpoint. The caller is expected to skip the row.
    """

    manifest_path = run_dir / "manifest.json"
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("speca: unable to read %s: %s", manifest_path, exc)
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("speca: malformed manifest %s: %s", manifest_path, exc)
        return None
    if not isinstance(data, dict):
        logger.warning("speca: manifest is not an object: %s", manifest_path)
        return None
    return data


def _iter_run_dirs(runs_dir: Path) -> Iterable[Path]:
    """Yield candidate run directories newest-first by mtime.

    We sort by directory mtime rather than parsing ``run_id`` because the
    timestamp is embedded in the id but not in a parser-friendly format,
    and mtime is "good enough" for the list view (the canonical ordering
    is re-applied after summaries are built, using ``started_at``).
    """

    if not runs_dir.exists():
        return []
    return sorted(
        (p for p in runs_dir.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _summary_from_manifest(
    *,
    run_dir: Path,
    manifest: dict[str, Any],
    now: datetime | None = None,
) -> RunSummary | None:
    """Build a :class:`RunSummary` from a manifest dict.

    Returns ``None`` when the manifest is too broken to summarise — i.e.
    no ``run_id`` and no ``started_at``. Anything else is best-effort.
    """

    run_id = manifest.get("run_id") or run_dir.name
    started_at = _parse_iso(manifest.get("started_at"))
    if not started_at:
        # Fall back to the directory mtime so the row still renders.
        try:
            started_at = datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return None

    ended_at = _parse_iso(manifest.get("ended_at"))
    phases_completed_raw = manifest.get("phases_completed") or []
    phases_completed = [str(p) for p in phases_completed_raw if isinstance(p, (str, int))]
    notes = manifest.get("notes")
    if notes is not None and not isinstance(notes, str):
        notes = str(notes)

    status = derive_run_status(
        phases_completed=phases_completed,
        notes=notes,
        ended_at=ended_at,
        started_at=started_at,
        now=now,
    )
    target_info = manifest.get("target_info") if isinstance(manifest.get("target_info"), dict) else None
    target_slug = derive_target_slug(run_id=run_id, target_info=target_info)
    cost = manifest.get("cost_usd_total")
    try:
        cost_value = float(cost) if cost is not None else 0.0
    except (TypeError, ValueError):
        cost_value = 0.0

    try:
        return RunSummary(
            run_id=run_id,
            started_at=started_at,
            ended_at=ended_at,
            target_slug=target_slug,
            status=status,
            cost_usd_total=cost_value,
            phases_completed=phases_completed,
        )
    except ValidationError as exc:
        logger.warning("speca: failed to build RunSummary for %s: %s", run_id, exc)
        return None


def list_runs(runs_dir: Path | None = None) -> list[RunSummary]:
    """Return all run summaries, newest first, capped at :data:`MAX_LIST_ROWS`."""

    target_dir = runs_dir or SPECA_RUNS_DIR
    now = datetime.now(timezone.utc)
    summaries: list[RunSummary] = []
    for run_dir in _iter_run_dirs(target_dir):
        manifest = _load_manifest(run_dir)
        if manifest is None:
            continue
        summary = _summary_from_manifest(run_dir=run_dir, manifest=manifest, now=now)
        if summary is None:
            continue
        summaries.append(summary)
        if len(summaries) >= MAX_LIST_ROWS * 2:
            # Safety valve: stop scanning if a runaway runs tree is found.
            break

    summaries.sort(key=lambda s: s.started_at, reverse=True)
    return summaries[:MAX_LIST_ROWS]


def get_run_detail(run_id: str, runs_dir: Path | None = None) -> RunDetail | None:
    """Return the full detail payload for a single run, or ``None`` if absent.

    Runs that were launched via the H1 RunSupervisor but never completed
    (cancelled mid-flight, crashed before finalize, or still running) only
    have ``state.json`` — the orchestrator writes ``manifest.json`` at
    finalize time. Fall back to a state.json-derived summary so the SPA
    doesn't 404 on perfectly valid mid-run rows.
    """

    target_dir = runs_dir or SPECA_RUNS_DIR
    run_dir = target_dir / run_id
    if not run_dir.is_dir():
        return None
    manifest = _load_manifest(run_dir)
    if manifest is None:
        # Try state.json (supervisor-owned). Lazy import to keep the
        # legacy manifest path zero-cost when state.json is absent too.
        try:
            from .run_state import load_state
        except Exception:  # pragma: no cover - import shield
            return None

        state = load_state(run_id, runs_dir=target_dir)
        if state is None:
            return None

        # state.run_status → RunSummary.status. Map ``orphaned_running`` /
        # ``crashed`` onto ``failed`` for the SPA which only knows the four
        # ``RunStatus`` values; the underlying state.json field still carries
        # the precise label.
        spec_status = state.status
        mapped: str
        if spec_status == "completed":
            mapped = "ok"
        elif spec_status in ("queued", "running"):
            mapped = "running"
        elif spec_status == "cancelled":
            mapped = "cancelled"
        else:
            mapped = "failed"

        phase_rows: list[PhaseRow] = []
        for entry in state.phases:
            phase_status: str
            if entry.status == "ok":
                phase_status = "ok"
            elif entry.status == "running":
                phase_status = "running"
            elif entry.status == "failed":
                phase_status = "failed"
            elif entry.status == "cancelled":
                phase_status = "cancelled"
            elif entry.status == "skipped":
                phase_status = "skipped"
            else:
                phase_status = "pending"
            duration: float | None = None
            if entry.started_at and entry.ended_at:
                duration = max(
                    0.0,
                    (entry.ended_at - entry.started_at).total_seconds(),
                )
            phase_rows.append(
                PhaseRow(
                    phase_id=entry.phase_id,
                    status=phase_status,  # type: ignore[arg-type]
                    duration_seconds=duration,
                    started_at=entry.started_at,
                    ended_at=entry.ended_at,
                )
            )

        phases_completed = [p.phase_id for p in state.phases if p.status == "ok"]
        target_slug = _extract_target_slug(run_id)

        return RunDetail(
            run_id=state.run_id,
            started_at=phase_rows[0].started_at if phase_rows else datetime.now(timezone.utc),
            ended_at=None if mapped == "running" else (
                phase_rows[-1].ended_at if phase_rows else None
            ),
            target_slug=target_slug,
            status=mapped,  # type: ignore[arg-type]
            cost_usd_total=state.cost_usd_total,
            phases_completed=phases_completed,
            phases=phase_rows,
            target_info=None,
            spec_sources=[],
            prompt_shas={},
            branch_name=derive_branch_name(
                target_slug=target_slug, run_id=state.run_id
            ),
        )

    now = datetime.now(timezone.utc)
    summary = _summary_from_manifest(run_dir=run_dir, manifest=manifest, now=now)
    if summary is None:
        return None

    phases = derive_phase_rows(
        phases_completed=summary.phases_completed,
        run_status=summary.status,
    )

    target_info_raw = manifest.get("target_info")
    target_info = target_info_raw if isinstance(target_info_raw, dict) else None

    spec_sources_raw = manifest.get("spec_sources") or []
    spec_sources = [str(s) for s in spec_sources_raw if isinstance(s, str)]

    prompt_shas_raw = manifest.get("prompt_shas") or {}
    prompt_shas: dict[str, str] = {}
    if isinstance(prompt_shas_raw, dict):
        for k, v in prompt_shas_raw.items():
            if isinstance(k, str) and isinstance(v, str):
                prompt_shas[k] = v

    branch_name = derive_branch_name(
        target_slug=summary.target_slug,
        run_id=summary.run_id,
    )

    return RunDetail(
        run_id=summary.run_id,
        started_at=summary.started_at,
        ended_at=summary.ended_at,
        target_slug=summary.target_slug,
        status=summary.status,
        cost_usd_total=summary.cost_usd_total,
        phases_completed=summary.phases_completed,
        phases=phases,
        target_info=target_info,
        spec_sources=spec_sources,
        prompt_shas=prompt_shas,
        branch_name=branch_name,
    )

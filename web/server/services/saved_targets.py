"""Compute the Saved targets list for the Project Picker.

The data flow is deliberately simple:

1. Walk ``.speca/runs/*/manifest.json`` (same on-disk substrate as the
   Runs router uses).
2. Extract each manifest's ``target_info.target_repo`` and dedupe by that
   key, keeping the most recent ``started_at`` as ``last_run_at``.
3. Prepend a hard-coded **demo seed** (``OpenListTeam/OpenList``) so the
   empty state is never blank on first launch — see Section 4.10
   (initiator-friendly principles) and Section 4.10.7 (pre-installed
   demo project) of ``docs/UI_DESIGN.md``. The demo target is an
   non-smart-contract OSS project so it doubles as a sanity check for
   the project-type expansion (web app / library / other).

We intentionally do **not** import :mod:`web.server.services.run_index`
to avoid binding this picker logic to the (larger) ``RunSummary`` shape;
the picker only needs ``target_info`` + ``started_at`` and reads them
directly. Manifest parse errors are logged and skipped so a single
malformed file cannot break the picker.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from web.server.config import SPECA_RUNS_DIR
from web.server.schemas.picker import SavedTarget

logger = logging.getLogger(__name__)

# The demo seed referenced in Section 4.10.7. Keeping it as a module-level
# constant (not a function arg) so the SPA contract is grep-able.
DEMO_SEED = SavedTarget(
    bug_bounty_url=None,
    target_repo="OpenListTeam/OpenList",
    target_ref=None,
    last_run_at=None,
    source="demo",
)


def _parse_iso(value: Any) -> datetime | None:
    """Tolerant ISO-8601 parser — same logic as ``run_index._parse_iso``.

    Duplicated here (rather than imported) so this service has no
    cross-module coupling beyond the schema module. Eight lines of
    duplication is cheaper than the dependency.
    """

    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    text = value.rstrip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _load_manifest(manifest_path: Path) -> dict[str, Any] | None:
    """Read a manifest, returning ``None`` (and logging) on any failure."""

    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("picker: unable to read %s: %s", manifest_path, exc)
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("picker: malformed manifest %s: %s", manifest_path, exc)
        return None
    if not isinstance(data, dict):
        return None
    return data


def list_saved_targets(runs_dir: Path | None = None) -> list[SavedTarget]:
    """Return demo seed + unique history entries, demo always first.

    History entries are deduplicated by ``target_repo``. When multiple
    runs target the same repo, the most recent ``started_at`` wins.
    Entries without a ``target_info.target_repo`` are silently skipped
    (a manifest written before the target was resolved is not useful as
    a saved-target hint).
    """

    target_dir = runs_dir or SPECA_RUNS_DIR

    # repo -> (last_run_at, bug_bounty_url, target_ref)
    history: dict[str, tuple[datetime | None, str | None, str | None]] = {}

    if target_dir.exists():
        for run_dir in target_dir.iterdir():
            if not run_dir.is_dir():
                continue
            manifest = _load_manifest(run_dir / "manifest.json")
            if manifest is None:
                continue

            target_info = manifest.get("target_info")
            if not isinstance(target_info, dict):
                continue
            target_repo = target_info.get("target_repo")
            if not isinstance(target_repo, str) or not target_repo:
                continue

            started_at = _parse_iso(manifest.get("started_at"))
            bug_bounty_url = target_info.get("bug_bounty_url")
            if bug_bounty_url is not None and not isinstance(bug_bounty_url, str):
                bug_bounty_url = None
            target_ref = target_info.get("target_ref")
            if target_ref is not None and not isinstance(target_ref, str):
                target_ref = None

            existing = history.get(target_repo)
            if existing is None or (
                started_at is not None
                and (existing[0] is None or started_at > existing[0])
            ):
                history[target_repo] = (started_at, bug_bounty_url, target_ref)

    entries: list[SavedTarget] = [DEMO_SEED]
    # Sort history entries by last_run_at descending, putting unknown
    # timestamps at the end so the freshest activity rises to the top.
    sortable = sorted(
        history.items(),
        key=lambda kv: kv[1][0] or datetime.fromtimestamp(0, tz=timezone.utc),
        reverse=True,
    )
    for repo, (last_run_at, bug_bounty_url, target_ref) in sortable:
        # Never let history shadow the demo seed even if a user actually
        # audits litecoin — the demo card already represents that target.
        if repo == DEMO_SEED.target_repo:
            continue
        entries.append(
            SavedTarget(
                bug_bounty_url=bug_bounty_url,
                target_repo=repo,
                target_ref=target_ref,
                last_run_at=last_run_at,
                source="history",
            )
        )

    return entries

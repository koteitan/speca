"""``GET /api/runs`` returns ``[]`` when no manifests exist.

Slice G regression: even if ``.speca/runs/`` is missing entirely (fresh
install, before any phase has been run), the listing endpoint must return
an empty array — *not* a 500 — so the SPA can render its empty-state hint.

We point the service-layer ``SPECA_RUNS_DIR`` at a ``tmp_path`` directory
that we intentionally leave empty. ``monkeypatch.setattr`` restores the
original at teardown so subsequent tests still see the real on-disk tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web.server.services import run_index


def test_runs_list_is_empty_when_runs_dir_missing(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A directory with zero run subdirs yields an empty JSON array."""

    empty_runs_dir = tmp_path / "speca-runs-empty"
    empty_runs_dir.mkdir()
    # The router calls ``list_runs()`` with no args, which falls back to
    # the module-level ``SPECA_RUNS_DIR`` constant — patching that constant
    # at the service layer is the lowest-blast-radius way to redirect the
    # filesystem read.
    monkeypatch.setattr(run_index, "SPECA_RUNS_DIR", empty_runs_dir)

    response = client.get("/api/runs")
    assert response.status_code == 200
    assert response.json() == []


def test_runs_list_is_empty_when_runs_dir_absent(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even a *non-existent* path must yield ``[]`` (no FileNotFoundError)."""

    missing = tmp_path / "does-not-exist"
    # NB: we never ``mkdir`` so the path is absent.
    monkeypatch.setattr(run_index, "SPECA_RUNS_DIR", missing)

    response = client.get("/api/runs")
    assert response.status_code == 200
    assert response.json() == []

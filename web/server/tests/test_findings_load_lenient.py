"""Findings router stays lenient against malformed PARTIAL JSON files.

The orchestrator writes ``outputs/03_PARTIAL_*.json`` / ``04_PARTIAL_*.json``
incrementally, and a crash between ``open`` and ``rename`` can leave a
half-written file on disk. The findings endpoint must:

1. Skip the malformed file (logging a warning is fine).
2. Return any *valid* records alongside the skipped ones.
3. Stay 200 — never 500 — so the SPA renders an empty list rather than
   an error banner.

We redirect ``SPECA_OUTPUTS_DIR`` at the loader module so the test does
not need to mutate the real ``outputs/`` tree on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web.server.services import finding_loader


def _write_partial(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_malformed_partial_is_skipped(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A garbage JSON file next to a valid one must not break the listing."""

    outputs = tmp_path / "outputs"
    outputs.mkdir()

    # 1. Broken JSON — must be skipped silently (logged).
    (outputs / "03_PARTIAL_W0B0_1700000000.json").write_text(
        "{not valid json,,, ", encoding="utf-8"
    )
    # 2. JSON whose top-level is a list (also unsupported by the loader).
    (outputs / "04_PARTIAL_W0B1_1700000001.json").write_text(
        "[1, 2, 3]", encoding="utf-8"
    )
    # 3. Valid Phase 03 record so we can assert something was returned.
    _write_partial(
        outputs / "03_PARTIAL_W0B2_1700000002.json",
        {
            "metadata": {"phase": "03", "timestamp": 1700000002},
            "audit_items": [
                {
                    "property_id": "P-TEST-001",
                    "severity": "High",
                    "code_path": "src/foo.py::L10-L20",
                }
            ],
        },
    )

    monkeypatch.setattr(finding_loader, "SPECA_OUTPUTS_DIR", outputs)

    response = client.get("/api/runs/any-run-id/findings")
    assert response.status_code == 200
    body = response.json()
    # Wire shape: { data: [...], meta: { data_source, count } }
    assert isinstance(body, dict)
    assert body["meta"]["data_source"] == "current_outputs"
    ids = [f["property_id"] for f in body["data"]]
    assert "P-TEST-001" in ids
    # Exactly one record survived — the two malformed files were skipped.
    assert body["meta"]["count"] == 1


def test_empty_outputs_dir_returns_empty_list(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A directory with no PARTIAL files yields an empty data array."""

    outputs = tmp_path / "empty-outputs"
    outputs.mkdir()
    monkeypatch.setattr(finding_loader, "SPECA_OUTPUTS_DIR", outputs)

    response = client.get("/api/runs/any/findings")
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["meta"]["count"] == 0

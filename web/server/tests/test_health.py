"""Smoke test for ``GET /api/health``.

The health endpoint is the canary used by the speca-web CLI banner and by
deployment probes. It must stay 200 + ``{"status": "ok"}`` even if every
other slice's state is empty/broken — there is no DB dependency to fail.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """The endpoint returns 200 with the documented body shape."""

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

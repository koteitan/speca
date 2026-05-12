"""``GET /api/integrations/status`` + ``/paths`` smoke contract.

We do not assert specific ``installed`` values — those depend on the
machine running pytest, and CI may or may not have ``code`` / ``gh``
installed. What we *do* assert is that:

* The status endpoint returns 200.
* The payload validates against the documented schema (the response_model
  guarantees this, but we double-check the shape for the SPA contract).
* The companion ``/paths`` endpoint returns 200 with three absolute path
  strings — used by Slice G's Settings page and the run-row VSCode actions.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_integrations_status_shape(client: TestClient) -> None:
    """The status payload exposes ``code`` + ``gh`` blocks with bool flags."""

    response = client.get("/api/integrations/status")
    assert response.status_code == 200, response.text

    body = response.json()
    assert set(body.keys()) == {"code", "gh"}

    # ``code`` block: { installed: bool, version: str | None }
    assert isinstance(body["code"]["installed"], bool)
    assert "version" in body["code"]

    # ``gh`` block: extends CliDetected with an ``authed: bool | None`` flag.
    assert isinstance(body["gh"]["installed"], bool)
    assert "version" in body["gh"]
    assert "authed" in body["gh"]  # may be None — that's allowed by the schema


def test_integrations_paths_returns_three_absolute_paths(
    client: TestClient,
) -> None:
    """``/paths`` returns repo_root + speca_dir + claude_dir as absolute strings."""

    response = client.get("/api/integrations/paths")
    assert response.status_code == 200, response.text

    body = response.json()
    assert set(body.keys()) == {"repo_root", "speca_dir", "claude_dir"}

    for key in ("repo_root", "speca_dir", "claude_dir"):
        value = body[key]
        assert isinstance(value, str) and value, f"{key} must be a non-empty string"
        # The server only emits resolved paths — anything else would be a
        # frontend footgun (``code <relative>`` opens the wrong workspace).
        assert Path(value).is_absolute(), f"{key} must be absolute, got {value!r}"

    # The speca_dir should live under repo_root (it is ``<repo>/.speca``).
    repo_root = Path(body["repo_root"]).resolve()
    speca_dir = Path(body["speca_dir"]).resolve()
    assert speca_dir.parent == repo_root, (
        f"speca_dir ({speca_dir}) should be a direct child of repo_root ({repo_root})"
    )

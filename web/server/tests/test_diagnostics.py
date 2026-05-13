"""``GET /api/diagnostics`` contract + env_probe unit coverage.

We do not assert specific ``installed`` values for the *router-level*
tests because they depend on the machine running pytest. The shape and
the per-probe parsing rules are pinned via:

* router shape test — every key the SPA expects is present with the
  documented type
* unit tests for :mod:`env_probe` — exercise the version-parser /
  status-decision matrix by patching ``subprocess.run`` and
  ``shutil.which``

The unit tests use ``monkeypatch`` rather than ``unittest.mock`` because
the rest of the suite already standardised on it (see
``test_integrations_fork.py``).
"""

from __future__ import annotations

import subprocess
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from web.server.schemas.integrations import (
    CliDetected,
    GhStatus,
    IntegrationsStatus,
)
from web.server.services import cli_detect, env_probe


# ---- helpers ----------------------------------------------------------------


def _completed(
    *, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["dummy"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _integrations_status(
    *,
    code_installed: bool = True,
    code_version: Optional[str] = "1.0.0",
    gh_installed: bool = True,
    gh_version: Optional[str] = "2.50.0",
    gh_authed: Optional[bool] = True,
) -> IntegrationsStatus:
    return IntegrationsStatus(
        code=CliDetected(installed=code_installed, version=code_version),
        gh=GhStatus(
            installed=gh_installed,
            version=gh_version,
            authed=gh_authed,
        ),
    )


# ---- env_probe unit tests ---------------------------------------------------


def test_probe_node_parses_semver_and_marks_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """``node --version`` prints ``v22.4.1`` → status=ok with parsed details."""

    monkeypatch.setattr(env_probe.shutil, "which", lambda name: "/fake/node")
    monkeypatch.setattr(
        env_probe.subprocess,
        "run",
        lambda *a, **kw: _completed(stdout="v22.4.1\n"),
    )

    status = env_probe.probe_node()
    assert status.installed is True
    assert status.version == "v22.4.1"
    assert status.status == "ok"
    assert status.details is not None
    assert status.details.get("min_version") == "20.0.0"
    assert status.details.get("parsed_version") == "22.4.1"


def test_probe_node_below_min_marks_outdated(monkeypatch: pytest.MonkeyPatch) -> None:
    """An ancient node (``v18.0.0``) is flagged as outdated, not ok."""

    monkeypatch.setattr(env_probe.shutil, "which", lambda name: "/fake/node")
    monkeypatch.setattr(
        env_probe.subprocess,
        "run",
        lambda *a, **kw: _completed(stdout="v18.0.0"),
    )

    status = env_probe.probe_node()
    assert status.installed is True
    assert status.status == "outdated"
    assert status.details is not None
    assert status.details.get("parsed_version") == "18.0.0"


def test_probe_node_missing_returns_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``node`` on PATH → status=missing, installed=False."""

    monkeypatch.setattr(env_probe.shutil, "which", lambda name: None)
    status = env_probe.probe_node()
    assert status.installed is False
    assert status.status == "missing"
    assert status.version is None


def test_probe_uv_returns_first_version_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """``uv --version`` lines like ``uv 0.4.18 (commit foo)`` are accepted."""

    monkeypatch.setattr(env_probe.shutil, "which", lambda name: "/fake/uv")
    monkeypatch.setattr(
        env_probe.subprocess,
        "run",
        lambda *a, **kw: _completed(stdout="uv 0.4.18 (abcdef1 2024-09-13)\n"),
    )

    status = env_probe.probe_uv()
    assert status.installed is True
    assert status.version == "uv 0.4.18 (abcdef1 2024-09-13)"
    assert status.status == "ok"


def test_probe_git_returns_first_version_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """``git --version`` returns ``git version 2.45.2`` → status=ok."""

    monkeypatch.setattr(env_probe.shutil, "which", lambda name: "/fake/git")
    monkeypatch.setattr(
        env_probe.subprocess,
        "run",
        lambda *a, **kw: _completed(stdout="git version 2.45.2"),
    )

    status = env_probe.probe_git()
    assert status.installed is True
    assert status.version == "git version 2.45.2"
    assert status.status == "ok"


def test_probe_timeout_returns_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``--version`` timeout is treated as installed-but-unknown.

    The binary clearly exists (``which`` returned a path) — we don't want
    to silently lose that fact just because ``--version`` hung.
    """

    monkeypatch.setattr(env_probe.shutil, "which", lambda name: "/fake/git")

    def _boom(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=3.0)

    monkeypatch.setattr(env_probe.subprocess, "run", _boom)
    status = env_probe.probe_git()
    assert status.installed is True
    assert status.status == "unknown"
    assert status.version is None


# ---- router-level contract --------------------------------------------------


def test_diagnostics_endpoint_returns_full_report(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``GET /api/diagnostics`` returns the full keyset the SPA expects."""

    # Force a stable cli_detect snapshot so the test is deterministic
    # regardless of whether ``code`` / ``gh`` happen to be installed on CI.
    monkeypatch.setattr(
        cli_detect,
        "get_status",
        lambda *a, **kw: _integrations_status(),
    )

    response = client.get("/api/diagnostics")
    assert response.status_code == 200, response.text
    body = response.json()

    assert set(body.keys()) == {
        "node",
        "uv",
        "git",
        "claude",
        "gh",
        "code",
        "auth",
        "api_key_configured",
    }

    for tool_name in ("node", "uv", "git", "claude", "gh", "code"):
        tool = body[tool_name]
        assert isinstance(tool["installed"], bool), tool_name
        assert tool["status"] in {"ok", "missing", "outdated", "unknown"}, tool_name
        assert tool["name"] == tool_name, tool_name

    # auth block matches AuthStatus shape
    assert "logged_in" in body["auth"]
    assert isinstance(body["auth"]["logged_in"], bool)

    assert isinstance(body["api_key_configured"], bool)


def test_diagnostics_uses_cli_detect_for_gh_and_code(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``gh`` / ``code`` blocks are sourced from cli_detect, not re-probed."""

    monkeypatch.setattr(
        cli_detect,
        "get_status",
        lambda *a, **kw: _integrations_status(
            code_installed=True,
            code_version="1.95.0",
            gh_installed=True,
            gh_version="gh version 2.50.0",
            gh_authed=False,
        ),
    )

    response = client.get("/api/diagnostics")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["code"]["installed"] is True
    assert body["code"]["version"] == "1.95.0"
    assert body["code"]["status"] == "ok"

    assert body["gh"]["installed"] is True
    assert body["gh"]["version"] == "gh version 2.50.0"
    # ``gh.authed=False`` is surfaced via ``details`` so the SPA can show
    # a "needs gh auth login" hint without a second round trip.
    assert body["gh"]["details"] == {"authed": False}


def test_diagnostics_marks_missing_tools_when_cli_detect_reports_none(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When cli_detect says ``code`` is absent we surface ``missing``."""

    monkeypatch.setattr(
        cli_detect,
        "get_status",
        lambda *a, **kw: _integrations_status(
            code_installed=False,
            code_version=None,
            gh_installed=False,
            gh_version=None,
            gh_authed=None,
        ),
    )

    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    body = response.json()
    assert body["code"]["installed"] is False
    assert body["code"]["status"] == "missing"
    assert body["gh"]["installed"] is False
    assert body["gh"]["status"] == "missing"


def test_api_key_configured_respects_env_var(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ANTHROPIC_API_KEY`` non-empty → ``api_key_configured == True``."""

    monkeypatch.setattr(
        cli_detect, "get_status", lambda *a, **kw: _integrations_status()
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")

    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    assert response.json()["api_key_configured"] is True


def test_api_key_configured_false_when_env_empty(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No env key + no apiKey in credentials.json → False."""

    monkeypatch.setattr(
        cli_detect, "get_status", lambda *a, **kw: _integrations_status()
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Stub credentials loader so we don't depend on the user's real
    # ~/.claude/credentials.json on the dev box / CI runner.
    from web.server.services import credentials as credentials_service

    monkeypatch.setattr(credentials_service, "_load_raw", lambda *a, **kw: {})

    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    assert response.json()["api_key_configured"] is False

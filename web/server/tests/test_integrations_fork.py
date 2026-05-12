"""``POST /api/integrations/fork`` (Slice B4) contract.

The endpoint wraps ``gh repo fork`` — these tests never touch the real
GitHub or even the real ``gh`` binary. We patch two seams:

* :func:`web.server.services.cli_detect.get_status` to control the
  pre-flight "is gh installed?" check.
* :func:`web.server.services.launchers.gh_repo_fork` to simulate the
  three outcomes the launcher promises (success / not-authed / fork
  failed) without spawning a subprocess.

A separate group of tests exercises the launcher directly via
``subprocess.run`` monkeypatching to lock in the stdout-parse behaviour
(``Created fork``, ``already exists``, missing owner/repo token, ...).
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
from web.server.services import cli_detect, launchers
from web.server.services.launchers import (
    GhForkFailed,
    GhNotAuthenticated,
    gh_repo_fork,
)


# ---- helpers ---------------------------------------------------------------


def _status(
    *,
    gh_installed: bool = True,
    gh_authed: Optional[bool] = True,
    code_installed: bool = True,
) -> IntegrationsStatus:
    """Build a minimal :class:`IntegrationsStatus` for ``get_status`` mocks."""

    return IntegrationsStatus(
        code=CliDetected(installed=code_installed, version="1.0.0"),
        gh=GhStatus(
            installed=gh_installed,
            version="2.50.0" if gh_installed else None,
            authed=gh_authed,
        ),
    )


def _completed(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Build a :class:`subprocess.CompletedProcess` for ``_run_gh`` mocks."""

    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


# ---- router-level tests (mock ``gh_repo_fork`` directly) -------------------


def test_fork_happy_path(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful fork returns ``ForkResponse`` with fork_url + forked_repo."""

    monkeypatch.setattr(cli_detect, "get_status", lambda *a, **kw: _status())

    captured: dict[str, object] = {}

    def fake_fork(target_repo: str, into_owner: Optional[str] = None) -> dict[str, str]:
        captured["target_repo"] = target_repo
        captured["into_owner"] = into_owner
        return {
            "fork_url": "https://github.com/me/Hello-World",
            "forked_repo": "me/Hello-World",
        }

    monkeypatch.setattr(launchers, "gh_repo_fork", fake_fork)

    response = client.post(
        "/api/integrations/fork",
        json={"target_repo": "octocat/Hello-World", "confirmed": True},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "fork_url": "https://github.com/me/Hello-World",
        "forked_repo": "me/Hello-World",
    }
    assert captured == {"target_repo": "octocat/Hello-World", "into_owner": None}


def test_fork_passes_into_owner(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``into_owner`` propagates to the launcher."""

    monkeypatch.setattr(cli_detect, "get_status", lambda *a, **kw: _status())

    seen: dict[str, object] = {}

    def fake_fork(target_repo: str, into_owner: Optional[str] = None) -> dict[str, str]:
        seen["into_owner"] = into_owner
        return {
            "fork_url": "https://github.com/myorg/Hello-World",
            "forked_repo": "myorg/Hello-World",
        }

    monkeypatch.setattr(launchers, "gh_repo_fork", fake_fork)

    response = client.post(
        "/api/integrations/fork",
        json={
            "target_repo": "octocat/Hello-World",
            "into_owner": "myorg",
            "confirmed": True,
        },
    )

    assert response.status_code == 200, response.text
    assert seen["into_owner"] == "myorg"


def test_fork_requires_confirmation(client: TestClient) -> None:
    """``confirmed: false`` (and a missing flag) both 400 before any subprocess."""

    response = client.post(
        "/api/integrations/fork",
        json={"target_repo": "octocat/Hello-World", "confirmed": False},
    )
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["detail"]["error"] == "confirmation_required"


def test_fork_missing_confirmed_field_defaults_to_false(client: TestClient) -> None:
    """Omitting ``confirmed`` is the same as ``false`` — must 400, not 200."""

    response = client.post(
        "/api/integrations/fork", json={"target_repo": "octocat/Hello-World"}
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["error"] == "confirmation_required"


def test_fork_gh_not_installed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``gh`` not on PATH returns 503 ``gh_cli_not_found``."""

    monkeypatch.setattr(
        cli_detect,
        "get_status",
        lambda *a, **kw: _status(gh_installed=False, gh_authed=None),
    )

    def fake_fork(*args, **kwargs):  # pragma: no cover — should not be reached
        raise AssertionError("launcher must not be called when gh is missing")

    monkeypatch.setattr(launchers, "gh_repo_fork", fake_fork)

    response = client.post(
        "/api/integrations/fork",
        json={"target_repo": "octocat/Hello-World", "confirmed": True},
    )
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["error"] == "gh_cli_not_found"


def test_fork_not_authed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """``GhNotAuthenticated`` becomes a 403 with the documented body."""

    monkeypatch.setattr(cli_detect, "get_status", lambda *a, **kw: _status())

    def fake_fork(*args, **kwargs):
        raise GhNotAuthenticated("gh auth status: not logged in")

    monkeypatch.setattr(launchers, "gh_repo_fork", fake_fork)

    response = client.post(
        "/api/integrations/fork",
        json={"target_repo": "octocat/Hello-World", "confirmed": True},
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["error"] == "gh_not_authed"


def test_fork_failed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """``GhForkFailed`` becomes a 502 carrying the stderr text."""

    monkeypatch.setattr(cli_detect, "get_status", lambda *a, **kw: _status())

    def fake_fork(*args, **kwargs):
        raise GhForkFailed("HTTP 404: Not Found (https://api.github.com/repos/...)")

    monkeypatch.setattr(launchers, "gh_repo_fork", fake_fork)

    response = client.post(
        "/api/integrations/fork",
        json={"target_repo": "octocat/does-not-exist", "confirmed": True},
    )
    assert response.status_code == 502, response.text
    body = response.json()
    assert body["detail"]["error"] == "gh_fork_failed"
    assert "404" in body["detail"]["detail"]


def test_fork_gh_disappeared_after_status(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``FileNotFoundError`` from the launcher (race) also maps to 503."""

    monkeypatch.setattr(cli_detect, "get_status", lambda *a, **kw: _status())

    def fake_fork(*args, **kwargs):
        raise FileNotFoundError("gh CLI not found on PATH")

    monkeypatch.setattr(launchers, "gh_repo_fork", fake_fork)

    response = client.post(
        "/api/integrations/fork",
        json={"target_repo": "octocat/Hello-World", "confirmed": True},
    )
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["error"] == "gh_cli_not_found"


# ---- pydantic validation ---------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "foo",                # no slash
        "a/b/c",              # too many slashes
        "owner/",             # empty repo
        "/repo",              # empty owner
        "owner repo/x",       # space in owner
        "owner/repo!",        # disallowed char
        "",                   # empty (also tripped by min_length)
    ],
)
def test_fork_invalid_target_repo_returns_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    """Pydantic validator rejects non ``owner/repo`` shapes before any subprocess."""

    monkeypatch.setattr(cli_detect, "get_status", lambda *a, **kw: _status())

    def fake_fork(*args, **kwargs):  # pragma: no cover — must not be called
        raise AssertionError("launcher must not be reached for invalid input")

    monkeypatch.setattr(launchers, "gh_repo_fork", fake_fork)

    response = client.post(
        "/api/integrations/fork",
        json={"target_repo": bad, "confirmed": True},
    )
    assert response.status_code == 422, response.text


# ---- launcher-level tests (mock ``_run_gh`` to lock parsing behaviour) ----


def _patch_gh_binary(monkeypatch: pytest.MonkeyPatch, *, present: bool = True) -> None:
    monkeypatch.setattr(
        launchers,
        "_find_gh_binary",
        lambda: "/usr/local/bin/gh" if present else None,
    )


def test_launcher_missing_binary_raises_filenotfound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_gh_binary(monkeypatch, present=False)

    with pytest.raises(FileNotFoundError):
        gh_repo_fork("octocat/Hello-World")


def test_launcher_auth_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_gh_binary(monkeypatch)

    def fake_run(args, *, timeout):
        # The launcher first probes ``gh auth status``.
        assert args[1] == "auth"
        return _completed(returncode=1, stderr="You are not logged into any hosts")

    monkeypatch.setattr(launchers, "_run_gh", fake_run)

    with pytest.raises(GhNotAuthenticated):
        gh_repo_fork("octocat/Hello-World")


def test_launcher_parses_created_fork_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """``gh repo fork`` "Created fork ..." stdout -> forked_repo + URL."""

    _patch_gh_binary(monkeypatch)

    calls: list[list[str]] = []

    def fake_run(args, *, timeout):
        calls.append(list(args))
        if args[1] == "auth":
            return _completed(returncode=0, stdout="Logged in to github.com as me")
        # ``gh repo fork`` invocation.
        return _completed(
            returncode=0,
            stdout="✓ Created fork me/Hello-World\n",
        )

    monkeypatch.setattr(launchers, "_run_gh", fake_run)

    result = gh_repo_fork("octocat/Hello-World")
    assert result == {
        "fork_url": "https://github.com/me/Hello-World",
        "forked_repo": "me/Hello-World",
    }
    # The fork invocation must carry the no-clone / no-remote flags.
    fork_call = calls[-1]
    assert "repo" in fork_call and "fork" in fork_call
    assert "--clone=false" in fork_call
    assert "--remote=false" in fork_call
    assert "--org" not in fork_call


def test_launcher_parses_already_exists_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``"<owner>/<repo> already exists"`` is a success — parse the owner/repo."""

    _patch_gh_binary(monkeypatch)

    def fake_run(args, *, timeout):
        if args[1] == "auth":
            return _completed(returncode=0)
        return _completed(
            returncode=0,
            stderr="me/Hello-World already exists\n",
        )

    monkeypatch.setattr(launchers, "_run_gh", fake_run)

    result = gh_repo_fork("octocat/Hello-World")
    assert result["forked_repo"] == "me/Hello-World"
    assert result["fork_url"] == "https://github.com/me/Hello-World"


def test_launcher_into_owner_appends_org_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_gh_binary(monkeypatch)

    captured: list[list[str]] = []

    def fake_run(args, *, timeout):
        captured.append(list(args))
        if args[1] == "auth":
            return _completed(returncode=0)
        return _completed(returncode=0, stdout="Created fork myorg/Hello-World\n")

    monkeypatch.setattr(launchers, "_run_gh", fake_run)

    result = gh_repo_fork("octocat/Hello-World", into_owner="myorg")
    assert result["forked_repo"] == "myorg/Hello-World"
    fork_call = captured[-1]
    assert fork_call[-2:] == ["--org", "myorg"]


def test_launcher_nonzero_exit_raises_forkfailed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_gh_binary(monkeypatch)

    def fake_run(args, *, timeout):
        if args[1] == "auth":
            return _completed(returncode=0)
        return _completed(returncode=1, stderr="HTTP 404: Not Found\n")

    monkeypatch.setattr(launchers, "_run_gh", fake_run)

    with pytest.raises(GhForkFailed) as excinfo:
        gh_repo_fork("octocat/does-not-exist")
    assert "404" in str(excinfo.value)


def test_launcher_timeout_raises_forkfailed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_gh_binary(monkeypatch)

    def fake_run(args, *, timeout):
        if args[1] == "auth":
            return _completed(returncode=0)
        raise subprocess.TimeoutExpired(cmd=args, timeout=timeout)

    monkeypatch.setattr(launchers, "_run_gh", fake_run)

    with pytest.raises(GhForkFailed) as excinfo:
        gh_repo_fork("octocat/Hello-World")
    assert "timed out" in str(excinfo.value).lower()


def test_launcher_unrecognised_stdout_raises_forkfailed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Success exit but no ``owner/repo`` token in stdout/stderr -> error."""

    _patch_gh_binary(monkeypatch)

    def fake_run(args, *, timeout):
        if args[1] == "auth":
            return _completed(returncode=0)
        # No slash anywhere — parser cannot recover.
        return _completed(returncode=0, stdout="ok\n")

    monkeypatch.setattr(launchers, "_run_gh", fake_run)

    with pytest.raises(GhForkFailed) as excinfo:
        gh_repo_fork("octocat/Hello-World")
    assert "recognisable owner/repo" in str(excinfo.value)


def test_launcher_skips_target_repo_echo(monkeypatch: pytest.MonkeyPatch) -> None:
    """If stdout only contains the upstream ``octocat/Hello-World`` we error,
    not silently return the source as the fork."""

    _patch_gh_binary(monkeypatch)

    def fake_run(args, *, timeout):
        if args[1] == "auth":
            return _completed(returncode=0)
        # Echoes only the upstream repo — no fork owner anywhere.
        return _completed(returncode=0, stdout="forking octocat/Hello-World\n")

    monkeypatch.setattr(launchers, "_run_gh", fake_run)

    with pytest.raises(GhForkFailed):
        gh_repo_fork("octocat/Hello-World")

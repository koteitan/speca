"""``POST /api/runs`` (Slice B1) contract.

The endpoint orchestrates three collaborators:

* :class:`WorkspaceManager` — bare cache + worktree provisioning
* :class:`RunSupervisor`    — subprocess + state.json lifecycle
* router-side validation    — ``owner/repo`` shape + canonical envelopes

All three are mocked here so the test never touches the network, git, or
a real worktree directory. We assert on:

* ``status_code`` (202 / 422 / 502)
* ``RunStartResponse`` shape (run_id / branch_name / workspace_path / started_at)
* the *order* of collaborator calls (ensure_bare_cache must precede
  create_worktree, both must precede supervisor.start_run)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from web.server.routers import runs as runs_router
from web.server.schemas.run_state import RunStateDoc
from web.server.services import run_state as run_state_svc
from web.server.services import run_supervisor as run_supervisor_svc
from web.server.services import workspace_manager as workspace_manager_svc
from web.server.services.workspace_manager import CloneFailed, RefNotFound


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_spec_body() -> dict[str, Any]:
    """Minimum spec that passes Pydantic + router-side validation."""

    return {
        "bug_bounty_url": "https://example.invalid/bounty",
        "target_repo": "acme/widget",
        "target_ref": "main",
        "workers": 2,
        "max_concurrent": 16,
    }


class _FakeWorkspaceManager:
    """Drop-in for :class:`WorkspaceManager` with recordable calls.

    The real manager would shell out to git; this fake just remembers the
    arguments and returns a pretend worktree :class:`Path`. Each test that
    cares about ordering inspects ``calls`` after the fact.
    """

    def __init__(self, *, fail_ensure: Exception | None = None,
                 fail_worktree: Exception | None = None,
                 worktree_path: Path | None = None) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self._fail_ensure = fail_ensure
        self._fail_worktree = fail_worktree
        self._worktree_path = worktree_path or Path("/tmp/fake-worktree")

    def ensure_bare_cache(self, repo_url: str) -> Path:
        self.calls.append(("ensure_bare_cache", (repo_url,), {}))
        if self._fail_ensure is not None:
            raise self._fail_ensure
        return Path("/tmp/fake-bare.git")

    def create_worktree(self, *, run_id: str, repo_url: str, ref: str | None = None) -> Path:
        self.calls.append(("create_worktree", (), {"run_id": run_id, "repo_url": repo_url, "ref": ref}))
        if self._fail_worktree is not None:
            raise self._fail_worktree
        return self._worktree_path


class _FakeSupervisor:
    """Minimal supervisor stand-in: records ``start_run`` invocations."""

    def __init__(self, run_id: str = "fake-run-id") -> None:
        self.run_id = run_id
        self.start_run_calls: list[tuple[Any, ...]] = []

    async def start_run(self, spec: Any, *, workspace_path: Path,
                        target_info: Any = None) -> str:
        self.start_run_calls.append((spec, workspace_path, target_info))
        return self.run_id


def _install_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    workspace: _FakeWorkspaceManager,
    supervisor: _FakeSupervisor,
    run_id: str = "fake-run-id",
    state_doc: RunStateDoc | None = None,
) -> None:
    """Wire the fakes into the router's collaborators."""

    monkeypatch.setattr(
        workspace_manager_svc, "WorkspaceManager", lambda *a, **kw: workspace
    )
    monkeypatch.setattr(
        run_supervisor_svc, "get_run_supervisor", lambda: supervisor
    )
    # The router computes its own run_id to feed ``create_worktree``;
    # pin it so we can assert on the worktree call without coupling to
    # the real timestamp/sha helper.
    monkeypatch.setattr(
        run_supervisor_svc, "make_run_id", lambda **kw: run_id
    )
    # ``load_state`` runs after ``start_run``; return a populated doc so
    # ``started_at`` falls back to the documented heartbeat field.
    monkeypatch.setattr(
        run_state_svc,
        "load_state",
        lambda *a, **kw: state_doc,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_start_run_returns_202_and_metadata(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Valid spec yields 202 + all four response fields populated."""

    worktree = tmp_path / "wt" / "fake-run-id"
    workspace = _FakeWorkspaceManager(worktree_path=worktree)
    supervisor = _FakeSupervisor(run_id="2026-05-12T00-00-00Z-abcdef1-widget")

    heartbeat = datetime(2026, 5, 12, tzinfo=timezone.utc)
    state_doc = RunStateDoc(
        run_id=supervisor.run_id,
        status="running",
        last_heartbeat_at=heartbeat,
    )
    _install_fakes(
        monkeypatch,
        workspace=workspace,
        supervisor=supervisor,
        run_id="2026-05-12T00-00-00Z-abcdef1-widget",
        state_doc=state_doc,
    )

    response = client.post("/api/runs", json=_valid_spec_body())

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["run_id"] == supervisor.run_id
    assert body["branch_name"] == f"audit/acme-widget/{supervisor.run_id}"
    assert body["workspace_path"] == str(worktree)
    # ``started_at`` echoes the state-doc heartbeat verbatim.
    assert body["started_at"].startswith("2026-05-12T00:00:00")


def test_start_run_calls_collaborators_in_order(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ensure_bare_cache -> create_worktree -> supervisor.start_run."""

    workspace = _FakeWorkspaceManager()
    supervisor = _FakeSupervisor()
    _install_fakes(monkeypatch, workspace=workspace, supervisor=supervisor)

    response = client.post("/api/runs", json=_valid_spec_body())
    assert response.status_code == 202, response.text

    # Workspace was hit twice: ensure_bare_cache, then create_worktree.
    op_names = [call[0] for call in workspace.calls]
    assert op_names == ["ensure_bare_cache", "create_worktree"]
    # And supervisor.start_run ran once after the worktree was ready.
    assert len(supervisor.start_run_calls) == 1


def test_start_run_passes_target_ref_to_worktree(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``target_ref`` from the spec is forwarded verbatim to ``create_worktree``."""

    workspace = _FakeWorkspaceManager()
    supervisor = _FakeSupervisor()
    _install_fakes(monkeypatch, workspace=workspace, supervisor=supervisor)

    body = _valid_spec_body()
    body["target_ref"] = "v1.2.3"
    response = client.post("/api/runs", json=body)
    assert response.status_code == 202

    create_call = next(c for c in workspace.calls if c[0] == "create_worktree")
    assert create_call[2]["ref"] == "v1.2.3"


def test_start_run_passes_https_url_to_bare_cache(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The router composes the GitHub ``https://`` URL itself."""

    workspace = _FakeWorkspaceManager()
    supervisor = _FakeSupervisor()
    _install_fakes(monkeypatch, workspace=workspace, supervisor=supervisor)

    body = _valid_spec_body()
    body["target_repo"] = "octocat/Hello-World"
    response = client.post("/api/runs", json=body)
    assert response.status_code == 202

    ensure_call = next(c for c in workspace.calls if c[0] == "ensure_bare_cache")
    assert ensure_call[1] == ("https://github.com/octocat/Hello-World.git",)


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "foo",                 # no slash
        "a/b/c",               # too many segments
        "owner/",              # empty repo
        "/repo",               # empty owner
        "owner repo/x",        # whitespace
        "owner/repo!",         # disallowed char
        "https://github.com/owner/repo",  # full URL — rejected at this layer
    ],
)
def test_start_run_invalid_target_repo_returns_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    """The router-side regex rejects everything that isn't ``owner/repo``."""

    workspace = _FakeWorkspaceManager()
    supervisor = _FakeSupervisor()
    _install_fakes(monkeypatch, workspace=workspace, supervisor=supervisor)

    body = _valid_spec_body()
    body["target_repo"] = bad
    response = client.post("/api/runs", json=body)
    assert response.status_code == 422, response.text
    # Workspace + supervisor must NOT be touched on a 422.
    assert workspace.calls == []
    assert supervisor.start_run_calls == []


def test_start_run_missing_bug_bounty_url_returns_422(client: TestClient) -> None:
    """Pydantic rejects a missing required field with a 422."""

    body = _valid_spec_body()
    del body["bug_bounty_url"]
    response = client.post("/api/runs", json=body)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Upstream failures
# ---------------------------------------------------------------------------


def test_start_run_clone_failed_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``CloneFailed`` from ``ensure_bare_cache`` becomes a 502 envelope."""

    workspace = _FakeWorkspaceManager(
        fail_ensure=CloneFailed("git clone --bare exit 128: remote not found")
    )
    supervisor = _FakeSupervisor()
    _install_fakes(monkeypatch, workspace=workspace, supervisor=supervisor)

    response = client.post("/api/runs", json=_valid_spec_body())
    assert response.status_code == 502, response.text
    body = response.json()
    assert body["detail"]["error"] == "clone_failed"
    assert "remote not found" in body["detail"]["message"]
    # Supervisor must not be touched if cloning failed.
    assert supervisor.start_run_calls == []


def test_start_run_worktree_clone_failed_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``CloneFailed`` from ``create_worktree`` (disk full, ...) -> 502."""

    workspace = _FakeWorkspaceManager(
        fail_worktree=CloneFailed("git worktree add: no space left on device")
    )
    supervisor = _FakeSupervisor()
    _install_fakes(monkeypatch, workspace=workspace, supervisor=supervisor)

    response = client.post("/api/runs", json=_valid_spec_body())
    assert response.status_code == 502, response.text
    assert response.json()["detail"]["error"] == "worktree_failed"
    assert supervisor.start_run_calls == []


def test_start_run_ref_not_found_returns_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unknown ``target_ref`` collapses to a 422 (caller fault)."""

    workspace = _FakeWorkspaceManager(
        fail_worktree=RefNotFound("ref 'nope' not found")
    )
    supervisor = _FakeSupervisor()
    _install_fakes(monkeypatch, workspace=workspace, supervisor=supervisor)

    body = _valid_spec_body()
    body["target_ref"] = "nope"
    response = client.post("/api/runs", json=body)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error"] == "ref_not_found"

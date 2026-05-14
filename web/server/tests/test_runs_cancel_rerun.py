"""``POST /api/runs/<id>/cancel`` and ``.../rerun`` contracts (Slice B1).

The supervisor is mocked end-to-end. We exercise:

* ``cancel`` against a running run    -> 200 ``cancel_requested``
* ``cancel`` against a finished run   -> 200 ``already_finished``
* ``cancel`` against an unknown run   -> 404 ``run_not_found``
* ``rerun`` happy path                -> 200, supervisor.rerun_phases called
* ``rerun`` with a bogus phase        -> 422 ``invalid_phases``
* ``rerun`` against a still-running   -> 409 ``still_running``
* ``rerun`` against an unknown run    -> 404 ``run_not_found``
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from web.server.schemas.run_state import (
    LiveStatus,
    PhaseStateEntry,
    RunStateDoc,
)
from web.server.services import run_state as run_state_svc
from web.server.services import run_supervisor as run_supervisor_svc


# ---------------------------------------------------------------------------
# Fake supervisor
# ---------------------------------------------------------------------------


class _FakeSupervisor:
    """In-memory supervisor stand-in for cancel + rerun.

    The router consults ``get_live_status``, ``_active``, ``cancel_run``,
    and ``rerun_phases``. We provide attribute-level controls so each
    test can dial in the exact failure / success path it wants.
    """

    def __init__(
        self,
        *,
        live: LiveStatus | None = None,
        active_ids: tuple[str, ...] = (),
    ) -> None:
        self._live = live
        # The router checks ``run_id not in supervisor._active`` —
        # mirror the attribute so the access doesn't AttributeError.
        self._active: dict[str, Any] = {rid: object() for rid in active_ids}
        self.cancel_calls: list[str] = []
        self.rerun_calls: list[tuple[str, list[str]]] = []

    def get_live_status(self, run_id: str) -> LiveStatus | None:
        return self._live

    async def cancel_run(self, run_id: str) -> None:
        self.cancel_calls.append(run_id)

    async def rerun_phases(self, run_id: str, phases: list[str]) -> None:
        self.rerun_calls.append((run_id, list(phases)))


def _live_status(run_id: str, status: str = "running") -> LiveStatus:
    """Build a :class:`LiveStatus` matching the supervisor's shape."""

    return LiveStatus(
        run_id=run_id,
        status=status,  # type: ignore[arg-type]
        current_phase="03",
        phases=[PhaseStateEntry(phase_id="03", status="running")],
        cost_usd_total=0.0,
        cancel_requested=False,
    )


def _state_doc(run_id: str, status: str = "completed") -> RunStateDoc:
    """Build a :class:`RunStateDoc` for ``run_state.load_state`` mocks."""

    return RunStateDoc(
        run_id=run_id,
        status=status,  # type: ignore[arg-type]
        phases=[PhaseStateEntry(phase_id="03", status="ok")],
    )


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


def test_cancel_running_run_returns_cancel_requested(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A live, in-flight run yields 200 + ``cancel_requested``."""

    run_id = "run-alive"
    supervisor = _FakeSupervisor(
        live=_live_status(run_id, "running"),
        active_ids=(run_id,),
    )
    monkeypatch.setattr(
        run_supervisor_svc, "get_run_supervisor", lambda: supervisor
    )

    response = client.post(f"/api/runs/{run_id}/cancel")
    assert response.status_code == 200, response.text
    assert response.json() == {"run_id": run_id, "status": "cancel_requested"}
    assert supervisor.cancel_calls == [run_id]


def test_cancel_finished_run_returns_already_finished(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A terminal run (state.json present, supervisor evicted) is idempotent."""

    run_id = "run-done"
    # ``get_live_status`` falls back to disk for evicted runs and returns
    # a LiveStatus, but the run is *not* in ``_active``.
    supervisor = _FakeSupervisor(
        live=_live_status(run_id, "completed"),
        active_ids=(),
    )
    monkeypatch.setattr(
        run_supervisor_svc, "get_run_supervisor", lambda: supervisor
    )

    response = client.post(f"/api/runs/{run_id}/cancel")
    assert response.status_code == 200, response.text
    assert response.json() == {"run_id": run_id, "status": "already_finished"}
    # No actual cancel was dispatched.
    assert supervisor.cancel_calls == []


def test_cancel_unknown_run_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No state.json and no in-memory record -> 404 ``run_not_found``."""

    supervisor = _FakeSupervisor(live=None, active_ids=())
    monkeypatch.setattr(
        run_supervisor_svc, "get_run_supervisor", lambda: supervisor
    )

    response = client.post("/api/runs/nope/cancel")
    assert response.status_code == 404, response.text
    assert response.json()["detail"]["error"] == "run_not_found"


# ---------------------------------------------------------------------------
# Rerun
# ---------------------------------------------------------------------------


def test_rerun_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A terminal run + valid phase list -> 200 + supervisor.rerun_phases called."""

    run_id = "run-done"
    supervisor = _FakeSupervisor()
    monkeypatch.setattr(
        run_supervisor_svc, "get_run_supervisor", lambda: supervisor
    )
    monkeypatch.setattr(
        run_state_svc, "load_state", lambda *a, **kw: _state_doc(run_id, "failed")
    )

    response = client.post(
        f"/api/runs/{run_id}/rerun", json={"phases": ["03", "04"]}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"run_id": run_id, "rerun_phases": ["03", "04"]}
    assert supervisor.rerun_calls == [(run_id, ["03", "04"])]


def test_rerun_with_bogus_phase_returns_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unknown phase id aborts at the router with the offending list."""

    supervisor = _FakeSupervisor()
    monkeypatch.setattr(
        run_supervisor_svc, "get_run_supervisor", lambda: supervisor
    )
    # ``load_state`` should never be reached when validation kicks in first.
    monkeypatch.setattr(
        run_state_svc, "load_state",
        lambda *a, **kw: pytest.fail("load_state must not run on 422"),
    )

    response = client.post(
        "/api/runs/whatever/rerun", json={"phases": ["bogus"]}
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["detail"]["error"] == "invalid_phases"
    assert body["detail"]["invalid"] == ["bogus"]
    assert supervisor.rerun_calls == []


def test_rerun_with_partially_bogus_phases_returns_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even a single bad phase rejects the whole request."""

    supervisor = _FakeSupervisor()
    monkeypatch.setattr(
        run_supervisor_svc, "get_run_supervisor", lambda: supervisor
    )

    response = client.post(
        "/api/runs/whatever/rerun", json={"phases": ["03", "zzz"]}
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["invalid"] == ["zzz"]


def test_rerun_empty_phases_returns_422(client: TestClient) -> None:
    """Pydantic ``min_length=1`` rejects an empty phase list."""

    response = client.post("/api/runs/whatever/rerun", json={"phases": []})
    assert response.status_code == 422


def test_rerun_unknown_run_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No state.json -> 404 ``run_not_found``."""

    supervisor = _FakeSupervisor()
    monkeypatch.setattr(
        run_supervisor_svc, "get_run_supervisor", lambda: supervisor
    )
    monkeypatch.setattr(run_state_svc, "load_state", lambda *a, **kw: None)

    response = client.post(
        "/api/runs/missing/rerun", json={"phases": ["03"]}
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"]["error"] == "run_not_found"
    assert supervisor.rerun_calls == []


def test_rerun_running_run_returns_409(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A still-running run cannot be re-run; user must cancel first."""

    run_id = "run-alive"
    supervisor = _FakeSupervisor()
    monkeypatch.setattr(
        run_supervisor_svc, "get_run_supervisor", lambda: supervisor
    )
    monkeypatch.setattr(
        run_state_svc, "load_state", lambda *a, **kw: _state_doc(run_id, "running")
    )

    response = client.post(
        f"/api/runs/{run_id}/rerun", json={"phases": ["03"]}
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == "still_running"
    assert supervisor.rerun_calls == []

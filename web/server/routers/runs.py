"""HTTP routes for the Runs slice.

Two endpoints, both read-only:

* ``GET /api/runs`` — list of :class:`RunSummary`, newest first
* ``GET /api/runs/{run_id}`` — full :class:`RunDetail`

The actual indexing/parsing is done in
:mod:`web.server.services.run_index`; the router stays thin so that
adding e.g. a future ``POST /api/runs`` (v1, "New run" button) doesn't
have to wade through business logic.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from web.server.schemas.runs import RunDetail, RunSummary
from web.server.services.run_index import get_run_detail, list_runs

# We register the router under ``/api`` and define explicit paths so each
# endpoint reads top-down with its full URL — easier to grep than relying
# on a ``/api/runs`` prefix.
router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs", response_model=list[RunSummary])
def get_runs() -> list[RunSummary]:
    """Return the most recent runs (capped, newest first)."""

    return list_runs()


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str) -> RunDetail:
    """Return the detail payload for a single run."""

    detail = get_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return detail

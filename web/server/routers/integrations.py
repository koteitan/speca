"""Integrations router — local CLI detection and "Open in VSCode".

Endpoints:

* ``GET  /api/integrations/status`` — read-only snapshot of whether
  ``code`` and ``gh`` are installed (and, for ``gh``, whether the user is
  logged in). Cached server-side for ~30 s; the SPA additionally treats
  the query as fresh for 60 s.
* ``POST /api/integrations/open-in-vscode`` — fire-and-forget ``code``
  spawn. Returns ``{"ok": true}`` on success, ``503`` with a structured
  ``vscode_cli_not_found`` body if ``code`` is missing.

The ``POST /api/integrations/fork`` endpoint (gh fork) is reserved for v1
and intentionally not registered here — the v0 status payload is enough
for the UI to render a "Fork to GitHub" button as disabled / coming soon.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..config import SPECA_REPO_ROOT, SPECA_RUNS_DIR, USER_CLAUDE_DIR
from ..schemas.integrations import (
    IntegrationPaths,
    IntegrationsStatus,
    OpenInVSCodeRequest,
)
from ..services import cli_detect, launchers

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status", response_model=IntegrationsStatus)
def get_status() -> IntegrationsStatus:
    """Return whether ``code`` / ``gh`` are installed (and ``gh`` is authed)."""

    return cli_detect.get_status()


@router.post("/open-in-vscode")
def open_in_vscode(payload: OpenInVSCodeRequest) -> dict[str, bool]:
    """Spawn ``code`` to open ``payload.path`` (optionally at ``payload.line``).

    The launcher is fire-and-forget; we never wait on the spawned process.
    A successful spawn returns ``{"ok": true}`` immediately. Failure to
    locate the ``code`` binary maps to a 503 with a structured body so the
    SPA can show a "VSCode CLI not found" hint without parsing free text.
    """

    try:
        launchers.open_in_vscode(payload.path, payload.line)
    except FileNotFoundError as exc:
        logger.warning("integrations.open_in_vscode: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "vscode_cli_not_found",
                "hint": "Install VSCode CLI",
            },
        ) from exc
    except ValueError as exc:
        # Defensive: Pydantic should have caught empty paths already.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("integrations.open_in_vscode: launch failed")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "vscode_launch_failed",
                "hint": str(exc),
            },
        ) from exc

    return {"ok": True}


@router.get("/paths", response_model=IntegrationPaths)
def get_paths() -> IntegrationPaths:
    """Return absolute filesystem paths the SPA feeds into ``<OpenInVSCode>``.

    Slice G uses this endpoint to populate the Settings page maintenance
    links and the per-row "Open in VSCode" actions on Runs / Findings —
    the frontend has no other way to learn the SPECA repo root because
    Vite is served from the same origin but cannot reach the host FS.

    Paths are *absolute strings* (not URLs) and may contain backslashes on
    Windows; the VSCode CLI accepts either form so we leave them as-is.
    """

    # ``SPECA_RUNS_DIR`` resolves to ``<repo>/.speca/runs`` — its parent is
    # the ``.speca/`` directory the user wants to open.
    speca_dir = SPECA_RUNS_DIR.parent
    return IntegrationPaths(
        repo_root=str(SPECA_REPO_ROOT),
        speca_dir=str(speca_dir),
        claude_dir=str(USER_CLAUDE_DIR),
    )

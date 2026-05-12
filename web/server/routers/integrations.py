"""Integrations router — local CLI detection and "Open in VSCode".

Endpoints:

* ``GET  /api/integrations/status`` — read-only snapshot of whether
  ``code`` and ``gh`` are installed (and, for ``gh``, whether the user is
  logged in). Cached server-side for ~30 s; the SPA additionally treats
  the query as fresh for 60 s.
* ``POST /api/integrations/open-in-vscode`` — fire-and-forget ``code``
  spawn. Returns ``{"ok": true}`` on success, ``503`` with a structured
  ``vscode_cli_not_found`` body if ``code`` is missing.
* ``POST /api/integrations/fork`` — wrap ``gh repo fork`` to fork
  ``target_repo`` into the user's GH account (or a chosen org). The
  endpoint requires ``confirmed: true`` so the frontend ConfirmDialog is
  the only way to trigger a write — there is no implicit yes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..config import SPECA_REPO_ROOT, SPECA_RUNS_DIR, USER_CLAUDE_DIR
from ..schemas.integrations import (
    ForkRequest,
    ForkResponse,
    IntegrationPaths,
    IntegrationsStatus,
    OpenInVSCodeRequest,
)
from ..services import cli_detect, launchers
from ..services.launchers import GhForkFailed, GhNotAuthenticated

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


@router.post("/fork", response_model=ForkResponse)
def fork_target_repo(req: ForkRequest) -> ForkResponse:
    """Fork ``req.target_repo`` to the user's GH account via ``gh repo fork``.

    Failure modes are surfaced as structured HTTP errors:

    * ``400 confirmation_required``  — ``confirmed`` was not set; the
      frontend ConfirmDialog gate has not been passed.
    * ``503 gh_cli_not_found``       — ``gh`` is not installed on PATH
      (mirrors the ``vscode_cli_not_found`` shape used by the
      open-in-vscode endpoint).
    * ``403 gh_not_authed``          — ``gh auth status`` reports no
      logged-in account. The hint instructs the user to run
      ``gh auth login``.
    * ``502 gh_fork_failed``         — ``gh repo fork`` exited non-zero
      for any other reason (target not found, rate limit, missing scope,
      ...). The stderr text is forwarded in ``detail`` so the user can
      diagnose it without checking server logs.

    On success returns ``ForkResponse`` with both the canonical
    ``https://github.com/...`` URL and the parsed ``owner/repo`` token.
    """

    if not req.confirmed:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "confirmation_required",
                "hint": (
                    "frontend must set confirmed: true after "
                    "ConfirmDialog approval"
                ),
            },
        )

    cli = cli_detect.get_status()
    # ``cli`` is a pydantic model; use attribute access (``.gh.installed``)
    # rather than dict subscripts so we keep the contract single-source.
    if not cli.gh.installed:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "gh_cli_not_found",
                "hint": "Install gh CLI: https://cli.github.com/",
            },
        )

    try:
        result = launchers.gh_repo_fork(req.target_repo, req.into_owner)
    except FileNotFoundError as exc:
        # Race window: ``cli_detect`` reported gh installed but the binary
        # has since been removed. Treat the same as the pre-flight miss.
        logger.warning("integrations.fork: gh disappeared mid-request: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "gh_cli_not_found",
                "hint": "Install gh CLI: https://cli.github.com/",
            },
        ) from exc
    except GhNotAuthenticated as exc:
        logger.warning("integrations.fork: not authed (%s)", exc)
        raise HTTPException(
            status_code=403,
            detail={
                "error": "gh_not_authed",
                "hint": "Run `gh auth login` first",
            },
        ) from exc
    except GhForkFailed as exc:
        logger.warning("integrations.fork: gh repo fork failed (%s)", exc)
        raise HTTPException(
            status_code=502,
            detail={
                "error": "gh_fork_failed",
                "detail": str(exc),
            },
        ) from exc

    return ForkResponse(**result)

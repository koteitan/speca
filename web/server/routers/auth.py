"""Auth router for the SPECA web UI.

Endpoints:

* ``GET  /api/auth/status``   — read-only login probe used by the SPA on boot.
* ``POST /api/auth/api-key``  — write an Anthropic API key into the shared
  ``~/.claude/credentials.json`` file. The raw key only flows in via the
  request body; the response is the post-write :class:`AuthStatus`.
* ``POST /api/auth/login``    — placeholder for the OAuth (claude.ai) flow.
  v0 returns HTTP 202 with a stub body; Slice / version that lands the real
  flow will swap the implementation without changing the URL.

The router is intentionally thin: it delegates all credentials I/O to
:mod:`web.server.services.credentials` so unit tests can target that module
without spinning up FastAPI.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from ..schemas.auth import ApiKeyRequest, AuthStatus
from ..services import credentials as credentials_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status", response_model=AuthStatus)
def get_status() -> AuthStatus:
    """Report whether the user is logged in. Never returns key material."""

    return credentials_service.get_status()


@router.post("/api-key", response_model=AuthStatus)
def set_api_key(payload: ApiKeyRequest) -> AuthStatus:
    """Persist ``payload.key`` as the Anthropic API key.

    On success returns the freshly-computed :class:`AuthStatus` so the SPA
    can update its cache from a single round trip.
    """

    try:
        credentials_service.set_api_key(payload.key)
    except ValueError as exc:
        # Pydantic validation already enforces ``min_length=1``; this guards
        # the service-layer invariant for callers other than the HTTP layer.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("auth.api_key: failed to persist credentials")
        raise HTTPException(
            status_code=500,
            detail=f"failed to write credentials file: {exc}",
        ) from exc

    return credentials_service.get_status()


@router.post("/login")
def start_oauth_login() -> JSONResponse:
    """Spawn the ``claude auth login`` CLI in a new console for OAuth.

    The official Claude Code CLI handles the OAuth dance with claude.ai and
    writes the resulting tokens to ``~/.claude/credentials.json``. We detach
    the subprocess so the FastAPI request returns immediately; the user
    completes the OAuth flow in their browser, then the SPA's polling on
    ``/api/auth/status`` sees ``logged_in=True, method="oauth"``.
    """

    claude_path = shutil.which("claude") or (
        shutil.which("claude.cmd") if sys.platform == "win32" else None
    )
    if claude_path is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "claude CLI not found on PATH. Install Claude Code "
                "(npm install -g @anthropic-ai/claude-code) then retry."
            ),
        )

    cmd = [claude_path, "auth", "login"]
    creation_flags = 0
    if sys.platform == "win32":
        # CREATE_NEW_CONSOLE = 0x00000010 — pops a visible window so the user
        # sees the OAuth URL the CLI prints. CREATE_NO_WINDOW would hide it
        # but then the user has no way to copy the URL on machines where the
        # auto-launched browser fails (e.g. headless WSL).
        creation_flags = 0x00000010

    try:
        subprocess.Popen(  # noqa: S603 — claude_path resolved via shutil.which
            cmd,
            shell=False,
            stdin=None,
            stdout=None,
            stderr=None,
            creationflags=creation_flags,
            close_fds=True,
        )
    except OSError as exc:
        logger.exception("auth.login: failed to spawn `claude auth login`")
        raise HTTPException(
            status_code=500,
            detail=f"failed to spawn claude CLI: {exc}",
        ) from exc

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "spawned",
            "hint": (
                "A console window has opened (or claude is running in your "
                "terminal). Complete the OAuth flow in the browser that "
                "opens, then return here — the login state will refresh "
                "automatically within a few seconds."
            ),
        },
    )

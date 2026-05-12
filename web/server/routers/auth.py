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
def login_stub() -> JSONResponse:
    """v0 stub for the claude.ai OAuth flow.

    Returns HTTP 202 ("Accepted") with a payload that the SPA can branch on
    to render the "not yet — use an API key" hint. The real implementation
    will live behind the same URL in a future slice/version.
    """

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "not_implemented_in_v0",
            "hint": "Use API key for now",
        },
    )

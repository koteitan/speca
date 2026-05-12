"""HTTP routes for the Project Picker.

Slice F (v0 minimal) exposes the read-only "Saved targets" endpoint
described in Section 7.1 of ``docs/UI_DESIGN.md``. Slice B3 layers the
``POST /picker/fetch_url`` endpoint (B. "From URL" flow) on top of the
same router so the wiring in ``main.py`` does not have to change.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from web.server.schemas.picker import (
    FetchUrlRequest,
    FetchUrlResponse,
    SavedTarget,
)
from web.server.services import bounty_scope
from web.server.services.bounty_scope import (
    AnthropicUnreachable,
    BountyScopeError,
    InvalidScopeResponse,
)
from web.server.services.saved_targets import list_saved_targets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/picker", tags=["picker"])


@router.get("/saved", response_model=list[SavedTarget])
def get_saved_targets() -> list[SavedTarget]:
    """Return the Saved targets list (demo seed first, then history)."""

    return list_saved_targets()


@router.post("/fetch_url", response_model=FetchUrlResponse)
async def fetch_url(req: FetchUrlRequest) -> FetchUrlResponse:
    """Extract bug-bounty scope from ``req.bug_bounty_url`` via the Anthropic SDK.

    This is the SDK equivalent of ``Step 0a`` in
    ``.github/workflows/full-audit.yml``. Errors are mapped to:

    * ``503 anthropic_unreachable`` — SDK failure / no API key / timeout.
      ``retryable=True`` because the cause is usually transient.
    * ``502 invalid_scope_response`` — Anthropic answered but the response
      could not be parsed into the schema (rare — :mod:`bounty_scope`
      normally falls back to populating ``notes`` rather than raising).
    * ``500`` — any other :class:`BountyScopeError` subclass.
    """

    try:
        result = await bounty_scope.fetch_scope_from_url(
            str(req.bug_bounty_url), req.contract_addresses
        )
        return FetchUrlResponse(**result)
    except AnthropicUnreachable as exc:
        # SPA renders a retry button + "set API key" hint based on the
        # ``retryable`` flag — see docs/UI_DESIGN.md § 7.2.
        raise HTTPException(
            status_code=503,
            detail={
                "error": "anthropic_unreachable",
                "retryable": True,
                "message": str(exc),
            },
        ) from exc
    except InvalidScopeResponse as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "invalid_scope_response",
                "message": str(exc),
            },
        ) from exc
    except BountyScopeError as exc:
        # Catch-all so a new subclass added later still produces a clean
        # error envelope instead of leaking through as a 500 with no body.
        logger.exception("picker.fetch_url: scope extraction failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

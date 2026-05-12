"""HTTP routes for the Project Picker.

Slice F (v0 minimal) only exposes the read-only "Saved targets" endpoint
described in Section 7.1 of ``docs/UI_DESIGN.md``. Future slices will
add ``POST /picker/fetch_url`` (B. From URL flow) under this same
router so the wiring in ``main.py`` does not have to change again.
"""

from __future__ import annotations

from fastapi import APIRouter

from web.server.schemas.picker import SavedTarget
from web.server.services.saved_targets import list_saved_targets

router = APIRouter(prefix="/api/picker", tags=["picker"])


@router.get("/saved", response_model=list[SavedTarget])
def get_saved_targets() -> list[SavedTarget]:
    """Return the Saved targets list (demo seed first, then history)."""

    return list_saved_targets()

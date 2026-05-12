"""Pydantic schemas for the Project Picker (Saved targets) API.

Slice F provides a minimal v0 surface — a single read-only endpoint that
lists targets the user has already audited locally, plus a hard-coded
demo entry so the empty state is avoided on first launch (Section 4.10.7
of ``docs/UI_DESIGN.md``).

The schema intentionally keeps every field nullable except ``target_repo``
because:

* ``bug_bounty_url`` is not always known — manifests written before
  Slice 0 may not have it.
* ``target_ref`` defaults to the upstream branch when omitted by the
  pipeline; surfacing ``None`` lets the SPA decide whether to display a
  placeholder.
* ``last_run_at`` is ``None`` for the demo seed (no history yet).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SavedTarget(BaseModel):
    """One row in ``GET /api/picker/saved``.

    ``source`` is the discriminator the SPA uses to render a "demo" badge
    on the seed entry without an extra heuristic on the client side.
    """

    model_config = ConfigDict(extra="forbid")

    bug_bounty_url: str | None = None
    target_repo: str
    target_ref: str | None = None
    last_run_at: datetime | None = None
    source: Literal["history", "demo"]

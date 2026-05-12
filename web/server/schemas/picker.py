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

from pydantic import BaseModel, ConfigDict, HttpUrl


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


# --- Slice B3: POST /picker/fetch_url -----------------------------------------
#
# ``FetchUrlRequest`` mirrors the input of the ``full-audit.yml`` Step 0a
# ``claude --print`` call: a bug bounty program URL plus an optional comma-
# separated list of extra contract addresses the operator wants forced into
# scope even when the program page omits them.
#
# ``FetchUrlResponse`` is the *flat* union of ``BUG_BOUNTY_SCOPE.json`` and
# ``EXTRACTED_INPUTS.json`` from that same workflow step — the SPA only needs
# one round trip to populate the Project Picker "From URL" form.


class FetchUrlRequest(BaseModel):
    """Body of ``POST /api/picker/fetch_url``.

    ``bug_bounty_url`` is validated as an HTTP(S) URL up-front so we never
    burn an Anthropic call on a typo. ``contract_addresses`` is intentionally
    a free-form comma-separated string to match the
    ``inputs.contract_addresses`` shape in ``.github/workflows/full-audit.yml``
    (Step 0a) — keeping the same surface means the SPA can later forward this
    value verbatim into a ``workflow_dispatch`` payload.
    """

    model_config = ConfigDict(extra="forbid")

    bug_bounty_url: HttpUrl
    contract_addresses: str | None = None


class ScopeContract(BaseModel):
    """One entry in :pyattr:`FetchUrlResponse.in_scope_contracts`.

    ``network`` and ``name`` are optional because many programs list raw
    addresses without further metadata. The schema deliberately mirrors the
    object shape the Action prompt asks Claude to produce
    (``{"address": "0x...", "network": "...", "name": "..."}``) so the
    extraction layer does not have to rename fields.
    """

    model_config = ConfigDict(extra="forbid")

    address: str
    network: str | None = None
    name: str | None = None


class FetchUrlResponse(BaseModel):
    """Flat scope payload returned by ``POST /api/picker/fetch_url``.

    Every field except ``program_url`` is optional / has a safe default so
    that a partially-extracted page (e.g. one where the model could not find
    a reward range) still produces a 200 — the SPA can prompt the user to
    fill the missing bits manually. ``spec_urls`` / ``keywords`` are
    comma-separated strings, not lists, to match
    ``outputs/EXTRACTED_INPUTS.json`` in the Action (``Step 0d`` consumes them
    via ``json.load(...)['spec_urls']``).
    """

    model_config = ConfigDict(extra="forbid")

    program_url: str
    program_name: str | None = None
    in_scope_assets: list[str] = []
    in_scope_contracts: list[ScopeContract] = []
    out_of_scope: list[str] = []
    severity_ratings: str | None = None
    reward_range: str | None = None
    notes: str | None = None
    spec_urls: str = ""
    keywords: str = ""

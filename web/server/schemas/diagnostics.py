"""Pydantic schemas for the diagnostics router.

The diagnostics endpoint is the web-UI counterpart of the planned
``speca doctor`` CLI command (see ``docs/SPECA_CLI_SPEC.md`` §6 / §11 M1).
It probes the local environment for the tools and credentials a SPECA run
depends on, and returns one :class:`ToolStatus` per tool plus a single
:class:`AuthStatus` block lifted from the existing auth router.

Shape rationale:

* Every probe returns the same :class:`ToolStatus` shape so the SPA can
  render the report as a uniform grid of chips. The only tool-specific
  bits live under ``details`` (e.g. ``gh.authed``, ``node.outdated``).
* ``status`` is a Literal so the SPA can switch on the exact set without
  having to coerce ``installed`` + ``outdated`` + ``details`` into a chip
  colour locally — the backend has more context to make the call.
* ``api_key_configured`` is a bool, never the key itself; we mirror the
  auth router's discipline of never echoing key material to the wire.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .auth import AuthStatus


ToolStatusLiteral = Literal["ok", "missing", "outdated", "unknown"]


class ToolStatus(BaseModel):
    """Common shape for an env-probe result.

    ``status`` is the chip colour the SPA renders:

    * ``ok``       — installed (and, if a min version applies, recent enough)
    * ``missing``  — binary not on PATH
    * ``outdated`` — installed but below a documented min version
    * ``unknown``  — the binary is present but ``--version`` produced no
      parseable output. Treated as a soft-fail in the UI.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    installed: bool
    version: str | None = None
    status: ToolStatusLiteral = "unknown"
    # Optional per-tool extras. Examples:
    #   { "authed": true }                  (gh)
    #   { "min_version": "20.0.0",
    #     "parsed_version": "22.4.1" }       (node)
    details: dict[str, object] | None = None


class DiagnosticsReport(BaseModel):
    """Snapshot returned by ``GET /api/diagnostics``."""

    model_config = ConfigDict(extra="forbid")

    node: ToolStatus
    uv: ToolStatus
    git: ToolStatus
    claude: ToolStatus
    gh: ToolStatus
    code: ToolStatus
    auth: AuthStatus
    api_key_configured: bool

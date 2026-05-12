"""Pydantic schemas for the integrations router.

The integrations slice surfaces local-machine state (whether ``code`` /
``gh`` are installed, whether ``gh auth`` is logged in) and accepts a single
write-style action — "open this path in VSCode". Schemas live here so they
can be reused by tests without importing the router module.

None of these models carry secrets: ``authed`` is a tri-state boolean that
only reflects ``gh auth status``' exit code, not the token itself.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CliDetected(BaseModel):
    """Common shape for "is this CLI installed?" probes.

    ``version`` is the first line of ``<cli> --version`` so callers can show
    a hint like "code 1.95.0" in the UI. It is ``None`` when the CLI is
    missing or the version probe failed for any reason — we never let a
    flaky subprocess turn the whole status endpoint into a 500.
    """

    model_config = ConfigDict(extra="forbid")

    installed: bool
    version: str | None = None


class GhStatus(CliDetected):
    """``gh`` CLI status with an additional ``authed`` flag.

    ``authed`` is ``True``/``False`` when the CLI is installed (mapping to the
    exit code of ``gh auth status``), and ``None`` when the CLI itself is
    missing — there is no auth state to report in that case.
    """

    authed: bool | None = None


class IntegrationsStatus(BaseModel):
    """Snapshot returned by ``GET /api/integrations/status``."""

    model_config = ConfigDict(extra="forbid")

    code: CliDetected
    gh: GhStatus


class OpenInVSCodeRequest(BaseModel):
    """Body of ``POST /api/integrations/open-in-vscode``.

    ``path`` is required and must be non-empty. The frontend is expected to
    pass an absolute path; the launcher will ``Path(path).resolve()`` either
    way so that ``..`` segments cannot escape silently. ``line`` is optional;
    when present we use ``code -g <path>:<line>``.
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    line: int | None = Field(default=None, ge=1)


class IntegrationPaths(BaseModel):
    """Absolute paths the SPA needs to feed into ``<OpenInVSCode>``.

    These are server-side absolute paths so the frontend never has to do its
    own filesystem reasoning (paths are ``Path`` objects on the server but
    serialised as strings — VSCode CLI accepts forward or back slashes).

    * ``repo_root``  — SPECA repo working tree (``web/server/config.SPECA_REPO_ROOT``)
    * ``speca_dir``  — ``<repo_root>/.speca`` (manifest + per-run state lives here)
    * ``claude_dir`` — ``~/.claude`` (credentials, skills, worktrees, ...)
    """

    model_config = ConfigDict(extra="forbid")

    repo_root: str
    speca_dir: str
    claude_dir: str

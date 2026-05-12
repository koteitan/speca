"""Pydantic schemas for the integrations router.

The integrations slice surfaces local-machine state (whether ``code`` /
``gh`` are installed, whether ``gh auth`` is logged in) and accepts a single
write-style action — "open this path in VSCode". Schemas live here so they
can be reused by tests without importing the router module.

None of these models carry secrets: ``authed`` is a tri-state boolean that
only reflects ``gh auth status``' exit code, not the token itself.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


# ---- POST /api/integrations/fork (Slice B4) ---------------------------------
#
# A single regex enforces the ``owner/repo`` shape — GitHub allows letters,
# digits, hyphens, underscores, and dots in both components (no spaces, no
# slashes inside a component). The check is intentionally narrow: we'd rather
# reject ``foo`` / ``a/b/c`` / ``owner repo`` outright than let an invalid
# string travel into the ``gh repo fork`` subprocess.

_TARGET_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


class ForkRequest(BaseModel):
    """Body of ``POST /api/integrations/fork``.

    The ``confirmed`` flag is the server-side checkpoint matching the
    frontend ``ConfirmDialog`` — there is no implicit "yes". A frontend bug
    that omits the flag must produce a 400 so we never spawn ``gh repo
    fork`` against a half-typed repo from a Settings page hot reload.
    """

    model_config = ConfigDict(extra="forbid")

    target_repo: str = Field(min_length=1, description="owner/repo")
    into_owner: str | None = Field(
        default=None, description="Optional org/user to fork into"
    )
    confirmed: bool = Field(
        default=False,
        description="Must be true; frontend ConfirmDialog gate",
    )

    @field_validator("target_repo")
    @classmethod
    def _validate_target_repo(cls, value: str) -> str:
        if not _TARGET_REPO_RE.match(value):
            raise ValueError(
                "target_repo must be in 'owner/repo' form "
                "(letters, digits, '.', '_', '-')"
            )
        return value


class ForkResponse(BaseModel):
    """Body of a successful ``POST /api/integrations/fork``.

    ``forked_repo`` is in the ``"<new_owner>/<repo_name>"`` form so the
    frontend can render it without re-parsing the URL, and ``fork_url`` is
    the canonical ``https://github.com/<owner>/<repo>`` we synthesize from
    the parsed owner+name pair (we never trust the raw ``gh`` stdout URL
    because its exact format has churned across releases).
    """

    model_config = ConfigDict(extra="forbid")

    fork_url: str
    forked_repo: str

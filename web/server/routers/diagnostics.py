"""Diagnostics router — web-UI equivalent of ``speca doctor``.

Endpoint:

* ``GET /api/diagnostics`` — read-only snapshot of the local environment
  (Node / uv / git / claude / gh / VSCode CLI) plus the existing
  auth-status block and an Anthropic-API-key-configured flag.

The router intentionally reuses the existing
:mod:`web.server.services.cli_detect` cache for ``claude`` / ``gh`` /
``code`` so the integration-status page and the diagnostics page agree on
those three tools without having to spawn duplicate subprocesses.

Failure isolation:

* Each probe runs independently with a 3 s timeout.
* Any unexpected exception inside an individual probe degrades to a
  ``missing`` result for that tool rather than failing the whole report.
* The endpoint itself never returns 5xx — a partially-degraded report is
  always more useful than no report.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from typing import Callable

from fastapi import APIRouter

from ..schemas.diagnostics import DiagnosticsReport, ToolStatus
from ..services import cli_detect, credentials as credentials_service, env_probe

logger = logging.getLogger(__name__)

router = APIRouter()


# 3 s budget for the claude probe — matches the env_probe / cli_detect
# convention so the worst-case latency of GET /api/diagnostics is bounded.
_PROBE_TIMEOUT_SECONDS = 3.0


def _safe(probe: Callable[[], ToolStatus], *, name: str) -> ToolStatus:
    """Run ``probe()`` and degrade any unexpected exception to ``missing``.

    The frontend renders a ``missing`` chip identically regardless of
    whether the binary was absent or the probe itself crashed — the user
    only cares that the tool is unusable. We still log the exception so
    the server-side trace is preserved.
    """

    try:
        return probe()
    except Exception:  # pragma: no cover - defensive
        logger.exception("diagnostics: probe %s crashed", name)
        return ToolStatus(name=name, installed=False, version=None, status="missing")


def _probe_claude_from_cli_detect() -> ToolStatus:
    """Probe ``claude`` (Claude Code CLI) standalone.

    ``cli_detect`` does not cover ``claude`` today (it is consumed by the
    auth router via :func:`credentials._ask_cli_for_status`), so we
    re-implement the small ``shutil.which`` + ``--version`` pattern here
    rather than widening ``cli_detect``'s public surface. Keeping it local
    means the existing ``GET /api/integrations/status`` contract stays
    byte-for-byte identical.
    """

    candidates = ("claude", "claude.cmd") if sys.platform == "win32" else ("claude",)
    binary = None
    for cand in candidates:
        hit = shutil.which(cand)
        if hit:
            binary = hit
            break

    if binary is None:
        return ToolStatus(name="claude", installed=False, status="missing")

    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            shell=False,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("diagnostics: claude --version failed (%s)", exc)
        return ToolStatus(name="claude", installed=True, status="unknown")

    output = (result.stdout or result.stderr or "").strip()
    first_line = next((ln.strip() for ln in output.splitlines() if ln.strip()), None)

    return ToolStatus(
        name="claude",
        installed=True,
        version=first_line,
        status="ok" if first_line else "unknown",
    )


def _probe_code_from_cli_detect() -> ToolStatus:
    """Re-shape ``cli_detect``'s ``code`` block as a :class:`ToolStatus`."""

    snapshot = cli_detect.get_status()
    cd = snapshot.code
    if not cd.installed:
        return ToolStatus(name="code", installed=False, status="missing")
    return ToolStatus(
        name="code",
        installed=True,
        version=cd.version,
        status="ok" if cd.version else "unknown",
    )


def _probe_gh_from_cli_detect() -> ToolStatus:
    """Re-shape ``cli_detect``'s ``gh`` block as a :class:`ToolStatus`.

    Adds ``details.authed`` so the SPA can render a sub-line "logged in /
    not logged in" without a second round trip.
    """

    snapshot = cli_detect.get_status()
    gh = snapshot.gh
    if not gh.installed:
        return ToolStatus(name="gh", installed=False, status="missing")

    details: dict[str, object] = {"authed": gh.authed}
    return ToolStatus(
        name="gh",
        installed=True,
        version=gh.version,
        status="ok" if gh.version else "unknown",
        details=details,
    )


def _api_key_configured() -> bool:
    """Return ``True`` if an Anthropic API key looks usable.

    Two sources, in order:

    1. ``ANTHROPIC_API_KEY`` environment variable (set + non-empty).
    2. ``apiKey`` field in ``~/.claude/credentials.json``.

    The actual key material is never returned — only a boolean. Mirrors
    the discipline of ``AuthStatus`` which also keeps the key off the
    wire.
    """

    env_key = os.environ.get("ANTHROPIC_API_KEY") or ""
    if env_key.strip():
        return True

    try:
        data = credentials_service._load_raw()  # pragma: no cover - exercised below via test
    except Exception:  # pragma: no cover - defensive
        return False

    api_key = data.get("apiKey")
    return isinstance(api_key, str) and bool(api_key.strip())


# === routers: diagnostics ===
@router.get("/diagnostics", response_model=DiagnosticsReport)
def get_diagnostics() -> DiagnosticsReport:
    """Return a snapshot of local-environment health.

    Reuses :mod:`cli_detect` for the three tools it already caches so
    repeated calls to ``/api/integrations/status`` + ``/api/diagnostics``
    only pay for one set of subprocesses every ~30 s.
    """

    node = _safe(env_probe.probe_node, name="node")
    uv = _safe(env_probe.probe_uv, name="uv")
    git = _safe(env_probe.probe_git, name="git")
    claude = _safe(_probe_claude_from_cli_detect, name="claude")
    gh = _safe(_probe_gh_from_cli_detect, name="gh")
    code = _safe(_probe_code_from_cli_detect, name="code")

    try:
        auth = credentials_service.get_status()
    except Exception:  # pragma: no cover - defensive
        logger.exception("diagnostics: credentials.get_status failed")
        from ..schemas.auth import AuthStatus

        auth = AuthStatus(logged_in=False, method=None, identity=None)

    return DiagnosticsReport(
        node=node,
        uv=uv,
        git=git,
        claude=claude,
        gh=gh,
        code=code,
        auth=auth,
        api_key_configured=_api_key_configured(),
    )

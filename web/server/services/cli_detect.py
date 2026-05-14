"""Detect local CLI tools (``code``, ``gh``) and probe their state.

Two callers:

* :mod:`web.server.routers.integrations` — the ``GET /status`` endpoint
* :mod:`web.server.services.launchers` — needs to know whether ``code`` is
  reachable before spawning it

Implementation notes:

* ``shutil.which`` already consults ``PATHEXT`` on Windows so ``code`` will
  resolve to ``code.cmd`` automatically in most cases — we add a manual
  ``.cmd`` retry only as a safety net for shells that have stripped it from
  ``PATHEXT``.
* All subprocess invocations use ``shell=False``, a 3-second timeout, and
  swallow failures (``OSError``, ``subprocess.TimeoutExpired``) into
  ``None``. Status endpoints must never throw.
* The whole status snapshot is cached for ~30 seconds. The cache key is
  empty (a single shared result) because the detection result depends on
  the user's machine state, not on any request parameter.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional

from ..schemas.integrations import CliDetected, GhStatus, IntegrationsStatus

logger = logging.getLogger(__name__)

# 3-second cap per subprocess; if ``--version`` or ``gh auth status`` is
# slower than this on the user's machine something is already broken and
# we'd rather return a stale-ish "not detected" than freeze the API.
_PROBE_TIMEOUT_SECONDS = 3.0

# Cache TTL for the full snapshot. The frontend stale time is 60 seconds
# (see useIntegrationsStatus); we cache shorter so a user who runs
# ``gh auth login`` mid-session can see the change with a single refetch.
_CACHE_TTL_SECONDS = 30.0


@dataclass(frozen=True)
class _Probe:
    """Resolved CLI binary path and parsed version string."""

    path: Optional[str]
    version: Optional[str]


def _which(*candidates: str) -> Optional[str]:
    """Return the first ``which`` hit among ``candidates``.

    On Windows, ``shutil.which("code")`` normally resolves to ``code.cmd``
    via ``PATHEXT``. We still pass ``code.cmd`` as an explicit fallback for
    shells (or PowerShell profiles) that mangle ``PATHEXT``.
    """

    for candidate in candidates:
        hit = shutil.which(candidate)
        if hit:
            return hit
    return None


def _version_line(binary: str) -> Optional[str]:
    """Run ``<binary> --version`` and return its first non-empty line."""

    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("cli_detect: %s --version failed (%s)", binary, exc)
        return None

    # ``gh --version`` writes to stdout; ``code --version`` does too.
    # Fall back to stderr if stdout is empty so we don't silently miss data.
    output = result.stdout or result.stderr or ""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _probe_code() -> _Probe:
    binary = _which("code", "code.cmd") if sys.platform == "win32" else _which("code")
    if not binary:
        return _Probe(path=None, version=None)
    return _Probe(path=binary, version=_version_line(binary))


def _probe_gh() -> _Probe:
    binary = _which("gh", "gh.exe") if sys.platform == "win32" else _which("gh")
    if not binary:
        return _Probe(path=None, version=None)
    return _Probe(path=binary, version=_version_line(binary))


def _gh_authed(binary: str) -> Optional[bool]:
    """Return whether ``gh auth status`` reports a logged-in account.

    Strategy: ``gh auth status`` exits 0 if at least one host has working
    credentials, non-zero otherwise. We don't need to parse stdout/stderr —
    the exit code is the signal the UI needs.

    The ``--json`` flag is *not* universally supported by older ``gh``
    versions for ``auth status``; we pass ``hostname`` only when supported
    is not detected (i.e. we just don't pass it). The bare command is
    enough for v0.
    """

    try:
        result = subprocess.run(
            [binary, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("cli_detect: gh auth status failed (%s)", exc)
        return None

    return result.returncode == 0


# ---- module-level TTL cache --------------------------------------------------
#
# We keep the cache state in module-level variables rather than using
# ``functools.lru_cache`` because we want a *time-based* eviction (lru_cache
# is purely size-based). The implementation is intentionally simple — no
# locking — because FastAPI's default sync endpoint runs in a threadpool and
# a small race that produces an extra subprocess call is harmless.

_cached_status: Optional[IntegrationsStatus] = None
_cached_at: float = 0.0


def _compute_status() -> IntegrationsStatus:
    code_probe = _probe_code()
    gh_probe = _probe_gh()

    code = CliDetected(
        installed=code_probe.path is not None,
        version=code_probe.version,
    )

    if gh_probe.path is None:
        gh = GhStatus(installed=False, version=None, authed=None)
    else:
        gh = GhStatus(
            installed=True,
            version=gh_probe.version,
            authed=_gh_authed(gh_probe.path),
        )

    return IntegrationsStatus(code=code, gh=gh)


def get_status(force: bool = False) -> IntegrationsStatus:
    """Return a cached :class:`IntegrationsStatus` snapshot.

    ``force=True`` bypasses the TTL cache and is used by tests.
    """

    global _cached_status, _cached_at

    now = time.monotonic()
    if (
        not force
        and _cached_status is not None
        and now - _cached_at < _CACHE_TTL_SECONDS
    ):
        return _cached_status

    snapshot = _compute_status()
    _cached_status = snapshot
    _cached_at = now
    return snapshot


def find_code_binary() -> Optional[str]:
    """Return the resolved path to ``code`` (or ``code.cmd`` on Windows).

    Used by the launcher to bypass the status cache — when the user clicks
    "Open in VSCode" we always want to use the freshest ``which`` hit.
    """

    if sys.platform == "win32":
        return _which("code", "code.cmd")
    return _which("code")

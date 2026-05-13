"""Local environment probes for the ``/api/diagnostics`` endpoint.

Each ``probe_<tool>()`` function returns a :class:`ToolStatus` describing
whether the binary is installed, what version it reports, and (when a
documented minimum applies) whether the version satisfies that minimum.

All subprocess invocations follow the same Phase-0a pattern that
:mod:`web.server.services.cli_detect` already uses:

* ``shell=False``, ``capture_output=True``
* 3-second timeout (``_PROBE_TIMEOUT_SECONDS``)
* ``encoding="utf-8"`` with ``errors="replace"`` so Windows ``code.cmd``
  output (occasionally mixed CP932 + UTF-8) does not crash the probe
* ``OSError`` / ``TimeoutExpired`` are swallowed — every probe must
  degrade to a clean ``missing`` rather than raise.

This module is intentionally independent of ``cli_detect`` so the two
slices can evolve in parallel; the ``claude`` / ``gh`` / ``code`` probes
needed by ``/api/diagnostics`` are *thin re-uses* of ``cli_detect`` to
keep the integration-status cache as the single source of truth for those
three tools.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from ..schemas.diagnostics import ToolStatus

logger = logging.getLogger(__name__)

# Same 3 s budget as cli_detect — anything slower than this is already
# broken on the user's machine; we'd rather return ``missing`` than freeze
# the endpoint.
_PROBE_TIMEOUT_SECONDS = 3.0

# Node minimum version. Matches the CLI spec (§10.1 / §11 M7 "Node >= 20")
# and `package.json` engines field if present.
NODE_MIN_VERSION: tuple[int, int, int] = (20, 0, 0)


@dataclass(frozen=True)
class _Probe:
    path: Optional[str]
    version: Optional[str]


# ---- low-level helpers ------------------------------------------------------


def _which(*candidates: str) -> Optional[str]:
    """Return the first ``shutil.which`` hit among ``candidates``.

    On Windows we add ``<name>.cmd`` / ``<name>.exe`` variants so probes
    keep working when ``PATHEXT`` has been stripped by a custom shell
    profile — the same pattern cli_detect uses.
    """

    for candidate in candidates:
        hit = shutil.which(candidate)
        if hit:
            return hit
    return None


def _windows_candidates(name: str) -> tuple[str, ...]:
    """Return ``(name, name.cmd, name.exe)`` on Windows, ``(name,)`` elsewhere."""

    if sys.platform == "win32":
        return (name, f"{name}.cmd", f"{name}.exe")
    return (name,)


def _version_line(binary: str, *, args: tuple[str, ...] = ("--version",)) -> Optional[str]:
    """Run ``<binary> <args...>`` and return the first non-empty output line.

    ``--version`` is the universal pattern; ``args`` is parameterised only
    so the few tools that need ``-v`` or ``--version-only`` can override
    without copy-pasting the timeout/encoding boilerplate.
    """

    try:
        result = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            shell=False,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("env_probe: %s %s failed (%s)", binary, " ".join(args), exc)
        return None

    output = result.stdout or result.stderr or ""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


_SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _parse_semver(text: str) -> Optional[tuple[int, int, int]]:
    """Extract the first ``x.y.z`` triple from ``text``.

    Tools print the version in different shapes (``v22.4.1``,
    ``node v22.4.1``, ``git version 2.45.2``, ``uv 0.4.18 (commit ...)``,
    ``2.50.0``). Searching for the first triple is more robust than
    splitting on whitespace.
    """

    match = _SEMVER_RE.search(text)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _status_for(
    *,
    name: str,
    probe: _Probe,
    min_version: Optional[tuple[int, int, int]] = None,
    details: Optional[dict[str, object]] = None,
) -> ToolStatus:
    """Translate a raw :class:`_Probe` into a :class:`ToolStatus`.

    Decision table:

    * ``path`` missing                                    → ``missing``
    * ``path`` present, no version parsed                 → ``unknown``
    * ``path`` present, version below ``min_version``     → ``outdated``
    * ``path`` present, version OK (or no min)            → ``ok``
    """

    if probe.path is None:
        return ToolStatus(
            name=name,
            installed=False,
            version=None,
            status="missing",
            details=details,
        )

    if probe.version is None:
        return ToolStatus(
            name=name,
            installed=True,
            version=None,
            status="unknown",
            details=details,
        )

    if min_version is not None:
        parsed = _parse_semver(probe.version)
        merged_details = dict(details or {})
        merged_details["min_version"] = "{}.{}.{}".format(*min_version)
        if parsed is not None:
            merged_details["parsed_version"] = "{}.{}.{}".format(*parsed)
            if parsed < min_version:
                return ToolStatus(
                    name=name,
                    installed=True,
                    version=probe.version,
                    status="outdated",
                    details=merged_details,
                )
        return ToolStatus(
            name=name,
            installed=True,
            version=probe.version,
            status="ok",
            details=merged_details,
        )

    return ToolStatus(
        name=name,
        installed=True,
        version=probe.version,
        status="ok",
        details=details,
    )


# ---- public probes ----------------------------------------------------------


def _probe_binary(*candidates: str) -> _Probe:
    binary = _which(*candidates)
    if binary is None:
        return _Probe(path=None, version=None)
    return _Probe(path=binary, version=_version_line(binary))


def probe_node() -> ToolStatus:
    """Probe the Node.js runtime. Enforces ``>= 20.0.0`` per CLI spec."""

    probe = _probe_binary(*_windows_candidates("node"))
    return _status_for(name="node", probe=probe, min_version=NODE_MIN_VERSION)


def probe_uv() -> ToolStatus:
    """Probe the ``uv`` Python launcher used by the orchestrator."""

    probe = _probe_binary(*_windows_candidates("uv"))
    return _status_for(name="uv", probe=probe)


def probe_git() -> ToolStatus:
    """Probe git. Used for both the SPECA repo and target-repo clones."""

    probe = _probe_binary(*_windows_candidates("git"))
    return _status_for(name="git", probe=probe)

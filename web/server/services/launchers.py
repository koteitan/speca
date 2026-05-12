"""Spawn helpers for external tools (currently: VSCode).

This module is deliberately small — it owns the "fork off a detached
process, never block the request" pattern so the router never has to deal
with subprocess primitives directly. Two invariants:

1. **``shell=False`` always.** On Windows, the user's ``code`` install can
   live under a path containing spaces (``C:\\Program Files\\...``). Any
   ``shell=True`` invocation has to manually quote the command line, which
   has historically been an endless source of CVE-grade bugs in editors.
   Passing a list with ``shell=False`` makes the OS do the quoting.
2. **Detach immediately.** ``code`` returns once the existing VSCode
   process picks up the file, but we still don't want a 30s click delay
   if VSCode is launching cold. ``Popen`` with discarded stdio handles is
   enough; we deliberately do not ``wait()``.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from . import cli_detect

logger = logging.getLogger(__name__)

# ``CREATE_NO_WINDOW`` suppresses the brief black ``cmd.exe`` flash that
# Windows otherwise shows when ``Popen`` spawns a console subprocess. The
# constant is only defined on Windows builds of the Python stdlib, so we
# guard the import with a platform check.
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# ``gh repo fork`` blocking time is dominated by network round-trips to
# GitHub; 60 s comfortably covers a slow corporate proxy without letting a
# silently-hung CLI freeze the API worker forever.
_GH_FORK_TIMEOUT_SECONDS = 60.0

# Some Windows installers register ``gh.exe`` only via the per-user
# ``%LOCALAPPDATA%\Programs\GitHub CLI`` path; ``shutil.which`` covers that
# via ``PATHEXT`` already, but we list both candidates for parity with the
# ``code`` resolver above.


class GhNotAuthenticated(RuntimeError):
    """Raised when ``gh auth status`` reports no logged-in account.

    The router maps this to HTTP 403 with a structured ``gh_not_authed``
    body so the SPA can show a "Run ``gh auth login``" hint without parsing
    free-text error messages.
    """


class GhForkFailed(RuntimeError):
    """Raised when ``gh repo fork`` exits non-zero for any other reason.

    Common causes: target repo does not exist, network error, GitHub rate
    limit, or the user's PAT lacks the ``public_repo`` scope. The router
    maps this to HTTP 502 (``gh_fork_failed``); the exception message
    carries the verbatim ``gh`` stderr so a human can diagnose it from the
    response body.
    """


def open_in_vscode(path: str, line: Optional[int] = None) -> None:
    """Spawn ``code`` to open ``path`` (optionally jumping to ``line``).

    ``path`` is resolved with ``strict=False`` so that the launcher will
    happily open a file/folder that does not exist yet — VSCode itself
    handles "this path is missing" with its own UX, and refusing to spawn
    here would surprise users who type a path into a chat panel.

    Raises:
        FileNotFoundError: ``code`` (and on Windows ``code.cmd``) is not
            on ``PATH``. The router converts this into HTTP 503 with a
            structured ``vscode_cli_not_found`` body.
    """

    if not path or not path.strip():
        # Pydantic enforces ``min_length=1`` at the router boundary, but
        # the service-layer invariant should hold for any caller.
        raise ValueError("path must be a non-empty string")

    binary = cli_detect.find_code_binary()
    if binary is None:
        raise FileNotFoundError(
            "VSCode CLI ('code') not found on PATH. "
            "Install VSCode and run the 'Shell Command: Install \\'code\\' "
            "command in PATH' action from the command palette."
        )

    # ``resolve(strict=False)`` keeps Windows backslashes intact (no slash
    # normalisation) and produces an absolute path that ``code`` can open
    # regardless of the cwd uvicorn was launched from.
    resolved = Path(path).resolve(strict=False)

    if line is not None:
        cmd = [binary, "-g", f"{resolved}:{line}"]
    else:
        cmd = [binary, str(resolved)]

    logger.info("launchers.open_in_vscode: spawning %s", cmd)

    try:
        subprocess.Popen(  # noqa: S603 — shell=False, args are a list
            cmd,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
            close_fds=True,
        )
    except FileNotFoundError:
        # Re-raise unchanged so the router maps it to the documented
        # ``vscode_cli_not_found`` 503 response. This catches the edge case
        # where ``cli_detect`` reported a binary that has since been
        # removed from disk between the status query and the click.
        raise
    except OSError as exc:
        # Any other OS-level spawn failure (permission denied,
        # ENOEXEC, ...) — surface it as a launch failure so the UI can
        # show a useful toast.
        logger.exception("launchers.open_in_vscode: spawn failed")
        raise RuntimeError(f"failed to launch VSCode: {exc}") from exc


# ---- gh repo fork ----------------------------------------------------------
#
# ``gh repo fork`` stdout has churned across releases — we've observed at
# least these shapes in the wild:
#
#   "<owner>/<repo> already exists"
#   "✓ Created fork <owner>/<repo>"
#   "Created fork <owner>/<repo>"
#
# The regex below tolerates an optional leading status glyph + words and
# captures the first ``<token>/<token>`` it sees. We do *not* trust any
# URL ``gh`` prints — instead we re-synthesize ``https://github.com/...``
# from the parsed ``owner/repo`` so the response stays stable even when
# ``gh`` swaps its output format again.

_GH_FORK_OUTPUT_RE = re.compile(
    r"([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)"
)


def _find_gh_binary() -> Optional[str]:
    """Resolve the ``gh`` binary on PATH.

    Mirrors the ``code`` resolver: ``shutil.which`` covers Windows' PATHEXT
    in the common case, but we list ``gh.exe`` explicitly as a defensive
    fallback for shells with a mangled PATHEXT.
    """

    if sys.platform == "win32":
        return shutil.which("gh") or shutil.which("gh.exe")
    return shutil.which("gh")


def _run_gh(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    """Run ``gh`` with our standard subprocess flags.

    Centralised so every ``gh`` call shares the same ``shell=False`` +
    ``CREATE_NO_WINDOW`` defaults — the launcher should never grow ad-hoc
    spawn sites.
    """

    return subprocess.run(  # noqa: S603 — shell=False, args are a list
        args,
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        creationflags=_CREATE_NO_WINDOW,
    )


def gh_repo_fork(
    target_repo: str, into_owner: Optional[str] = None
) -> dict[str, str]:
    """Fork ``target_repo`` to the user's GH account via ``gh repo fork``.

    Spawns ``gh repo fork <repo> --clone=false --remote=false`` (plus
    ``--org <into_owner>`` when provided) with a 60 s timeout. We verify
    ``gh auth status`` first so a missing login produces a structured 403
    instead of a generic 502.

    Returns:
        ``{"fork_url": "https://github.com/<owner>/<repo>",
           "forked_repo": "<owner>/<repo>"}``

    Raises:
        FileNotFoundError: ``gh`` CLI is not on PATH.
        GhNotAuthenticated: ``gh auth status`` reports no logged-in
            account.
        GhForkFailed: ``gh repo fork`` exited non-zero for any other
            reason; the exception message carries the stderr text.
    """

    gh_path = _find_gh_binary()
    if gh_path is None:
        raise FileNotFoundError(
            "gh CLI not found on PATH. Install from https://cli.github.com/"
        )

    # ``gh auth status`` is cheap (no network in most cases — it inspects
    # the on-disk credential file) so paying for it on every fork avoids
    # the messy ``gh repo fork`` failure mode where the CLI prompts on
    # stderr for a browser login that will never happen in a subprocess.
    try:
        auth = _run_gh([gh_path, "auth", "status"], timeout=10.0)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("launchers.gh_repo_fork: auth probe failed (%s)", exc)
        raise GhNotAuthenticated(
            "gh auth status probe failed; run `gh auth login`"
        ) from exc
    if auth.returncode != 0:
        raise GhNotAuthenticated(
            (auth.stderr or auth.stdout or "gh auth status reported non-zero").strip()
        )

    cmd = [gh_path, "repo", "fork", target_repo, "--clone=false", "--remote=false"]
    if into_owner:
        # ``--org`` is the documented flag for forking into an
        # organisation. Personal forks pass no flag — gh defaults to the
        # logged-in user's account.
        cmd.extend(["--org", into_owner])

    logger.info("launchers.gh_repo_fork: spawning %s", cmd)

    try:
        result = _run_gh(cmd, timeout=_GH_FORK_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise GhForkFailed(
            f"gh repo fork timed out after {_GH_FORK_TIMEOUT_SECONDS:.0f}s"
        ) from exc
    except OSError as exc:
        raise GhForkFailed(f"failed to spawn gh repo fork: {exc}") from exc

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise GhForkFailed(stderr or f"gh repo fork exited {result.returncode}")

    # ``gh repo fork`` is chatty on stdout but the "where did it land?"
    # signal is always an ``owner/repo`` token. We scan stdout first, then
    # stderr (some gh versions emit the "Created fork" line on stderr),
    # then fall back to ``<into_owner|me>/<repo_name>`` so a future format
    # change cannot kill the endpoint.
    forked_repo: Optional[str] = None
    for stream in (result.stdout or "", result.stderr or ""):
        for line in stream.splitlines():
            match = _GH_FORK_OUTPUT_RE.search(line)
            if not match:
                continue
            candidate = match.group(1)
            # Skip the upstream "<target_repo>" echo so we don't return
            # the source as if it were the fork.
            if candidate == target_repo:
                continue
            forked_repo = candidate
            break
        if forked_repo:
            break

    if forked_repo is None:
        # Last-ditch synthesis: ``<into_owner or "<unknown>">/<repo_name>``.
        # The repo name is the second segment of ``target_repo``; the owner
        # we genuinely don't know without parsing stdout, so we surface the
        # failure to the caller rather than guessing.
        raise GhForkFailed(
            "gh repo fork succeeded but stdout did not contain "
            "a recognisable owner/repo token: "
            f"{(result.stdout or result.stderr or '').strip()!r}"
        )

    fork_url = f"https://github.com/{forked_repo}"
    return {"fork_url": fork_url, "forked_repo": forked_repo}

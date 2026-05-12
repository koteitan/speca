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

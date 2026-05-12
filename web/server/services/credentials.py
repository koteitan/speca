"""Credentials helper for the SPECA web UI.

Login state is owned by the official Claude Code CLI. On Windows the CLI
uses the OS keychain (DPAPI / Credential Manager) rather than a flat
``~/.claude/credentials.json`` file, so the only portable way to detect
"are you logged in?" is to ask the CLI itself via ``claude auth status``.

``set_api_key`` still writes ``apiKey`` into ``~/.claude/credentials.json``
because the CLI documents that file as a fallback for ``ANTHROPIC_API_KEY``;
the existing fields are preserved via merge so the CLI's OAuth session is
never clobbered by a typo in our UI.

All status queries strictly return booleans / display strings — never the
raw key/token.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from ..schemas.auth import AuthStatus

logger = logging.getLogger(__name__)


CREDENTIALS_PATH: Path = Path.home() / ".claude" / "credentials.json"

# Cache `claude auth status` for a short window. Spawning a Node CLI per
# request is ~300ms on Windows; polling at 2s from the SPA would dominate
# the user's idle CPU. We invalidate on `set_api_key`.
_STATUS_CACHE_TTL_SECONDS: float = 1.5
_status_cache: tuple[float, AuthStatus] | None = None


def _load_raw(path: Path = CREDENTIALS_PATH) -> dict[str, Any]:
    """Return the parsed credentials dict, or ``{}`` if the file is absent.

    Corrupt JSON is logged and treated as empty so that the user can recover
    by simply re-entering their API key through the UI instead of having to
    hand-edit the file.
    """

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:  # permissions, etc.
        logger.warning("credentials: read failed (%s) — treating as empty", exc)
        return {}

    if not text.strip():
        return {}

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning(
            "credentials: %s is not valid JSON (%s) — treating as empty",
            path,
            exc,
        )
        return {}

    if not isinstance(data, dict):
        logger.warning(
            "credentials: %s did not contain an object at the top level "
            "(got %s) — treating as empty",
            path,
            type(data).__name__,
        )
        return {}

    return data


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    """Write ``payload`` to ``path`` atomically.

    Uses :func:`tempfile.mkstemp` in the same directory so that
    :func:`os.replace` is a rename within the same filesystem (atomic on both
    POSIX and Windows NTFS). The temp file is ``chmod 0o600`` on POSIX so the
    short window before the rename does not leak the key to other users; on
    Windows we rely on the per-user ``%USERPROFILE%`` ACL and skip the chmod.
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=".credentials.", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())

        if sys.platform != "win32":
            try:
                os.chmod(tmp_path, 0o600)
            except OSError as exc:  # pragma: no cover - best effort
                logger.warning("credentials: chmod 0600 failed (%s)", exc)

        os.replace(tmp_path, path)
    except Exception:
        # On failure leave no half-written tempfile behind.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - best effort
            pass
        raise


def _resolve_claude_cli() -> str | None:
    """Return the absolute path to the ``claude`` CLI, or ``None``."""

    found = shutil.which("claude")
    if found is None and sys.platform == "win32":
        found = shutil.which("claude.cmd")
    return found


def _ask_cli_for_status() -> AuthStatus | None:
    """Run ``claude auth status --json`` and parse the result.

    Returns ``None`` if the CLI is missing or the call failed for any reason
    (we want callers to fall back to the credentials.json probe rather than
    crash the SPA).
    """

    claude_path = _resolve_claude_cli()
    if claude_path is None:
        return None

    try:
        # Node CLI cold-start on Windows is ~300ms; cap at 5s defensively.
        proc = subprocess.run(  # noqa: S603 — path resolved via shutil.which
            [claude_path, "auth", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
            creationflags=(0x08000000 if sys.platform == "win32" else 0),  # CREATE_NO_WINDOW
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("credentials: `claude auth status` failed (%s)", exc)
        return None

    if proc.returncode != 0:
        # CLI returns non-zero when logged out — that's a valid state, not an
        # error. Try to parse stdout anyway; if that fails, fall through.
        logger.debug(
            "credentials: claude auth status rc=%s stderr=%s",
            proc.returncode,
            proc.stderr[:200] if proc.stderr else "",
        )

    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        logger.warning("credentials: claude auth status JSON parse failed (%s)", exc)
        return None

    if not isinstance(payload, dict):
        return None

    logged_in = bool(payload.get("loggedIn"))
    if not logged_in:
        return AuthStatus(logged_in=False, method=None, identity=None)

    auth_method_raw = str(payload.get("authMethod") or "").lower()
    method = "oauth" if "claude.ai" in auth_method_raw else "api_key"
    email = payload.get("email")
    identity = email if isinstance(email, str) and email.strip() else None

    return AuthStatus(logged_in=True, method=method, identity=identity)


def get_status(path: Path = CREDENTIALS_PATH) -> AuthStatus:
    """Return whether the user is logged in and how.

    Primary source of truth is ``claude auth status --json`` because the CLI
    may stash credentials in the OS keychain (Windows DPAPI / macOS Keychain)
    rather than a flat file. We fall back to parsing
    ``~/.claude/credentials.json`` so the UI still works when the CLI is not
    on PATH at all (pure API-key environments).
    """

    global _status_cache
    now = time.monotonic()
    if _status_cache is not None and (now - _status_cache[0]) < _STATUS_CACHE_TTL_SECONDS:
        return _status_cache[1]

    cli_status = _ask_cli_for_status()
    if cli_status is not None:
        _status_cache = (now, cli_status)
        return cli_status

    # Fallback: parse credentials.json directly. Only useful when the CLI
    # isn't installed but the user dropped an api-key into the file.
    data = _load_raw(path)

    api_key = data.get("apiKey")
    if isinstance(api_key, str) and api_key.strip():
        status = AuthStatus(logged_in=True, method="api_key", identity=None)
    else:
        oauth = data.get("claudeAiOauth")
        if isinstance(oauth, dict):
            access_token = oauth.get("accessToken")
            if isinstance(access_token, str) and access_token.strip():
                email = oauth.get("email")
                identity = email if isinstance(email, str) and email.strip() else None
                status = AuthStatus(logged_in=True, method="oauth", identity=identity)
            else:
                status = AuthStatus(logged_in=False, method=None, identity=None)
        else:
            status = AuthStatus(logged_in=False, method=None, identity=None)

    _status_cache = (now, status)
    return status


def invalidate_status_cache() -> None:
    """Force the next :func:`get_status` to re-query the CLI / file."""

    global _status_cache
    _status_cache = None


def set_api_key(key: str, path: Path = CREDENTIALS_PATH) -> None:
    """Persist ``key`` as the ``apiKey`` field while preserving other state.

    Existing ``claudeAiOauth`` (and any other field we don't know about) is
    left untouched. Empty / whitespace-only ``key`` is rejected so we don't
    silently log the user out by writing a blank field.
    """

    if not key or not key.strip():
        raise ValueError("API key must be a non-empty string")

    data = _load_raw(path)
    data["apiKey"] = key
    _atomic_write(path, data)
    invalidate_status_cache()

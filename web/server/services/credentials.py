"""Read/write helper for ``~/.claude/credentials.json``.

The file is shared with the official Claude Code CLI which uses a schema
roughly shaped like::

    {
      "claudeAiOauth": { "accessToken": "...", "email": "...", ... },
      "apiKey": "sk-ant-..."
    }

We MUST preserve any field we do not know about — wiping ``claudeAiOauth``
because the user typed an API key into our UI would log them out of the CLI.
All mutations therefore:

1. Read the existing file (tolerating missing-file / corrupt-JSON cases)
2. Merge the new field into the dict
3. Atomically replace the file via ``tempfile`` + :func:`os.replace`

The status query is the only function that returns to the API layer and it
strictly returns booleans / display strings — never the raw key/token.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from ..schemas.auth import AuthStatus

logger = logging.getLogger(__name__)


CREDENTIALS_PATH: Path = Path.home() / ".claude" / "credentials.json"


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


def get_status(path: Path = CREDENTIALS_PATH) -> AuthStatus:
    """Return whether the user is logged in and how.

    Order of precedence: a non-empty ``apiKey`` wins because the UI's API key
    flow is the explicit/manual path; OAuth is treated as a fallback. This
    matches what the CLI does in practice — if an API key is set it is used.

    The function never raises for "no credentials yet"; it returns
    ``AuthStatus(logged_in=False)`` so the SPA can render the login screen.
    """

    data = _load_raw(path)

    api_key = data.get("apiKey")
    if isinstance(api_key, str) and api_key.strip():
        return AuthStatus(logged_in=True, method="api_key", identity=None)

    oauth = data.get("claudeAiOauth")
    if isinstance(oauth, dict):
        access_token = oauth.get("accessToken")
        if isinstance(access_token, str) and access_token.strip():
            email = oauth.get("email")
            identity = email if isinstance(email, str) and email.strip() else None
            return AuthStatus(logged_in=True, method="oauth", identity=identity)

    return AuthStatus(logged_in=False, method=None, identity=None)


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

"""Auth router for the SPECA web UI.

Endpoints:

* ``GET  /api/auth/status``         — read-only login probe used on boot.
* ``POST /api/auth/api-key``        — persist an API key.
* ``POST /api/auth/login``          — fire-and-forget: spawn the standard
                                      ``claude auth login`` CLI in its own
                                      console so the user can complete the
                                      paste-code OAuth dance externally.
* ``POST /api/auth/oauth/start``    — paste-code OAuth (CLI spec §4.5.1)
                                      backed by an inline subprocess: returns
                                      the auth URL the SPA should open and
                                      a session id for the matching paste.
* ``POST /api/auth/oauth/paste``    — submit the code the user pasted back
                                      from claude.ai; we forward it to the
                                      running CLI subprocess's stdin and
                                      report success once credentials are
                                      written.

The router is intentionally thin: it delegates all credentials I/O to
:mod:`web.server.services.credentials` so unit tests can target that module
without spinning up FastAPI.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..schemas.auth import ApiKeyRequest, AuthStatus
from ..services import credentials as credentials_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Inline paste-code OAuth session store
# ---------------------------------------------------------------------------
#
# CLI spec §4.5.1 explicitly forbids a loopback redirect (Anthropic does not
# allow ``localhost`` callbacks), so the web variant of the flow must use
# paste-code: the SPA gets a URL, the user authorises on claude.ai, the
# resulting auth code is pasted back into a form, and the server completes
# the exchange. We delegate the actual code↔token exchange to the official
# ``claude auth login`` CLI so we do not have to vendor Anthropic's OAuth
# constants (PKCE verifier / token endpoint URLs).
#
# Process model: one subprocess per session, captured with stdin/stdout
# piped so we can extract the URL it prints and forward the pasted code
# back. Sessions are reaped after 10 minutes (matches the CLI's default).

_OAUTH_SESSION_TIMEOUT_SECONDS = 600.0


class _OAuthSession:
    """One in-flight paste-code OAuth attempt."""

    def __init__(self, session_id: str, proc: subprocess.Popen[str]) -> None:
        self.session_id = session_id
        self.proc = proc
        self.created_at = time.monotonic()
        self.auth_url: str | None = None
        self.stdout_buffer: list[str] = []
        self.lock = threading.Lock()
        self.completed = False
        self.error: str | None = None


_oauth_sessions: dict[str, _OAuthSession] = {}
_oauth_sessions_lock = threading.Lock()


_AUTH_URL_RE = re.compile(r"https?://(?:claude\.ai|console\.anthropic\.com)/\S+")


def _reap_oauth_sessions() -> None:
    """Drop sessions that have completed or aged past the timeout."""

    now = time.monotonic()
    with _oauth_sessions_lock:
        dead = [
            sid
            for sid, sess in _oauth_sessions.items()
            if sess.completed
            or sess.proc.poll() is not None
            or (now - sess.created_at) > _OAUTH_SESSION_TIMEOUT_SECONDS
        ]
        for sid in dead:
            sess = _oauth_sessions.pop(sid, None)
            if sess is not None:
                try:
                    if sess.proc.poll() is None:
                        sess.proc.terminate()
                except OSError:  # pragma: no cover - best effort
                    pass


@router.get("/status", response_model=AuthStatus)
def get_status() -> AuthStatus:
    """Report whether the user is logged in. Never returns key material."""

    return credentials_service.get_status()


@router.post("/api-key", response_model=AuthStatus)
def set_api_key(payload: ApiKeyRequest) -> AuthStatus:
    """Persist ``payload.key`` as the Anthropic API key.

    On success returns the freshly-computed :class:`AuthStatus` so the SPA
    can update its cache from a single round trip.
    """

    try:
        credentials_service.set_api_key(payload.key)
    except ValueError as exc:
        # Pydantic validation already enforces ``min_length=1``; this guards
        # the service-layer invariant for callers other than the HTTP layer.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("auth.api_key: failed to persist credentials")
        raise HTTPException(
            status_code=500,
            detail=f"failed to write credentials file: {exc}",
        ) from exc

    return credentials_service.get_status()


@router.post("/login")
def start_oauth_login() -> JSONResponse:
    """Spawn the ``claude auth login`` CLI in a new console for OAuth.

    The official Claude Code CLI handles the OAuth dance with claude.ai and
    writes the resulting tokens to ``~/.claude/credentials.json``. We detach
    the subprocess so the FastAPI request returns immediately; the user
    completes the OAuth flow in their browser, then the SPA's polling on
    ``/api/auth/status`` sees ``logged_in=True, method="oauth"``.
    """

    claude_path = shutil.which("claude") or (
        shutil.which("claude.cmd") if sys.platform == "win32" else None
    )
    if claude_path is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "claude CLI not found on PATH. Install Claude Code "
                "(npm install -g @anthropic-ai/claude-code) then retry."
            ),
        )

    cmd = [claude_path, "auth", "login"]
    creation_flags = 0
    if sys.platform == "win32":
        # CREATE_NEW_CONSOLE = 0x00000010 — pops a visible window so the user
        # sees the OAuth URL the CLI prints. CREATE_NO_WINDOW would hide it
        # but then the user has no way to copy the URL on machines where the
        # auto-launched browser fails (e.g. headless WSL).
        creation_flags = 0x00000010

    try:
        subprocess.Popen(  # noqa: S603 — claude_path resolved via shutil.which
            cmd,
            shell=False,
            stdin=None,
            stdout=None,
            stderr=None,
            creationflags=creation_flags,
            close_fds=True,
        )
    except OSError as exc:
        logger.exception("auth.login: failed to spawn `claude auth login`")
        raise HTTPException(
            status_code=500,
            detail=f"failed to spawn claude CLI: {exc}",
        ) from exc

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "spawned",
            "hint": (
                "A console window has opened (or claude is running in your "
                "terminal). Complete the OAuth flow in the browser that "
                "opens, then return here — the login state will refresh "
                "automatically within a few seconds."
            ),
        },
    )


class OAuthStartResponse(BaseModel):
    """Body returned by ``POST /api/auth/oauth/start``."""

    session_id: str = Field(..., description="Echo back to /oauth/paste.")
    auth_url: str | None = Field(
        default=None,
        description=(
            "URL the user should open in their browser. ``null`` when the "
            "CLI did not print one within the start window — the SPA "
            "should fall back to instructing the user to read the CLI's "
            "stdout buffer (also available via the same endpoint).",
        ),
    )
    stdout_tail: str = Field(
        default="",
        description="Last ~1 KB of the CLI's stdout, surfaced for debugging.",
    )


class OAuthPasteRequest(BaseModel):
    session_id: str
    code: str = Field(..., min_length=1)


class OAuthPasteResponse(BaseModel):
    session_id: str
    completed: bool
    error: str | None = None


@router.post("/oauth/start", response_model=OAuthStartResponse)
def oauth_start() -> OAuthStartResponse:
    """Spawn ``claude auth login`` with pipes so the SPA can drive paste-code.

    The CLI prints the auth URL to stdout within ~1 s; we tail its stdout
    on a background thread and surface the captured URL to the caller.
    """

    _reap_oauth_sessions()

    claude_path = shutil.which("claude") or (
        shutil.which("claude.cmd") if sys.platform == "win32" else None
    )
    if claude_path is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "claude_cli_not_found",
                "message": (
                    "claude CLI not found on PATH. Install Claude Code "
                    "(npm install -g @anthropic-ai/claude-code) then retry."
                ),
            },
        )

    creation_flags = 0
    if sys.platform == "win32":
        # CREATE_NO_WINDOW so the CLI does not pop a visible console; the
        # SPA owns the UI now.
        creation_flags = 0x08000000

    try:
        proc = subprocess.Popen(  # noqa: S603 — claude_path resolved via which
            [claude_path, "auth", "login", "--claudeai"],
            shell=False,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=creation_flags,
            close_fds=True,
        )
    except OSError as exc:
        logger.exception("auth.oauth.start: spawn failed")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "spawn_failed",
                "message": f"failed to spawn claude CLI: {exc}",
            },
        ) from exc

    session_id = str(uuid.uuid4())
    sess = _OAuthSession(session_id=session_id, proc=proc)
    with _oauth_sessions_lock:
        _oauth_sessions[session_id] = sess

    def _tail_stdout() -> None:
        """Background reader — captures the auth URL from CLI stdout."""

        try:
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                line = raw_line.rstrip("\r\n")
                with sess.lock:
                    sess.stdout_buffer.append(line)
                    # Keep the tail bounded so a chatty CLI does not eat
                    # memory if the user wanders off mid-auth.
                    if len(sess.stdout_buffer) > 200:
                        sess.stdout_buffer = sess.stdout_buffer[-200:]
                    if sess.auth_url is None:
                        match = _AUTH_URL_RE.search(line)
                        if match:
                            sess.auth_url = match.group(0)
        except Exception as exc:  # pragma: no cover - background safety
            logger.warning("auth.oauth: stdout pump for %s died: %s", session_id, exc)

    threading.Thread(target=_tail_stdout, daemon=True).start()

    # Give the CLI ~2 s to print the URL (cold-start on Windows is slow).
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        with sess.lock:
            if sess.auth_url is not None:
                break
        time.sleep(0.05)

    with sess.lock:
        tail = "\n".join(sess.stdout_buffer[-40:])
        return OAuthStartResponse(
            session_id=session_id,
            auth_url=sess.auth_url,
            stdout_tail=tail,
        )


@router.post("/oauth/paste", response_model=OAuthPasteResponse)
def oauth_paste(body: OAuthPasteRequest) -> OAuthPasteResponse:
    """Forward the pasted code to the matching ``claude auth login`` subprocess.

    After writing to stdin we wait up to 30 s for the subprocess to exit
    (the CLI exchanges the code for tokens and writes credentials.json
    before returning). On exit, we invalidate the cached auth status so
    the next ``GET /api/auth/status`` reflects the new login.
    """

    with _oauth_sessions_lock:
        sess = _oauth_sessions.get(body.session_id)
    if sess is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "oauth_session_not_found", "session_id": body.session_id},
        )
    if sess.completed:
        return OAuthPasteResponse(
            session_id=sess.session_id, completed=True, error=sess.error
        )
    if sess.proc.poll() is not None:
        sess.completed = True
        sess.error = "claude CLI exited before code was pasted"
        return OAuthPasteResponse(
            session_id=sess.session_id, completed=True, error=sess.error
        )

    try:
        assert sess.proc.stdin is not None
        sess.proc.stdin.write(body.code.strip() + "\n")
        sess.proc.stdin.flush()
    except OSError as exc:
        sess.completed = True
        sess.error = f"failed to forward code: {exc}"
        return OAuthPasteResponse(
            session_id=sess.session_id, completed=True, error=sess.error
        )

    try:
        rc = sess.proc.wait(timeout=30.0)
    except subprocess.TimeoutExpired:
        sess.error = "claude CLI did not finish exchange within 30s"
        return OAuthPasteResponse(
            session_id=sess.session_id, completed=False, error=sess.error
        )

    sess.completed = True
    if rc != 0:
        # Drain remaining stdout for the error tail.
        with sess.lock:
            tail = "\n".join(sess.stdout_buffer[-20:])
        sess.error = (
            f"claude CLI exited with code {rc}. Tail:\n{tail}"
            if tail
            else f"claude CLI exited with code {rc}"
        )
    credentials_service.invalidate_status_cache()
    return OAuthPasteResponse(
        session_id=sess.session_id, completed=True, error=sess.error
    )

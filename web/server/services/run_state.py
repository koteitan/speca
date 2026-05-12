"""Atomic on-disk persistence for run state.json + orphan reconciliation.

The supervisor (``run_supervisor.py``) holds the authoritative in-memory
view of every active run; this module is the boring file-system layer
that survives across restarts so:

1. UI clients can render a useful page even if the backend just rebooted
2. We can detect runs whose owning supervisor crashed (``orphaned_running``)
   versus runs whose supervisor exited cleanly (``cancelled`` / ``ok``)

Design invariants:

* Writes are **atomic** — we create a tempfile in the same directory and
  ``os.replace`` it over the target, so a crash mid-write cannot leave a
  half-written ``state.json``.
* Reads are **tolerant** — any I/O or JSON-decoding error returns ``None``
  rather than raising, mirroring :mod:`web.server.services.run_index`.
* Reconciliation is **side-effect-only-on-orphan** — runs that are
  ``ok``/``failed``/``cancelled`` are left untouched, only ``running``
  rows whose ``owner_pid`` is dead get rewritten.
"""

from __future__ import annotations

import errno
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from web.server.config import SPECA_RUNS_DIR
from web.server.schemas.run_state import RunStateDoc

if TYPE_CHECKING:  # pragma: no cover - import cycle break
    from web.server.services.run_supervisor import RunSupervisor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _run_dir(run_id: str, runs_dir: Path | None = None) -> Path:
    """Resolve ``<runs_dir>/<run_id>/`` without creating the directory."""

    return (runs_dir or SPECA_RUNS_DIR) / run_id


def state_path_for(run_id: str, runs_dir: Path | None = None) -> Path:
    """Public helper so callers don't need to know the file name."""

    return _run_dir(run_id, runs_dir) / "state.json"


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def load_state(run_id: str, runs_dir: Path | None = None) -> RunStateDoc | None:
    """Read and validate ``state.json``, returning ``None`` on any error.

    The error modes we tolerate (and translate to ``None``):

    * file does not exist
    * file is unreadable (permission denied, etc.)
    * file is not valid JSON (e.g. an interrupted write — though the
      atomic-replace strategy should make this near-impossible)
    * payload fails Pydantic validation (schema drift)
    """

    sp = state_path_for(run_id, runs_dir)
    try:
        raw = sp.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("speca: unable to read %s: %s", sp, exc)
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("speca: malformed state.json at %s: %s", sp, exc)
        return None

    try:
        return RunStateDoc.model_validate(data)
    except ValidationError as exc:
        logger.warning("speca: state.json failed validation at %s: %s", sp, exc)
        return None


# ---------------------------------------------------------------------------
# Write — atomic via tempfile + os.replace
# ---------------------------------------------------------------------------


def _serialise(doc: RunStateDoc) -> str:
    """JSON-encode ``doc`` with stable ordering for byte-level diffability."""

    return doc.model_dump_json(indent=2)


def write_state(
    run_id: str,
    doc: RunStateDoc,
    runs_dir: Path | None = None,
) -> Path:
    """Atomically persist ``doc`` to ``<runs_dir>/<run_id>/state.json``.

    Implementation note: ``tempfile.NamedTemporaryFile(delete=False)`` +
    ``os.replace`` is the only portable atomic-write recipe — ``os.rename``
    fails across filesystems on Windows, but we always write into the same
    directory as the target, so ``os.replace`` is guaranteed to be atomic
    on every platform we support (POSIX + Win32).

    Returns the final path so callers can log it.
    """

    sp = state_path_for(run_id, runs_dir)
    sp.parent.mkdir(parents=True, exist_ok=True)

    payload = _serialise(doc)

    # ``dir=sp.parent`` so the tempfile lives next to the target — keeps
    # ``os.replace`` on the same filesystem (mandatory for atomicity).
    fd, tmp_name = tempfile.mkstemp(
        prefix=".state.",
        suffix=".json.tmp",
        dir=str(sp.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # ``fsync`` is not required for atomicity (``os.replace`` is
                # the atomic step); we still try it for durability but a
                # filesystem that rejects fsync (e.g. some test FUSEs) is
                # not a fatal failure.
                pass
        _atomic_replace(tmp_path, sp)
    except Exception:
        # Best-effort cleanup of the orphan tempfile; the ``replace`` above
        # would have eaten it on success.
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise

    return sp


def _atomic_replace(src: Path, dst: Path) -> None:
    """``os.replace`` with a small retry loop for Windows.

    ``os.replace`` is documented as atomic on every platform, but on
    Windows a concurrent writer (or the file being momentarily held open
    by Windows Search / Defender) can trigger ``ERROR_ACCESS_DENIED``
    (errno 13, WinError 5). The standard mitigation — used by git,
    poetry, uv, and ``filelock`` — is a short exponential-backoff retry
    on those specific error codes. On POSIX the loop exits on the first
    try.
    """

    attempts = 8 if sys.platform == "win32" else 1
    delay = 0.005  # 5ms initial backoff, doubled each try -> ~640ms max
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError as exc:  # WinError 5 manifests as PermissionError
            last_exc = exc
        except OSError as exc:
            # WinError 32 (sharing violation) shows up as OSError on
            # older Pythons; retry that too.
            if sys.platform == "win32" and getattr(exc, "winerror", None) in {5, 32}:
                last_exc = exc
            else:
                raise
        time.sleep(delay)
        delay = min(delay * 2, 0.5)
    assert last_exc is not None  # for type checkers
    raise last_exc


# ---------------------------------------------------------------------------
# Orphan reconciliation
# ---------------------------------------------------------------------------


def _process_is_alive(pid: int) -> bool:
    """Return whether ``pid`` corresponds to a process this OS can see.

    Cross-platform notes:

    * POSIX: ``os.kill(pid, 0)`` is the standard recipe. ``ProcessLookup
      Error`` means dead; ``PermissionError`` means alive-but-foreign.
    * Windows: ``os.kill(pid, 0)`` is **not** usable — signal 0 is not
      supported and the API returns ``ERROR_INVALID_PARAMETER`` for
      every PID, regardless of whether it is live. We fall back to
      ``OpenProcess`` + ``GetExitCodeProcess`` via ctypes (no extra deps).
    """

    if pid <= 0:
        return False

    if sys.platform == "win32":
        return _process_is_alive_win32(pid)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Alive but owned by another user — still counts as "running" so
        # we do not falsely orphan it.
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        logger.warning("speca: os.kill(%s, 0) raised %s", pid, exc)
        return True
    return True


def _process_is_alive_win32(pid: int) -> bool:
    """Windows liveness probe — ``OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)``.

    Cases:

    * Handle opens, exit code == STILL_ACTIVE (259) -> alive.
    * Handle opens, exit code != STILL_ACTIVE -> the process exited but
      the kernel kept the record around briefly; treat as dead.
    * OpenProcess fails with ERROR_ACCESS_DENIED -> process exists but
      we can't query it (different session/integrity level); treat as
      alive — we'd rather over-conservatively keep "running" than
      reclaim a foreign supervisor's run.
    * Otherwise (ERROR_INVALID_PARAMETER, etc.) -> dead.
    """

    import ctypes  # local import keeps non-Windows hot path lean
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    ERROR_ACCESS_DENIED = 5

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        err = ctypes.get_last_error()
        if err == ERROR_ACCESS_DENIED:
            return True
        return False
    try:
        code = wintypes.DWORD()
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        if not ok:
            # Can't read exit code — conservative default.
            return True
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def reconcile_orphans(
    supervisor: "RunSupervisor | None" = None,
    runs_dir: Path | None = None,
) -> list[str]:
    """Rewrite ``running`` state.json files whose ``owner_pid`` is dead.

    Algorithm:

    1. Walk ``<runs_dir>/*/state.json``.
    2. For each row whose ``status`` is ``"running"``:

       * if ``owner_pid`` equals the current process id, do nothing — the
         freshly-launched supervisor is the legitimate owner.
       * if the PID is dead, rewrite the file as ``"crashed"`` and tag
         every still-``running`` phase row as ``"failed"`` (with reason
         ``"supervisor crashed"``).
       * if the PID is alive but is not us, mark the row as
         ``"orphaned_running"`` — another supervisor instance owns it
         and the user should be told to kill that one before re-running.

    The ``supervisor`` argument is accepted for symmetry with the call
    site in ``main.py``; the function currently does not need it but
    threading it through keeps the signature stable for future use
    (e.g. forwarding "reconciled run_ids" into the in-memory map).

    Returns the list of run_ids that were rewritten — handy for logging.
    """

    target_dir = runs_dir or SPECA_RUNS_DIR
    if not target_dir.is_dir():
        return []

    my_pid = os.getpid()
    reconciled: list[str] = []
    for run_dir in target_dir.iterdir():
        if not run_dir.is_dir():
            continue
        run_id = run_dir.name
        doc = load_state(run_id, runs_dir=target_dir)
        if doc is None:
            continue
        if doc.status != "running":
            continue

        if doc.owner_pid == my_pid:
            # We are the owner — supervisor is just restarting itself,
            # nothing to reconcile.
            continue

        alive = _process_is_alive(doc.owner_pid)
        if alive:
            new_status = "orphaned_running"
            reason = "another supervisor instance owns this run"
        else:
            new_status = "crashed"
            reason = "supervisor crashed"

        updated_phases = []
        now = datetime.now(timezone.utc)
        for phase in doc.phases:
            if phase.status == "running":
                phase = phase.model_copy(
                    update={
                        "status": "failed",
                        "ended_at": now,
                        "reason": reason,
                    }
                )
            updated_phases.append(phase)

        doc = doc.model_copy(
            update={
                "status": new_status,
                "phases": updated_phases,
                "cancel_requested": False,
            }
        )
        try:
            write_state(run_id, doc, runs_dir=target_dir)
            reconciled.append(run_id)
            logger.info(
                "speca: reconciled run %s -> %s (owner_pid=%s, alive=%s)",
                run_id,
                new_status,
                doc.owner_pid,
                alive,
            )
        except OSError as exc:
            logger.warning(
                "speca: failed to reconcile %s: %s", run_id, exc
            )

    return reconciled


# ---------------------------------------------------------------------------
# Convenience: hydrate from disk into an in-memory doc, with sensible default
# ---------------------------------------------------------------------------


def load_or_init(
    run_id: str,
    *,
    runs_dir: Path | None = None,
    initial: dict[str, Any] | None = None,
) -> RunStateDoc:
    """Load existing state.json, or return a fresh :class:`RunStateDoc`.

    Used by the supervisor when starting a new run — we never want to
    silently *overwrite* an existing state file (e.g. on a re-run with
    the same id), but we also do not want to crash if the file is
    missing. ``initial`` is a dict that is merged with the defaults to
    seed a fresh doc.
    """

    existing = load_state(run_id, runs_dir=runs_dir)
    if existing is not None:
        return existing
    payload = {"run_id": run_id, **(initial or {})}
    return RunStateDoc.model_validate(payload)

"""WebSocket router for live run streaming (Slice B2).

Endpoint: ``/api/ws/runs/{run_id}/stream``

Contract (mirrors the slice spec):

1. On connection accept, send a ``state_snapshot`` event immediately so the
   SPA can render the current phase grid without waiting for the next
   queue tick.
2. If the supervisor has no live record for ``run_id`` we fall back to the
   on-disk ``state.json`` (run already finished, or backend restarted
   since). In that case we send one ``state_snapshot`` followed by
   ``run_terminated`` and close with code ``1000``.
3. Otherwise we forward every event yielded by
   :meth:`RunSupervisor.subscribe` 1:1 over the socket until we receive a
   ``run_terminated`` event from the supervisor, then close with ``1000``.
4. While the chain is running we emit a ``ping`` event every 20s on a
   background task so intermediaries / proxies don't terminate an idle
   socket. Cancelled cleanly when the main forwarder exits.

Close codes:

* ``1000`` — normal closure (chain finished, peer disconnect, etc.)
* ``1011`` — unexpected server error; ``reason`` is truncated to 100 chars
  per RFC 6455. We always wrap the close in ``try/except`` because the
  socket may already be torn down by the time we get there.

The router is registered under the same ``/api`` prefix as the rest of
the v1 backend (``app.include_router(runs_ws.router, prefix="/api")``);
this keeps the URL surface aligned with the REST routes and lets a
reverse proxy gate every backend route with a single rule.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.run_state import load_state
from ..services.run_supervisor import get_run_supervisor

logger = logging.getLogger(__name__)


router = APIRouter()


# ---------------------------------------------------------------------------
# Tunables (module-level so tests can monkeypatch without touching the route)
# ---------------------------------------------------------------------------

#: Interval between ``ping`` heartbeats while a run is being streamed.
#: Tests override this to ~0.1s to assert the keepalive fires.
KEEPALIVE_INTERVAL_SECONDS: float = 20.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Return an RFC3339-ish UTC timestamp with a trailing ``Z``.

    Pulled out as a function so tests can monkeypatch the clock without
    touching :mod:`datetime` globally.
    """

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def _keepalive(ws: WebSocket) -> None:
    """Background loop that emits a ``ping`` JSON frame on an interval.

    The loop swallows every exception other than ``asyncio.CancelledError``
    — the only meaningful failure is "socket already gone", in which case
    the main coroutine is also exiting and will close it.
    """

    try:
        while True:
            await asyncio.sleep(KEEPALIVE_INTERVAL_SECONDS)
            try:
                await ws.send_json({"type": "ping", "ts": _utc_now_iso()})
            except Exception:
                # Socket is closed / mid-close — bail; the main task will
                # finalise the close handshake.
                return
    except asyncio.CancelledError:
        return


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.websocket("/ws/runs/{run_id}/stream")
async def stream_run(websocket: WebSocket, run_id: str) -> None:
    """Stream events for ``run_id`` until the chain terminates.

    See the module docstring for the full contract — this function is the
    one wire path the SPA's ``useRunStream`` hook hits, so it deliberately
    contains the entire dispatch logic in-line rather than splitting into
    helpers that obscure the close-code accounting.
    """

    await websocket.accept()

    keepalive_task: asyncio.Task[None] | None = None
    try:
        supervisor = get_run_supervisor()
        live = supervisor.get_live_status(run_id)

        # ---- Run is already terminal (or unknown) ---------------------
        # In both cases we send a single ``state_snapshot`` (with ``data``
        # = the on-disk state, or ``None`` when nothing is on disk) plus
        # the ``run_terminated`` bookend so the SPA can render its final
        # view without waiting for the supervisor to broadcast.
        if live is None:
            doc = load_state(run_id)
            if doc is None:
                snapshot = {
                    "type": "state_snapshot",
                    "data": None,
                    "reason": "unknown_run_id",
                }
            else:
                snapshot = {
                    "type": "state_snapshot",
                    "data": doc.model_dump(mode="json"),
                }
            await websocket.send_json(snapshot)
            await websocket.send_json(
                {"type": "run_terminated", "reason": "already_finished"}
            )
            await websocket.close(code=1000)
            return

        # ---- Run is live: snapshot + forward subscribe() --------------
        await websocket.send_json(
            {"type": "state_snapshot", "data": live.model_dump(mode="json")}
        )

        keepalive_task = asyncio.create_task(
            _keepalive(websocket), name=f"speca-ws-keepalive-{run_id}"
        )

        # The supervisor's ``subscribe`` is an ``AsyncIterator`` — when
        # we break out of the ``async for`` it triggers the generator's
        # ``finally`` clause which removes our queue from the subscriber
        # list, so there is no resource leak on early exit.
        async for event in supervisor.subscribe(run_id):
            await websocket.send_json(event)
            if event.get("type") == "run_terminated":
                break

        await websocket.close(code=1000)

    except WebSocketDisconnect:
        # Peer closed the socket. The supervisor's subscribe generator
        # will be GC'd shortly after we return, unsubscribing the queue
        # via its ``finally`` block. Nothing else to do.
        logger.debug("speca: WS client disconnected for %s", run_id)
    except Exception as exc:  # noqa: BLE001 - we genuinely want any error here
        logger.exception("speca: WS stream for %s aborted", run_id)
        # RFC 6455 caps close reason at 123 bytes; we truncate further to
        # 100 chars to stay clear of multibyte boundary issues.
        reason = str(exc)[:100]
        try:
            await websocket.close(code=1011, reason=reason)
        except Exception:
            # Already closed or in a bad state — nothing we can do.
            pass
    finally:
        if keepalive_task is not None:
            keepalive_task.cancel()
            try:
                await keepalive_task
            except (asyncio.CancelledError, Exception):
                pass


__all__ = ["router", "stream_run", "KEEPALIVE_INTERVAL_SECONDS"]

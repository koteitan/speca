"""In-memory approval gate for side-effect chat tools (Slice C1 + C2).

The chat surface lets the model propose side-effecting actions
(``launch_pipeline`` / ``stop_pipeline``) — but before the runtime is
allowed to *execute* one, the user has to approve it from the SPA via
``POST /api/chat/tool_approve``.

Flow per pending approval:

1. ``chat_runtime`` detects a ``tool_use`` block whose name is in
   :data:`chat_tools.SIDE_EFFECT_TOOLS`.
2. It calls :func:`register_pending` to mint a :class:`PendingApproval`
   keyed by ``(conversation_id, tool_call_id)`` and emits a
   ``tool_approval_required`` SSE event.
3. The runtime then ``await``\\s ``approval.event`` (with a 10-minute
   timeout — see :data:`APPROVAL_TIMEOUT_SECONDS` upstream).
4. The frontend posts to ``/chat/tool_approve`` with ``action="approve" |
   "edit" | "cancel"``; the router calls :func:`resolve` which sets the
   ``asyncio.Event`` and the runtime resumes.

Threading / lifetime caveats
----------------------------

* :data:`_pending` is a process-local in-memory dict. v1 targets
  localhost single-user, so we do not need persistence — if uvicorn
  restarts mid-approval, the pending approval is dropped and the user
  resubmits.
* **TODO (v2):** add session-binding so an arbitrary caller cannot resolve
  someone else's pending tool_call_id. v1 is localhost-only + single user
  by design so the bare ``(conversation_id, tool_call_id)`` key suffices.
* The asyncio.Event lives in the same event loop that registered it
  (uvicorn's main loop) — :func:`resolve` is sync because it does not need
  to await anything; it only ``set()``s the event which is safe across
  loop boundaries.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)


ApprovalAction = Literal["approve", "edit", "cancel"]


@dataclass
class PendingApproval:
    """One in-flight approval awaiting a user decision.

    ``input_snapshot`` is the model-proposed input as it appeared at
    ``tool_use`` time — useful for the UI preview and as a fallback when
    the user "approves" without editing.

    ``edited_input`` is populated only on ``action == "edit"``. The
    runtime trusts whatever the user sends back; v1 does not diff against
    the snapshot (the whole point of edit is to override the model).
    """

    conversation_id: str
    tool_call_id: str
    tool_name: str
    input_snapshot: dict
    event: asyncio.Event = field(default_factory=asyncio.Event)
    action: ApprovalAction | None = None
    edited_input: dict | None = None


# Module-level registry. Key is ``(conversation_id, tool_call_id)`` — both
# pieces are needed because tool_call_ids from Anthropic are only unique
# within one message; pairing with conversation_id keeps two concurrent
# chats from clobbering each other.
_pending: dict[tuple[str, tuple[str, str]], PendingApproval] = {}


def _key(conversation_id: str, tool_call_id: str) -> tuple[str, tuple[str, str]]:
    # The nested tuple shape (rather than a flat 2-tuple) is just so
    # mypy / readers see "this is a composite key, not coincidence".
    return ("approval", (conversation_id, tool_call_id))


def register_pending(
    *,
    conversation_id: str,
    tool_call_id: str,
    tool_name: str,
    input_snapshot: dict,
) -> PendingApproval:
    """Record a new pending approval and return it.

    The caller (chat_runtime) is expected to ``await
    pending.event.wait()`` after emitting the ``tool_approval_required``
    event to the SSE stream.

    Re-registering the same ``(conversation_id, tool_call_id)`` is an
    error in v1: tool_call_ids are minted by Anthropic and never reused
    within a turn, so a collision means the runtime is calling us twice.
    We log and overwrite (rather than raise) so a buggy retry path can
    still make progress.
    """

    key = _key(conversation_id, tool_call_id)
    if key in _pending:
        logger.warning(
            "chat_approvals: overwriting existing pending approval for %s/%s",
            conversation_id,
            tool_call_id,
        )
    approval = PendingApproval(
        conversation_id=conversation_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        input_snapshot=dict(input_snapshot),
    )
    _pending[key] = approval
    return approval


def get_pending(conversation_id: str, tool_call_id: str) -> PendingApproval | None:
    """Look up a pending approval without consuming it."""

    return _pending.get(_key(conversation_id, tool_call_id))


def resolve(
    *,
    conversation_id: str,
    tool_call_id: str,
    action: ApprovalAction,
    edited_input: dict | None = None,
) -> bool:
    """Resolve a pending approval. Returns ``True`` iff one was found.

    Setting ``action`` to ``"edit"`` requires ``edited_input`` — the
    caller (router) is responsible for that contract; we accept ``None``
    here and let the runtime fall back to the snapshot (so a buggy client
    that posts ``edit`` without a body still gets a sensible behaviour).

    After resolving, we pop the entry from :data:`_pending` so memory
    does not leak even if the chat_runtime never woke up (e.g. the SSE
    stream was disconnected). The runtime's own timeout path drops the
    entry too — :func:`drop` is the no-op for already-resolved cases.
    """

    key = _key(conversation_id, tool_call_id)
    approval = _pending.get(key)
    if approval is None:
        return False
    approval.action = action
    approval.edited_input = dict(edited_input) if edited_input is not None else None
    approval.event.set()
    # Pop only on resolve — keep around if approval.event is awaited
    # elsewhere. The runtime drops it via :func:`drop` after consuming.
    _pending.pop(key, None)
    return True


def drop(conversation_id: str, tool_call_id: str) -> None:
    """Forget a pending approval. Safe to call when nothing is pending."""

    _pending.pop(_key(conversation_id, tool_call_id), None)


def _reset_for_tests() -> None:
    """Test-only helper: clear the in-memory registry between cases."""

    _pending.clear()


__all__ = [
    "ApprovalAction",
    "PendingApproval",
    "drop",
    "get_pending",
    "register_pending",
    "resolve",
]

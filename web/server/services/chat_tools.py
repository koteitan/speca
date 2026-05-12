"""Tool dispatch for the Chat slice — allowlist + approval-gated side effects.

This module declares the Anthropic tools the chat surface is allowed to
call. The allowlist now spans **two tiers**:

* **Read-only** (auto-dispatched, no UI prompt): ``read_run_status``,
  ``list_findings``, ``read_finding``, ``fetch_bounty_url``.
* **Side-effecting** (gated by an explicit user approval):
  ``launch_pipeline``, ``stop_pipeline``.

Defense in depth — see ``docs/UI_DESIGN.md`` § 4.8 and the slice C1 + C2 spec:

1. ``TOOLS`` is the literal list passed to Anthropic's ``messages.stream``
   — the model sees only what we have explicitly declared.
2. :func:`dispatch_tool` re-checks ``name`` against
   :data:`ALLOWED_TOOL_NAMES` and refuses anything outside it
   (:class:`ToolNotAllowed`). Side-effecting tools additionally raise if
   they reach :func:`dispatch_tool` — the runtime must route them through
   :func:`dispatch_side_effect_tool` *after* an approval succeeded.
3. The frontend ``<ToolCard>`` renders an approval panel for
   side-effecting tools and refuses to auto-confirm them.

Service modules (Slice B / C / H) are imported lazily inside each handler
— if a slice has not landed yet, we return ``{"error":
"service_not_ready", ...}`` instead of raising, so the rest of the
conversation flow keeps working.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# --- Tool specs ---------------------------------------------------------------

# Each tool follows Anthropic's ``Tool`` shape (``name`` + ``description`` +
# ``input_schema``). The schemas are intentionally narrow: required fields are
# explicit, and we use ``enum`` for closed sets so the model gets a clean
# error message if it hallucinates a value.
TOOLS: list[dict[str, Any]] = [
    {
        "name": "read_run_status",
        "description": (
            "Get current state of a SPECA audit run (phase progress, "
            "cost, status)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "list_findings",
        "description": (
            "List Phase 03/04 findings for a run with optional filters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "phase": {"type": "string", "enum": ["03", "04"]},
                "severity": {"type": "string"},
                "verdict": {"type": "string"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "read_finding",
        "description": "Get full detail of a single finding by property_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "property_id": {"type": "string"},
            },
            "required": ["run_id", "property_id"],
        },
    },
]


# --- Slice C1 + C2 additions ------------------------------------------------
#
# Read-only ``fetch_bounty_url`` is appended to the same flat ``TOOLS`` list
# so the model sees a single, consistent allowlist. Side-effect tools are
# appended too — they are *also* in the allowlist passed to Anthropic
# (otherwise the model could never propose them) but the runtime intercepts
# their execution and routes through the approval gate.

TOOLS.append(
    {
        "name": "fetch_bounty_url",
        "description": (
            "Fetch and parse a bug bounty program URL to extract scope, "
            "spec URLs, and keywords. Use this when the user wants to start "
            "a new audit from a bug bounty page."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bug_bounty_url": {"type": "string", "format": "uri"},
                "contract_addresses": {
                    "type": "string",
                    "description": "Optional comma-separated contract addresses",
                },
            },
            "required": ["bug_bounty_url"],
        },
    }
)
TOOLS.append(
    {
        "name": "launch_pipeline",
        "description": (
            "Start a new SPECA audit run. REQUIRES USER APPROVAL via "
            "tool_approval_required event — never execute directly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bug_bounty_url": {"type": "string", "format": "uri"},
                "target_repo": {
                    "type": "string",
                    "pattern": "^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$",
                },
                "target_ref": {"type": "string"},
                "contract_addresses": {"type": "string"},
                "spec_urls": {"type": "string"},
                "keywords": {"type": "string"},
                "workers": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 32,
                    "default": 4,
                },
                "max_concurrent": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 256,
                    "default": 64,
                },
                "push_to_remote": {"type": "boolean", "default": False},
            },
            "required": ["bug_bounty_url", "target_repo"],
        },
    }
)
TOOLS.append(
    {
        "name": "stop_pipeline",
        "description": "Cancel a running SPECA audit run. REQUIRES USER APPROVAL.",
        "input_schema": {
            "type": "object",
            "properties": {"run_id": {"type": "string"}},
            "required": ["run_id"],
        },
    }
)


# The allowlist is recomputed from ``TOOLS`` so additions above are picked
# up automatically. ``SIDE_EFFECT_TOOLS`` is a separate subset the runtime
# uses to decide which tool_uses need to go through the approval gate.
ALLOWED_TOOL_NAMES: frozenset[str] = frozenset(t["name"] for t in TOOLS)
SIDE_EFFECT_TOOLS: frozenset[str] = frozenset({"launch_pipeline", "stop_pipeline"})


class ToolNotAllowed(Exception):
    """Raised when the model emits a tool name outside :data:`ALLOWED_TOOL_NAMES`.

    The runtime translates this into an ``error`` SSE event with
    ``reason=tool_not_allowed`` and aborts the stream — the offending
    tool_use is *not* persisted to history.
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"tool not allowed: {name}")
        self.name = name


def _service_not_ready(name: str, reason: str = "service_not_ready") -> dict:
    """Uniform error payload when a Slice B/C service is missing.

    We pick a stable shape so the frontend can render a friendly "this part
    of SPECA isn't wired up yet" card without sniffing exception types.
    """

    return {"error": reason, "tool": name}


async def dispatch_tool(name: str, input: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a *read-only* tool call to the matching service.

    Raises :class:`ToolNotAllowed` if ``name`` is not in
    :data:`ALLOWED_TOOL_NAMES`. Side-effecting tools are in the allowlist
    but **must** be routed through :func:`dispatch_side_effect_tool`
    instead — calling this function with a side-effect name raises
    ``RuntimeError`` so a refactor that forgets the approval gate fails
    loudly rather than silently bypassing it (defense layer 2 of 3).

    Returns a dict that is either the service result or a ``{"error":
    ...}`` envelope — never ``None``.
    """

    if name not in ALLOWED_TOOL_NAMES:
        raise ToolNotAllowed(name)

    if name in SIDE_EFFECT_TOOLS:
        # The runtime must have intercepted this name before dispatch.
        # Refuse loudly so a future caller cannot bypass the approval
        # flow by accident.
        raise RuntimeError(
            f"{name} must be dispatched via dispatch_side_effect_tool "
            "after approval, not via dispatch_tool"
        )

    if name == "read_run_status":
        return await _read_run_status(input)
    if name == "list_findings":
        return await _list_findings(input)
    if name == "read_finding":
        return await _read_finding(input)
    if name == "fetch_bounty_url":
        return await _fetch_bounty_url(input)

    # Should never happen because of the allowlist check above, but kept as
    # a hard fallback in case ALLOWED_TOOL_NAMES drifts from the if-chain.
    raise ToolNotAllowed(name)  # pragma: no cover


async def dispatch_side_effect_tool(
    name: str, input: dict[str, Any]
) -> dict[str, Any]:
    """Execute a side-effect tool. Caller MUST have already approved it.

    This function is the only path that mutates SPECA state from the chat
    surface. The runtime (`chat_runtime.stream_response`) is responsible
    for:

    1. Confirming the tool name is in :data:`SIDE_EFFECT_TOOLS`.
    2. Calling :func:`web.server.services.chat_approvals.register_pending`,
       emitting a ``tool_approval_required`` event, and ``await``\\ing
       the user's response.
    3. Calling **this** function only when ``action="approve"`` or
       ``action="edit"`` came back.

    Imports of heavy service modules are deferred to call-time so that
    importing ``chat_tools`` (which the read-only test suite does) stays
    free of supervisor / workspace dependencies.
    """

    if name not in SIDE_EFFECT_TOOLS:
        raise ToolNotAllowed(name)

    if name == "launch_pipeline":
        return await _launch_pipeline(input)
    if name == "stop_pipeline":
        return await _stop_pipeline(input)
    # Unreachable while SIDE_EFFECT_TOOLS / branches stay in sync.
    raise ValueError(f"unknown side-effect tool: {name}")  # pragma: no cover


# --- Handlers ---------------------------------------------------------------
#
# Each handler imports its dependencies *inside* the function so that the
# slice can land even when Slice B/C is still in flight. Try-imports keep
# the chat surface usable while service modules are missing.


async def _read_run_status(input: dict[str, Any]) -> dict[str, Any]:
    run_id = input.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return {"error": "invalid_input", "tool": "read_run_status"}

    try:
        from web.server.services.run_index import get_run_detail  # type: ignore
    except ImportError as exc:
        logger.info("chat_tools: run_index not ready (%s)", exc)
        return _service_not_ready("read_run_status")

    try:
        detail = get_run_detail(run_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("chat_tools: read_run_status failed (%s)", exc)
        return {"error": "internal_error", "tool": "read_run_status"}

    if detail is None:
        return {"error": "not_found", "tool": "read_run_status", "run_id": run_id}
    # Pydantic v2: ``mode="json"`` yields ISO datetimes etc., which is what
    # we want when shipping the result back to the model as a JSON blob.
    return detail.model_dump(mode="json") if hasattr(detail, "model_dump") else dict(detail)


async def _list_findings(input: dict[str, Any]) -> dict[str, Any]:
    run_id = input.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return {"error": "invalid_input", "tool": "list_findings"}

    try:
        from web.server.services.finding_loader import list_findings as svc_list  # type: ignore
    except ImportError as exc:
        logger.info("chat_tools: finding_loader not ready (%s)", exc)
        return _service_not_ready("list_findings")

    phase = input.get("phase")
    severity = input.get("severity")
    verdict = input.get("verdict")

    try:
        result = svc_list(
            run_id,
            phase=phase if isinstance(phase, str) else None,
            severity=severity if isinstance(severity, str) else None,
            verdict=verdict if isinstance(verdict, str) else None,
        )
    except TypeError:
        # Slice C is allowed to evolve the signature. Fall back to the
        # bare positional form so we don't break when filters are absent.
        try:
            result = svc_list(run_id)  # type: ignore[misc]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("chat_tools: list_findings fallback failed (%s)", exc)
            return {"error": "internal_error", "tool": "list_findings"}
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("chat_tools: list_findings failed (%s)", exc)
        return {"error": "internal_error", "tool": "list_findings"}

    return _serialise(result)


async def _read_finding(input: dict[str, Any]) -> dict[str, Any]:
    run_id = input.get("run_id")
    property_id = input.get("property_id")
    if not isinstance(run_id, str) or not run_id:
        return {"error": "invalid_input", "tool": "read_finding"}
    if not isinstance(property_id, str) or not property_id:
        return {"error": "invalid_input", "tool": "read_finding"}

    try:
        from web.server.services.finding_loader import get_finding as svc_get  # type: ignore
    except ImportError as exc:
        logger.info("chat_tools: finding_loader not ready (%s)", exc)
        return _service_not_ready("read_finding")

    try:
        result = svc_get(run_id, property_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("chat_tools: read_finding failed (%s)", exc)
        return {"error": "internal_error", "tool": "read_finding"}

    if result is None:
        return {
            "error": "not_found",
            "tool": "read_finding",
            "run_id": run_id,
            "property_id": property_id,
        }
    return _serialise(result)


async def _fetch_bounty_url(input: dict[str, Any]) -> dict[str, Any]:
    """Pull the bounty-scope service in lazily and proxy the call.

    ``fetch_bounty_url`` is read-only: it only triggers an Anthropic
    ``messages.create`` with WebFetch. No SPECA state changes. We treat
    it like any other read-only tool from the chat surface's perspective.
    """

    bug_bounty_url = input.get("bug_bounty_url")
    if not isinstance(bug_bounty_url, str) or not bug_bounty_url:
        return {"error": "invalid_input", "tool": "fetch_bounty_url"}

    contract_addresses = input.get("contract_addresses")
    if contract_addresses is not None and not isinstance(contract_addresses, str):
        contract_addresses = None

    try:
        from web.server.services.bounty_scope import (  # type: ignore
            fetch_scope_from_url,
        )
    except ImportError as exc:
        logger.info("chat_tools: bounty_scope not ready (%s)", exc)
        return _service_not_ready("fetch_bounty_url")

    try:
        result = await fetch_scope_from_url(
            bug_bounty_url, contract_addresses
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("chat_tools: fetch_bounty_url failed (%s)", exc)
        return {"error": "internal_error", "tool": "fetch_bounty_url", "message": str(exc)}

    return _serialise(result)


async def _launch_pipeline(input: dict[str, Any]) -> dict[str, Any]:
    """Spawn a new SPECA run. Called only after the user approved.

    Mirrors the orchestration that the ``POST /api/runs`` HTTP route does
    in Slice B1: build the ``RunStartSpec``, ensure the bare cache, mint
    the run_id (so we can create a worktree under it), then hand off to
    the run supervisor.

    Returns ``{"run_id": "<id>"}`` on success; on validation / workspace
    errors returns ``{"error": "...", "message": "..."}`` so the chat
    surface can surface the problem inline without crashing the turn.
    """

    try:
        from web.server.schemas.run_state import RunStartSpec  # type: ignore
        from web.server.services.run_supervisor import (  # type: ignore
            get_run_supervisor,
            make_run_id,
        )
        from web.server.services.workspace_manager import (  # type: ignore
            WorkspaceError,
            WorkspaceManager,
        )
    except ImportError as exc:
        logger.info("chat_tools: launch_pipeline deps not ready (%s)", exc)
        return _service_not_ready("launch_pipeline")

    try:
        spec = RunStartSpec(**input)
    except Exception as exc:
        return {
            "error": "invalid_input",
            "tool": "launch_pipeline",
            "message": str(exc),
        }

    target_repo = spec.target_repo
    repo_url = f"https://github.com/{target_repo}.git"

    wm = WorkspaceManager()
    run_id = make_run_id(
        target_repo=target_repo,
        bug_bounty_url=str(spec.bug_bounty_url) if spec.bug_bounty_url else None,
    )

    try:
        wm.ensure_bare_cache(repo_url)
        worktree_path = wm.create_worktree(run_id, repo_url, spec.target_ref)
    except WorkspaceError as exc:
        logger.warning("chat_tools: workspace error (%s)", exc)
        return {
            "error": "workspace_error",
            "tool": "launch_pipeline",
            "message": str(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("chat_tools: launch_pipeline workspace failed")
        return {
            "error": "internal_error",
            "tool": "launch_pipeline",
            "message": str(exc),
        }

    # The supervisor mints its own run_id internally — we accept whatever
    # it returns rather than asserting equality with our pre-computed id.
    # In production both are derived from the same helper so they line
    # up; tests that stub the supervisor get the stub's id back.
    supervisor = get_run_supervisor()
    try:
        supervised_run_id = await supervisor.start_run(spec, worktree_path)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("chat_tools: supervisor.start_run failed")
        return {
            "error": "internal_error",
            "tool": "launch_pipeline",
            "message": str(exc),
        }

    return {"run_id": supervised_run_id}


async def _stop_pipeline(input: dict[str, Any]) -> dict[str, Any]:
    """Request cancellation of a running audit (post-approval only)."""

    run_id = input.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return {"error": "invalid_input", "tool": "stop_pipeline"}

    try:
        from web.server.services.run_supervisor import (  # type: ignore
            get_run_supervisor,
        )
    except ImportError as exc:
        logger.info("chat_tools: run_supervisor not ready (%s)", exc)
        return _service_not_ready("stop_pipeline")

    try:
        await get_run_supervisor().cancel_run(run_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("chat_tools: cancel_run failed (%s)", exc)
        return {"error": "internal_error", "tool": "stop_pipeline", "message": str(exc)}

    return {"run_id": run_id, "status": "cancel_requested"}


def _serialise(value: Any) -> dict[str, Any]:
    """Best-effort conversion of an arbitrary service return value to dict.

    We accept pydantic models, dicts, and lists of either; anything else is
    wrapped under ``{"data": ...}`` so the tool result is always a JSON
    object the model can reason about.
    """

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        items = []
        for item in value:
            if hasattr(item, "model_dump"):
                items.append(item.model_dump(mode="json"))
            else:
                items.append(item)
        return {"data": items, "count": len(items)}
    return {"data": value}

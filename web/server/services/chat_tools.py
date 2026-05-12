"""Tool dispatch for the Chat slice — **read-only allowlist**.

This module declares the *only* Anthropic tools the chat surface is allowed
to call in v0. Side-effecting tools (``launch_pipeline`` / ``stop_pipeline``
in the design doc) are intentionally **not** present.

Defense in depth — see ``docs/UI_DESIGN.md`` § 4.8 and the slice E spec:

1. The ``TOOLS`` list is passed verbatim to Anthropic's ``messages.stream``
   — so the model only ever *sees* read-only tools.
2. :func:`dispatch_tool` re-checks ``name`` against :data:`ALLOWED_TOOL_NAMES`
   and raises :class:`ToolNotAllowed` if the model still emits something it
   shouldn't (defense against future SDK / model surprises).
3. The frontend ``<ToolCard>`` component refuses to render an approval UI
   (its ``requiresApproval`` prop is typed ``never``).

Service modules (Slice B / C) are imported lazily inside each handler — if a
slice has not landed yet, we return ``{"error": "service_not_ready", ...}``
instead of raising, so the rest of the conversation flow keeps working.
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

ALLOWED_TOOL_NAMES: frozenset[str] = frozenset(t["name"] for t in TOOLS)


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
    """Dispatch a tool call to the matching read-only service.

    Raises :class:`ToolNotAllowed` if ``name`` is not in
    :data:`ALLOWED_TOOL_NAMES`. Returns a dict that is either the service
    result or a ``{"error": ...}`` envelope — never ``None``.

    The function is ``async`` to leave room for tools that genuinely need
    to await IO (the v0 services are sync but the API stays stable).
    """

    if name not in ALLOWED_TOOL_NAMES:
        raise ToolNotAllowed(name)

    if name == "read_run_status":
        return await _read_run_status(input)
    if name == "list_findings":
        return await _list_findings(input)
    if name == "read_finding":
        return await _read_finding(input)

    # Should never happen because of the allowlist check above, but kept as
    # a hard fallback in case ALLOWED_TOOL_NAMES drifts from the if-chain.
    raise ToolNotAllowed(name)  # pragma: no cover


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

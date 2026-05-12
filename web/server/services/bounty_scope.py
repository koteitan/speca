"""Anthropic-driven bug-bounty scope extractor for Slice B3.

This module is the SDK equivalent of the ``Step 0a: Extract Bug Bounty Scope``
shell step in ``.github/workflows/full-audit.yml`` — it asks Claude to read a
bug bounty program page (Immunefi / Sherlock / Cantina / Code4rena style) and
emit the **union** of the two JSON files the Action writes:

* ``outputs/BUG_BOUNTY_SCOPE.json`` — program_url / program_name / in_scope_*
  / out_of_scope / severity_ratings / reward_range / notes
* ``outputs/EXTRACTED_INPUTS.json`` — spec_urls / keywords for Phase 01a

The SPA's Project Picker "From URL" flow (Section 7.2 of ``docs/UI_DESIGN.md``,
Slice B3) calls this service once and uses the result to pre-fill the launch
form. Returning a single flat dict keeps the round-trip cheap and avoids the
SPA having to merge two payloads.

OAuth-only mode caveat
----------------------

Authenticated-via-claude.ai sessions (``method=="oauth"``) cannot drive the
Anthropic *SDK* directly — those tokens belong to the Claude Code CLI and the
``Anthropic`` Python client expects an ``sk-ant-...`` API key. The Action gets
away with this because it sets ``ANTHROPIC_API_KEY`` from a repo secret;
locally, the user has to either set ``ANTHROPIC_API_KEY`` themselves or paste
their key through ``POST /api/auth/api-key`` (which lands it in
``~/.claude/credentials.json``).

If neither is available we raise :class:`AnthropicUnreachable` with a clear
message — the router maps that to a 503 so the SPA can display a "set up an
API key to use From URL" hint without polluting the chat surface. A future
slice could plumb ``claude --print`` as a subprocess fallback for OAuth-only
mode, but v1 stays SDK-only to keep latency predictable.

WebFetch tool
-------------

The ``anthropic>=0.40`` SDK exposes the server-side ``web_fetch`` tool
(``WebFetchTool20260309Param``); it lives on the **stable** ``ToolUnionParam``
union, so we can pass it to ``messages.create`` directly — no beta header
required. We register it (and its sibling ``web_search``) so the model can
navigate the program page autonomously, exactly the way ``claude --print``
does in the Action. If a future API version retires this exact spec we will
get a clear ``BadRequestError`` from Anthropic, which we surface as
:class:`AnthropicUnreachable` rather than letting it bubble unwrapped.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# --- Constants ---------------------------------------------------------------

_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_MAX_TOKENS = 4096
# The hard ceiling on the SDK call — the Action's ``claude --print`` gets
# roughly 5 minutes per step in CI, but a UI form blocking that long is a
# terrible UX. 90s lets a typical Immunefi page resolve (~1-3 WebFetch calls)
# without leaving the user staring at a spinner.
_SDK_TIMEOUT_SECONDS = 90.0

# Pulled out for tests — see test_picker_fetch_url.py.
_CREDENTIALS_PATH: Path = Path.home() / ".claude" / "credentials.json"


# --- Errors ------------------------------------------------------------------


class BountyScopeError(Exception):
    """Base class for all scope-extraction failures.

    The router catches this last in its ``except`` chain so unknown subclasses
    still produce a 500 with the message, rather than a bare traceback.
    """


class AnthropicUnreachable(BountyScopeError):
    """The Anthropic call could not be made or completed.

    Covers: missing API key, network failure, rate-limit, timeout, and any
    other transient SDK error. The router maps this to ``503`` with
    ``retryable=True`` so the SPA can offer a retry button.
    """


class InvalidScopeResponse(BountyScopeError):
    """Anthropic returned a response we could not parse into the schema.

    Distinct from :class:`AnthropicUnreachable` because the right UX is *not*
    a "try again" button — the model already answered, so blindly retrying
    will likely produce another unparseable answer. The router maps this to
    ``502`` and surfaces the raw text inside ``notes`` upstream.
    """


# --- Internals ---------------------------------------------------------------


def _resolve_api_key() -> str:
    """Find an Anthropic API key, preferring the environment variable.

    Order:

    1. ``ANTHROPIC_API_KEY`` env var (matches what the Action passes in CI).
    2. ``apiKey`` field of ``~/.claude/credentials.json`` (matches what
       ``POST /api/auth/api-key`` writes via :mod:`credentials_service`).

    Raises :class:`AnthropicUnreachable` with an explicit OAuth-mode hint if
    neither is set, so the SPA can surface a "set up API key" call to action.
    """

    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    try:
        raw = _CREDENTIALS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        raw = ""
    except OSError as exc:
        logger.warning(
            "bounty_scope: failed to read %s (%s) — treating as no key",
            _CREDENTIALS_PATH,
            exc,
        )
        raw = ""

    if raw.strip():
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict):
            api_key = data.get("apiKey")
            if isinstance(api_key, str) and api_key.strip():
                return api_key.strip()

    raise AnthropicUnreachable(
        "no API key available; OAuth-only mode requires Claude Code CLI; "
        "set ANTHROPIC_API_KEY for SDK calls"
    )


def _build_prompt(bug_bounty_url: str, contract_addresses: str | None) -> str:
    """Render the user message — kept close to the Action's Step 0a text.

    Differences from the Action prompt:

    * We ask Claude to emit a **single** JSON object (not two files) because
      we are running in a request/response loop, not a shell script.
    * We pin the JSON inside a fenced ``json`` code block. The extractor in
      :func:`_extract_json` falls back to "first {…} run" if the fence is
      missing, but asking for it explicitly improves the hit rate.
    """

    addr_context = ""
    if contract_addresses and contract_addresses.strip():
        addr_context = (
            "Additional in-scope contract addresses provided by user: "
            f"{contract_addresses.strip()}"
        )

    return f"""Read the bug bounty program page at {bug_bounty_url} and extract:

1. Bug bounty scope (program_url, program_name, in_scope_assets,
   in_scope_contracts, out_of_scope, severity_ratings, reward_range, notes).
2. Specification URLs and keywords for Phase 01a discovery
   (spec_urls, keywords — both as comma-separated strings).

IMPORTANT: Many bug bounty programs (e.g., Sherlock, Immunefi) define scope using:
- Specific repository URLs with commit hashes
- Smart contract addresses on various networks (Ethereum, Base, Arbitrum, etc.)
- Specific file paths within repositories
Extract ALL of these. For contract addresses, include the network and contract
name if available.
{addr_context}

Return a SINGLE JSON object inside a ```json ... ``` fenced block with this exact shape:

```json
{{
  "program_url": "{bug_bounty_url}",
  "program_name": "<name or null>",
  "in_scope_assets": ["<assets - include repos, contract addresses, and file paths>"],
  "in_scope_contracts": [
    {{"address": "0x...", "network": "ethereum|base|...", "name": "<if available>"}}
  ],
  "out_of_scope": ["<excluded>"],
  "severity_ratings": "<if available, else null>",
  "reward_range": "<if available, else null>",
  "notes": "<special rules, else null>",
  "spec_urls": "<comma-separated URLs>",
  "keywords": "<comma-separated keywords>"
}}
```

Use the web_fetch tool to read the program page. Do not invent fields.
""".strip()


_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n(?P<body>.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Pull a JSON object out of an assistant message body.

    Strategy:

    1. First look for the canonical ``` ```json …``` ``` fenced block.
    2. If that fails, look for the first balanced ``{…}`` substring.

    Returns ``None`` when nothing parseable is found — the caller treats that
    as :class:`InvalidScopeResponse` and stashes the full text in ``notes``.
    """

    candidates: list[str] = []
    for match in _JSON_FENCE_RE.finditer(text):
        candidates.append(match.group("body"))

    if not candidates:
        # Fallback: first { to matching } using a tiny brace counter so we
        # don't choke on ``}`` inside string literals. Standard json.loads
        # then validates the structure for us.
        start = text.find("{")
        while start != -1:
            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[start : i + 1])
                        break
            start = text.find("{", start + 1)
            if candidates:
                break

    for body in candidates:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    return None


def _collect_text_from_message(message: Any) -> str:
    """Concatenate every ``text`` block from a Messages API response.

    We tolerate two shapes:

    * SDK objects with ``message.content`` = ``list[ContentBlock]`` where each
      block has ``.type`` and ``.text`` attributes (production).
    * Plain dicts (``{"type": "text", "text": "..."}``) — used by the mock
      client in :mod:`web.server.tests.test_picker_fetch_url`.

    Non-text blocks (``tool_use``, ``web_fetch_tool_result``, ``thinking``)
    are skipped — we only care about what the model finally said.
    """

    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if not content:
        return ""

    parts: list[str] = []
    for block in content:
        block_type = getattr(block, "type", None)
        text_value: Any = getattr(block, "text", None)
        if block_type is None and isinstance(block, dict):
            block_type = block.get("type")
            text_value = block.get("text")
        if block_type == "text" and isinstance(text_value, str):
            parts.append(text_value)
    return "\n".join(parts)


def _normalise_scope(
    raw: dict[str, Any],
    *,
    bug_bounty_url: str,
    full_text: str,
) -> dict[str, Any]:
    """Coerce a freshly-parsed JSON object into the response schema shape.

    Tolerant on input — the model may emit ``null`` for fields we type as
    ``""``, or it may give us ``list[str]`` for ``in_scope_contracts`` when
    the program page lists addresses without network metadata. We normalise
    those into the strict schema so :class:`~web.server.schemas.picker.
    FetchUrlResponse` validation always succeeds.
    """

    def _as_str_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v) for v in value if v is not None and str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _as_optional_str(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value if value.strip() else None
        return str(value)

    def _as_csv(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return ",".join(str(v) for v in value if v is not None and str(v).strip())
        if isinstance(value, str):
            return value.strip()
        return str(value)

    contracts_raw = raw.get("in_scope_contracts", [])
    contracts: list[dict[str, Any]] = []
    if isinstance(contracts_raw, list):
        for entry in contracts_raw:
            if isinstance(entry, dict):
                address = entry.get("address")
                if not isinstance(address, str) or not address.strip():
                    continue
                contracts.append(
                    {
                        "address": address.strip(),
                        "network": _as_optional_str(entry.get("network")),
                        "name": _as_optional_str(entry.get("name")),
                    }
                )
            elif isinstance(entry, str) and entry.strip():
                contracts.append(
                    {"address": entry.strip(), "network": None, "name": None}
                )

    program_url = raw.get("program_url")
    if not isinstance(program_url, str) or not program_url.strip():
        program_url = bug_bounty_url

    notes = _as_optional_str(raw.get("notes"))
    if notes is None and full_text and not raw:
        # Defensive: ``raw`` empty would only happen if a future code path
        # reaches us without going through _extract_json — keep the full
        # response visible to the operator.
        notes = full_text

    return {
        "program_url": program_url,
        "program_name": _as_optional_str(raw.get("program_name")),
        "in_scope_assets": _as_str_list(raw.get("in_scope_assets")),
        "in_scope_contracts": contracts,
        "out_of_scope": _as_str_list(raw.get("out_of_scope")),
        "severity_ratings": _as_optional_str(raw.get("severity_ratings")),
        "reward_range": _as_optional_str(raw.get("reward_range")),
        "notes": notes,
        "spec_urls": _as_csv(raw.get("spec_urls")),
        "keywords": _as_csv(raw.get("keywords")),
    }


# --- Client factory (overridable in tests) ----------------------------------
#
# The default factory imports the real Anthropic SDK lazily so this module
# can still be imported (and unit-tested) on a machine without the dependency
# installed — useful for the pure-schema tests.


def _default_client_factory(api_key: str) -> Any:
    """Construct an :class:`anthropic.Anthropic` client.

    Lazily imported so :func:`importlib.import_module` errors at test time
    are easy to spot, and so the module can be loaded for schema-only tests
    in environments where ``anthropic`` is not installed.
    """

    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency pinned
        raise AnthropicUnreachable(f"anthropic SDK not installed: {exc}") from exc

    return Anthropic(api_key=api_key)


# Tests overwrite this attribute to inject a fake client without monkey-
# patching ``anthropic`` itself. Keep the name as a module attribute (not a
# default parameter) so reassignment is straightforward.
client_factory = _default_client_factory


# --- Public API --------------------------------------------------------------


async def fetch_scope_from_url(
    bug_bounty_url: str,
    contract_addresses: str | None = None,
    *,
    model: str = _DEFAULT_MODEL,
) -> dict[str, Any]:
    """Ask Claude to extract bug-bounty scope from ``bug_bounty_url``.

    Returns a dict matching :class:`~web.server.schemas.picker.FetchUrlResponse`.
    On failure raises one of :class:`AnthropicUnreachable` /
    :class:`InvalidScopeResponse` — both inherit from
    :class:`BountyScopeError` for catch-all callers.

    Implementation notes:

    * Uses the *sync* ``Anthropic`` client from inside a worker thread via
      :func:`asyncio.to_thread`. The async ``AsyncAnthropic`` exists, but the
      sync client is the only one whose behaviour is exercised by the rest of
      this codebase (chat_runtime uses ``messages.stream`` synchronously), so
      reusing it here keeps the test surface uniform.
    * Registers the server-side ``web_fetch`` and ``web_search`` tools so the
      model can actually pull the program page. The SDK ships these on the
      stable ``ToolUnionParam`` union (anthropic 0.101+), no beta header
      required.
    """

    api_key = _resolve_api_key()  # raises AnthropicUnreachable if absent.

    try:
        client = client_factory(api_key)
    except AnthropicUnreachable:
        raise
    except Exception as exc:  # pragma: no cover - factory failure is rare
        raise AnthropicUnreachable(
            f"failed to construct Anthropic client: {exc}"
        ) from exc

    prompt = _build_prompt(bug_bounty_url, contract_addresses)
    tools: list[dict[str, Any]] = [
        # ``web_fetch_20260309`` is the newest variant in anthropic 0.101 and
        # accepts ``allowed_domains=None`` to mean "any URL".
        {"type": "web_fetch_20260309", "name": "web_fetch"},
        # web_search complements web_fetch when the model wants to look up
        # an indirection page (e.g. an Immunefi listing whose actual scope
        # lives on a GitHub README).
        {"type": "web_search_20260209", "name": "web_search"},
    ]

    def _call() -> Any:
        # Wrapped so the SDK's synchronous I/O runs in a worker thread.
        return client.messages.create(
            model=model,
            max_tokens=_DEFAULT_MAX_TOKENS,
            tools=tools,  # type: ignore[arg-type]
            messages=[{"role": "user", "content": prompt}],
        )

    try:
        message = await asyncio.wait_for(
            asyncio.to_thread(_call), timeout=_SDK_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError as exc:
        raise AnthropicUnreachable(
            f"Anthropic call timed out after {_SDK_TIMEOUT_SECONDS:.0f}s"
        ) from exc
    except AnthropicUnreachable:
        raise
    except Exception as exc:
        # Anthropic-specific exceptions (APIConnectionError, RateLimitError,
        # AuthenticationError, etc.) all inherit from ``AnthropicError``;
        # treating "anything from the SDK" as unreachable lets the SPA show a
        # single, consistent retry UI without us re-implementing the error
        # taxonomy here.
        logger.warning("bounty_scope: SDK call failed (%s)", exc)
        raise AnthropicUnreachable(str(exc) or exc.__class__.__name__) from exc

    full_text = _collect_text_from_message(message)
    parsed = _extract_json(full_text) if full_text else None

    if parsed is None:
        # JSON parse failed — surface the raw text so the operator can see
        # what the model actually said. Slice B3 spec: the response shape
        # should still match FetchUrlResponse so the SPA can render the form
        # with empty fields + a populated ``notes`` callout.
        fallback = {
            "program_url": bug_bounty_url,
            "notes": full_text or "Anthropic returned an empty response.",
        }
        logger.info(
            "bounty_scope: failed to extract JSON from response (len=%d)",
            len(full_text or ""),
        )
        return _normalise_scope(
            fallback, bug_bounty_url=bug_bounty_url, full_text=full_text
        )

    return _normalise_scope(parsed, bug_bounty_url=bug_bounty_url, full_text=full_text)

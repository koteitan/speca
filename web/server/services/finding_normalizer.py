"""Normalization helpers for raw Phase 03/04 PARTIAL records.

This module is the Python port of ``cli/src/lib/findings/loader.ts`` (only
the normalization paths — file IO lives in :mod:`finding_loader`). The CLI
loader is the source of truth for *behaviour*; this module exists so the
web backend can produce the same flattened ``Finding`` shape without
importing TypeScript.

Design choices mirrored from the CLI port:

* **Lenient severity normalization** — ``"MEDIUM"``, ``"medium"``, ``"Med"``
  all normalize to ``"Medium"``. Unknown / empty / whitespace falls back to
  ``"Informational"`` (the CLI returned empty string; v0 backend returns
  ``Informational`` so the response always validates against the closed
  enum and the frontend doesn't have to special-case ``""``).
* **Known verdicts pass-through** — closed list matches by exact uppercase.
  Unknown verdicts are returned as-is so forks adding new verdicts via
  ``--config`` continue to render (frontend ``VerdictChip`` shows them with
  a neutral style).
* **Code path parsing** — handles both string forms (``src/foo.cpp::sym::L1-2``,
  ``src/bar.cpp:80-91``) and the typed ``CodeScope`` object with a
  ``locations`` array. Returns ``file`` + ``line_range`` separately so the
  frontend can render ``file::line_range`` and the Slice G ``<OpenInVSCode>``
  can pick the components apart without re-parsing.
"""

from __future__ import annotations

import re
from typing import Any

KNOWN_SEVERITIES: tuple[str, ...] = (
    "Critical",
    "High",
    "Medium",
    "Low",
    "Informational",
)

KNOWN_VERDICTS: frozenset[str] = frozenset(
    {
        "CONFIRMED_VULNERABILITY",
        "CONFIRMED_POTENTIAL",
        "DISPUTED_FP",
        "DOWNGRADED",
        "NEEDS_MANUAL_REVIEW",
        "PASS_THROUGH",
    }
)


def normalize_severity(raw: Any) -> str:
    """Coerce arbitrary severity strings into the closed ``Severity`` enum.

    Mirrors ``normaliseSeverity`` in the TS loader but defaults to
    ``"Informational"`` on miss rather than the empty string. The strict
    Pydantic ``Literal[...]`` on the response model would reject ``""``
    so we collapse the fallback here once.

    >>> normalize_severity("MEDIUM")
    'Medium'
    >>> normalize_severity("low ")
    'Low'
    >>> normalize_severity("Critical")
    'Critical'
    >>> normalize_severity(None)
    'Informational'
    >>> normalize_severity("unknown_label")
    'Informational'
    """

    if not isinstance(raw, str):
        return "Informational"
    stripped = raw.strip()
    if not stripped:
        return "Informational"
    cap = stripped[0].upper() + stripped[1:].lower()
    if cap in KNOWN_SEVERITIES:
        return cap
    return "Informational"


def normalize_verdict(raw: Any) -> str | None:
    """Pass through verdict strings, only upper-casing the closed set.

    The closed enum is matched case-insensitively so a fork emitting
    ``"confirmed_potential"`` is still treated as known. Unknown verdicts
    (including ``None`` / empty) are returned unchanged — the frontend
    decides whether to render them.

    >>> normalize_verdict("CONFIRMED_POTENTIAL")
    'CONFIRMED_POTENTIAL'
    >>> normalize_verdict("confirmed_potential")
    'CONFIRMED_POTENTIAL'
    >>> normalize_verdict("CUSTOM_NEW_VERDICT")
    'CUSTOM_NEW_VERDICT'
    >>> normalize_verdict("")
    >>> normalize_verdict(None)
    """

    if not isinstance(raw, str):
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    upper = stripped.upper()
    if upper in KNOWN_VERDICTS:
        return upper
    return stripped


# Code path parsing -----------------------------------------------------------

# Pattern A: "file::symbol::Lstart[-Lend]" or "file::symbol:Lstart[-Lend]"
# Note: when the symbol contains "::" itself (qualified names like
# "Header::IMPL_SERIALIZABLE"), greedy/lazy matching gets ambiguous. We
# anchor on the trailing "::L<digits>" or ":L<digits>" so the symbol can
# legally contain "::".
_CODE_PATH_RE_A = re.compile(
    r"^(?P<file>[^:]+?)::(?P<symbol>.+?)(?:::|:)L(?P<start>\d+)(?:-L?(?P<end>\d+))?$"
)
# Pattern B: "file:start-end" (numeric, no L prefix)
_CODE_PATH_RE_B = re.compile(
    r"^(?P<file>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?$"
)


def _format_line_range(start: str | int | None, end: str | int | None) -> str | None:
    """Render ``L<start>[-L<end>]`` from numeric components.

    Returns ``None`` if no usable start is supplied. ``end`` collapses to
    ``start`` when missing or equal, matching the CLI's intent of "no range,
    single line".
    """

    if start in (None, "", 0, "0"):
        return None
    try:
        s = int(start)
    except (TypeError, ValueError):
        return None
    if end in (None, "", 0, "0"):
        return f"L{s}"
    try:
        e = int(end)
    except (TypeError, ValueError):
        return f"L{s}"
    if e <= s:
        return f"L{s}"
    return f"L{s}-L{e}"


def normalize_code_path(raw: Any) -> tuple[str | None, str | None]:
    """Split a raw ``code_path`` (string or CodeScope object) into file + range.

    Returns ``(file, line_range)``. Either component may be ``None`` when
    the raw value doesn't carry it — the frontend renders ``file`` alone,
    ``file::line_range``, or nothing depending on what's available.

    Supported inputs:

    * ``"src/foo.cpp::funcName::L11-L20"`` -> ``("src/foo.cpp", "L11-L20")``
    * ``"src/foo.cpp::Header::IMPL_SERIALIZABLE::L80-91"`` -> file split off
    * ``"src/bar.cpp:128-145"`` -> ``("src/bar.cpp", "L128-L145")``
    * ``"src/baz.cpp"`` (no line info) -> ``("src/baz.cpp", None)``
    * ``{"locations": [{"file": "...", "line_range": {"start": 1, "end": 2}}]}``
      -> first location wins

    >>> normalize_code_path("src/net.cpp::funcA::L80-91")
    ('src/net.cpp', 'L80-L91')
    >>> normalize_code_path("src/net.cpp:80-91")
    ('src/net.cpp', 'L80-L91')
    >>> normalize_code_path("src/net.cpp")
    ('src/net.cpp', None)
    >>> normalize_code_path(None)
    (None, None)
    """

    if raw is None:
        return None, None

    # CodeScope object form
    if isinstance(raw, dict):
        locations = raw.get("locations")
        if isinstance(locations, list) and locations:
            first = locations[0]
            if isinstance(first, dict):
                file_ = first.get("file")
                lr = first.get("line_range")
                start = end = None
                if isinstance(lr, dict):
                    start = lr.get("start")
                    end = lr.get("end")
                return (
                    str(file_) if isinstance(file_, str) and file_ else None,
                    _format_line_range(start, end),
                )
        return None, None

    if not isinstance(raw, str):
        return None, None

    s = raw.strip()
    if not s:
        return None, None

    m = _CODE_PATH_RE_A.match(s)
    if m:
        return m.group("file"), _format_line_range(m.group("start"), m.group("end"))

    m = _CODE_PATH_RE_B.match(s)
    if m:
        return m.group("file"), _format_line_range(m.group("start"), m.group("end"))

    # Fallback: take the substring before the first ``::`` as the file,
    # since at minimum Phase 03 emits ``file::...`` even when the suffix
    # doesn't match our pattern.
    if "::" in s:
        file_ = s.split("::", 1)[0]
        return file_, None
    return s, None


# Locations / gates helpers ---------------------------------------------------


def extract_locations(raw_item: dict[str, Any]) -> tuple[str | None, str | None]:
    """Pull the primary (file, line_range) out of a Phase 03 audit item.

    Prefers ``code_scope.locations[0]`` (typed) over the legacy
    ``code_path`` string. Used by the loader to fill ``Finding.file`` /
    ``Finding.line_range`` deterministically — the same field that Slice G
    will target with its ``data-testid="finding-code-path"`` hook.
    """

    scope = raw_item.get("code_scope")
    if isinstance(scope, dict):
        file_, range_ = normalize_code_path(scope)
        if file_:
            return file_, range_

    return normalize_code_path(raw_item.get("code_path"))


def extract_gates_passed(raw_item: dict[str, Any]) -> list[str]:
    """Best-effort extraction of Phase 04 ``gates_passed``.

    The Phase 04 record may emit a free-form ``reviewer_notes`` string
    referencing "Gate 1", "Gate 2", "Gate 3" — we don't try to parse that.
    If the upstream JSON ever grows a dedicated ``gates_passed`` array we
    pass it through; otherwise return empty (the frontend hides the
    section when this is empty).
    """

    val = raw_item.get("gates_passed")
    if isinstance(val, list):
        return [str(x) for x in val if isinstance(x, (str, int))]
    return []

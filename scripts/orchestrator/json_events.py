"""NDJSON event emitter for ``run_phase.py --json``.

Emits one JSON object per line on stdout for pipeline-level transitions.
Consumers (TUI dashboards, CI scripts) read these events instead of
scraping decorative log output.

Event shape:
    {"type": <event-type>, "ts": <iso-utc>, "phase": <phase-id>, ...payload}

Event types (per docs/SPECA_CLI_SPEC.md §8.2 / §12.1):
    phase-started            {phase, workers, max_concurrent, force, model?}
    phase-completed          {phase, duration_s, total_results}
    phase-failed             {phase, reason, duration_s}
    budget-exceeded          {phase, cost_usd, max_budget_usd, duration_s}
    circuit-breaker-tripped  {phase, reason, stats, duration_s}
    pipeline-started         {phases, workers, max_concurrent, force}
    pipeline-completed       {phases, results, duration_s}
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import IO, Any


class JsonEventEmitter:
    """Emit pipeline events as NDJSON on a target stream.

    Stays a no-op when ``enabled=False`` so callers can wire it
    unconditionally and toggle behaviour from the CLI flag.
    """

    def __init__(self, enabled: bool, stream: IO[str] | None = None) -> None:
        self.enabled = enabled
        # Capture the real stdout up-front. ``run_phase.py`` redirects
        # ``sys.stdout`` to stderr in --json mode to suppress decorative
        # output; capturing here keeps events going to the actual stdout.
        self._stream = stream if stream is not None else sys.__stdout__

    def emit(self, event_type: str, **payload: Any) -> None:
        if not self.enabled:
            return
        record: dict[str, Any] = {
            "type": event_type,
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        }
        record.update(payload)
        try:
            line = json.dumps(record, ensure_ascii=False, default=str)
            self._stream.write(line + "\n")
            self._stream.flush()
        except (BrokenPipeError, ValueError):
            # Consumer hung up or stream closed; let the orchestrator
            # finish and surface its own errors instead of crashing here.
            self.enabled = False

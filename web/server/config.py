"""Runtime path resolution for the SPECA web backend.

All paths are resolved as :class:`pathlib.Path` so that callers do not have to
worry about Windows vs POSIX separators. The repository root is derived from
this file's location (``web/server/config.py`` lives two directories below the
repo root) so the resolution works regardless of the cwd of the process that
imports the module.
"""

from __future__ import annotations

from pathlib import Path

# ``web/server/config.py`` -> ``web/server`` -> ``web`` -> ``<repo root>``
SPECA_REPO_ROOT: Path = Path(__file__).resolve().parents[2]

# Per-run state managed by ``scripts/run_phase.py`` and friends.
SPECA_RUNS_DIR: Path = SPECA_REPO_ROOT / ".speca" / "runs"

# Phase outputs (``outputs/<phase>_PARTIAL_*.json``, ``outputs/logs/*.jsonl``).
SPECA_OUTPUTS_DIR: Path = SPECA_REPO_ROOT / "outputs"

# User-scoped Claude CLI directory (credentials, skills, worktrees, ...).
USER_CLAUDE_DIR: Path = Path.home() / ".claude"

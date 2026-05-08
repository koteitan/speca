---
sidebar_position: 2
---

# Quickstart (5 minutes)

A walkthrough that gets you to your first audit in five minutes.

## Setup (1 minute)

Generate metadata for the target codebase.

```bash
cd speca
speca init
```

This command produces `outputs/TARGET_INFO.json` and `outputs/BUG_BOUNTY_SCOPE.json`.

## Run the audit pipeline (3 minutes)

Run Phase 01a through Phase 04 in a single invocation.

```bash
uv run python3 scripts/run_phase.py --target 04 --workers 4
```

You can monitor the pipeline as it progresses. For details on each phase, see the [Pipeline](../pipeline/overview.md) section.

## Review the results (1 minute)

Browse the results in your browser.

```bash
speca browse outputs/04_PARTIAL_*.json
```

For each finding, the viewer shows the corresponding property, the proof attempt details, and the result of the 3-gate review.

## Drill-down analysis

You can ask follow-up questions through the Claude Code CLI.

```bash
speca ask "Why was this vulnerability detected?"
```

You can inspect the rationale behind a proof attempt (the proof gap) and identify exactly which spec-level constraint is being violated.

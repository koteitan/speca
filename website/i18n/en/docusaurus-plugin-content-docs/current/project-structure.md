---
sidebar_position: 6
---

# Project structure

This page describes the folder layout of the SPECA repository and the role of each directory.

## Directory tree

```
speca/
├── scripts/
│   ├── orchestrator/       # Async Python orchestrator (main logic)
│   ├── run_phase.py        # Pipeline execution entry point
│   └── setup_mcp.sh        # MCP server registration script
├── prompts/                # Worker prompts for each Phase
│   ├── 01a_spec_discovery/
│   ├── 01b_subgraph_extractor/
│   ├── 01e_property_generation/
│   └── ...
├── cli/                    # speca-cli (Node.js + Ink TUI frontend)
│   ├── src/
│   │   └── cli.tsx         # CLI entry point
│   └── README.md
├── tests/                  # pytest test suite
├── outputs/                # Pipeline I/O files (gitignored)
│   ├── TARGET_INFO.json    # Audit target information
│   ├── BUG_BOUNTY_SCOPE.json
│   └── {phase}_PARTIAL_*.json
├── automation/             # GitHub Actions workflow definitions
├── website/               # Docusaurus documentation site (this site)
├── .claude/
│   └── skills/             # Claude Code skill definitions (01a / 01b)
├── CLAUDE.md               # Architecture, design decisions, command reference
└── README.md               # Project overview and arXiv paper link
```

## Roles of major directories

**`scripts/orchestrator/`**  
The core of the pipeline. `config.py` defines the configuration of each Phase, and `base.py` manages batch generation, parallel execution, and resume. `runner.py` invokes the Claude Code CLI, and `watchdog.py` monitors cost.

**`prompts/`**  
Contains the Claude prompts for each Phase. Phases 01a and 01b are defined as skills (`SKILL.md`); the remaining Phases inline the worker prompts directly. Reading the prompts shows what each Phase is analyzing and how.

**`cli/`**  
The TUI frontend that provides the `speca init` / `speca run` / `speca browse` and other commands. The entry point is `cli/src/cli.tsx`. Implemented in Node.js + Ink.

**`tests/`**  
Automated tests that run with pytest. They run as a CI pre-flight check before every Phase. Run with `uv run python3 -m pytest tests/ -v --tb=short`.

**`outputs/`**  
Holds pipeline input files (`TARGET_INFO.json`, `BUG_BOUNTY_SCOPE.json`) and the outputs of each Phase (`{phase}_PARTIAL_*.json`). Listed in `.gitignore`, so audit results never leak into the repository.

**`automation/`**  
GitHub Actions workflow definitions. CI jobs are split per Phase, allowing each Phase to be re-executed independently.

## Where to start reading the code

If you want to grasp the overall pipeline flow, start from `scripts/run_phase.py`. The flow is: argument parsing → `PhaseConfig` selection → `BaseOrchestrator.run()`.

If you want to investigate the CLI behavior, the entry point is `cli/src/cli.tsx`.

The concrete analysis logic for each Phase is written in the corresponding prompt under `prompts/`. Phases 01e, 02c, 03, and 04 inline all logic into the prompt.

For the *why* behind the layout — the harness invariants, prompt-vs-skill split, and the non-obvious context-flow decisions — see the [Agent design](./agent-design/overview.md) section. Background and rationale of design decisions are also summarized in [CLAUDE.md](https://github.com/NyxFoundation/speca/blob/main/CLAUDE.md).

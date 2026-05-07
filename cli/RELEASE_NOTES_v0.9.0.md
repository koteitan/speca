# speca-cli v0.9.0

Soft-launch release of the TUI front-end for [SPECA](https://github.com/NyxFoundation/speca).

This is a **pre-1.0 preview** that reserves the npm package name and exercises the
tag-driven release pipeline. All features from the M1–M7 milestones are included
and tested — the 0.9.x line will collect any rough edges surfaced by early users
before v1.0.0 commits to API stability.

```bash
npx speca-cli@latest doctor
```

## What you get

- `speca version` — print the speca-cli version
- `speca doctor` — diagnose Node / uv / git / claude-code / OAuth scope readiness
- `speca auth login` — paste-code OAuth flow against Anthropic Claude Code (or `--api-key` fallback)
- `speca auth status` — list saved accounts with token expiry
- `speca init` — interactive wizard (powered by `@clack/prompts`) that writes valid `TARGET_INFO.json` and `BUG_BOUNTY_SCOPE.json`, validated against the Pydantic-derived JSON Schemas
- `speca run` — Ink TUI dashboard that drives `scripts/run_phase.py --json`, with phase rows, worker badges, log pane, budget gauge, and budget-exceeded modal
- `speca browse` — finding browser with severity-coloured table, filter DSL (`severity:` / `verdict:` / `prop:` / `repo:` / `text:` + AND/OR/NOT + wildcards), sort, code peek with syntax highlighting
- `speca ask` — chat with Claude about a finding via `claude --output-format stream-json --resume`, with 50 KB context cap and project-local session persistence

## Implementation highlights

- **No re-implementation of audit logic.** `speca-cli` invokes the existing Python orchestrator via `uv run python3 scripts/run_phase.py` and parses its NDJSON event stream — every phase still runs in the Python orchestrator under the hood.
- **Cross-platform token store.** OAuth tokens land in `~/.config/speca/auth.json` (Windows: `%APPDATA%\speca\auth.json`) with `chmod 0o600` on POSIX and atomic tmp+rename writes.
- **Vendored OAuth.** `auth.ts` / `pkce.ts` / `constants.ts` are vendored verbatim from MIT-licensed [`ex-machina-co/opencode-anthropic-auth`](https://github.com/ex-machina-co/opencode-anthropic-auth); per-file provenance is in `cli/docs/VENDOR.md`.
- **Theme + keybind layer.** Three themes ship in v0.9 (dark / light / solarized); the active theme + per-action keybind overrides come from `~/.config/speca/config.toml`.
- **Two non-TUI modes for CI.** Every subcommand respects `--no-tui` (plain text) and `--json` (NDJSON). `speca run --json` re-emits the Python orchestrator's pipeline events with a stamped `ts` envelope so downstream tools can rely on a single contract.
- **Type-checked Python ↔ TS contract.** Pipeline events are Pydantic-modelled in Python and the TS Zod schema is auto-generated from the exported JSON Schema, so a Python-side rename surfaces as a CLI build error rather than a silent runtime drift.

## Tested

- 282 pytest cases (orchestrator + Phase 01b recovery)
- 256 vitest cases (CLI core + render + property tests + Python ↔ TS event contract)
- E2E: `run_phase.py --phase 01b --json` output is validated against the generated Zod union on every push
- CI matrix: `ubuntu-22.04` × `macos-14` × `windows-2022` × Node 20 / 22 — all six cells pass on every PR

## Roadmap to v1.0.0

This 0.9.x line is the API-soak window. Expected work before v1.0.0:

- Asciinema-recorded demo cast (recipe in `cli/asciinema/README.md`)
- Multi-finding chat context for `speca ask`
- `speca attach` (read-only attach to a running pipeline)
- Headless "start now, attach later" pipeline mode

Anything else surfaced by 0.9.x users will be triaged in the GitHub tracker.

## Install

```bash
# Always-fresh (recommended for the 0.9.x preview)
npx speca-cli@latest <command>

# Pin to this release
npx speca-cli@0.9.0 <command>

# Global install
npm install -g speca-cli
```

Requires **Node 20+**. For the audit pipeline you also need `uv`, `git`, and `claude` (`speca doctor` checks all of them).

## Documentation

- [`cli/README.md`](https://github.com/NyxFoundation/speca/blob/main/cli/README.md) — usage guide
- [`cli/TESTING.md`](https://github.com/NyxFoundation/speca/blob/main/cli/TESTING.md) — manual test recipe
- [`cli/CHANGELOG.md`](https://github.com/NyxFoundation/speca/blob/main/cli/CHANGELOG.md) — changelog
- [`docs/SPECA_CLI_SPEC.md`](https://github.com/NyxFoundation/speca/blob/main/docs/SPECA_CLI_SPEC.md) — design spec

## Feedback

Issues and feedback for the 0.9.x preview welcome at https://github.com/NyxFoundation/speca/issues.

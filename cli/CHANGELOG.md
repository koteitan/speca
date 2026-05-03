# Changelog

All notable changes to `speca-cli` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-05-04

First production release. Implements all M1–M6 milestones from
[`docs/SPECA_CLI_SPEC.md`](../docs/SPECA_CLI_SPEC.md) §11.

### Added

#### Core commands
- `speca version` — print speca-cli version
- `speca doctor` — diagnose Node / uv / git / claude-code / OAuth scope readiness
- `speca auth login` — paste-code OAuth flow against Anthropic Claude Code
- `speca auth login --api-key <key>` — fallback for users without a Claude Code subscription
- `speca auth status` — list saved accounts with token expiry
- `speca init` — `@clack/prompts` wizard that writes valid `TARGET_INFO.json` and `BUG_BOUNTY_SCOPE.json` (validated against the Pydantic-derived JSON Schemas)
- `speca run` — TUI dashboard that drives `scripts/run_phase.py --json`, with phase rows, worker badges, log pane, budget gauge, and budget-exceeded modal
- `speca browse` — finding browser with severity-coloured table, filter DSL (`severity:`, `verdict:`, `prop:`, `repo:`, `text:`, AND/OR/NOT, wildcards), sort, and code peek with syntax highlighting
- `speca ask` — chat with Claude about a finding via `claude --output-format stream-json --resume`, with 50KB context cap and project-local session persistence

#### Infrastructure
- Vendored `ex-machina-co/opencode-anthropic-auth` (MIT) for OAuth — see `docs/VENDOR.md`
- Cross-platform token store at `~/.config/speca/auth.json` (Windows: `%APPDATA%\speca\auth.json`), atomic write, chmod 0600 on POSIX
- NDJSON pipeline event emitter (`scripts/orchestrator/json_events.py`) with 7 event types
- JSON Schema export from Pydantic (`scripts/export_schemas.py`) bundled into the npm package
- Theme system (dark / light / solarized) loadable from `~/.config/speca/config.toml`
- Keybind override system via the same `config.toml`
- Generic `<ErrorModal>` covering SPEC §10.4's seven failure modes
- Common `--no-tui` and `--json` output-mode helpers (`getOutputMode`, `printNoTui`, `emitJson`)

#### Documentation
- `cli/README.md` (~350 lines) — end-user guide
- `docs/hiro/cli-quickstart.md` — Japanese quickstart for hirorogo team
- `cli/asciinema/README.md` — recording recipe for the demo cast
- `cli/docs/VENDOR.md` — vendored-code provenance tracker

### Tests
- 220 vitest cases across 24 files, all green on the matrix (ubuntu-22.04 / macOS 14 / windows-2022 × Node 20 / 22)

### Deferred to v1.1+
- Wiring the M6 polish infrastructure (theme, keybinds, ErrorModal, output-mode helpers) into the M3/M4/M5 subcommand renderers — the infrastructure ships standalone in v1.0; subcommand integration follows in v1.1
- `speca attach` (read-only attach to a running pipeline)
- Multi-finding chat context for `speca ask`
- Asciinema-recorded README demo cast (recording recipe shipped, asset to be uploaded post-release)
- Headless "start now, attach later" pipeline mode

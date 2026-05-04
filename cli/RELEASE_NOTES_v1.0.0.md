# speca-cli v1.0.0

First production release of the TUI front-end for [SPECA](https://github.com/NyxFoundation/speca).

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
- **Theme + keybind layer.** Three themes ship in v1 (dark / light / solarized); the active theme + per-action keybind overrides come from `~/.config/speca/config.toml`.
- **Two non-TUI modes for CI.** Every subcommand respects `--no-tui` (plain text) and `--json` (NDJSON). `speca run --json` re-emits the Python orchestrator's pipeline events with a stamped `ts` envelope so downstream tools can rely on a single contract.
- **CI matrix green.** `ubuntu-22.04` × `macos-14` × `windows-2022` × Node 20 / 22 — all 6 cells pass on every PR.

## Tested

- 220 vitest cases across 24 files
- Smoke harness (`cli/TESTING.md` §「まとめ」) covers `version` / `doctor` / `auth status` / `init --non-interactive` / U2 schema validate / `run --phase 01b --json` / `browse --no-tui` / `browse --json`
- `npm pack --dry-run` ships **152.3 kB** / 200 files (`speca-cli@1.0.0`)

## Deferred to v1.1+

These ship as standalone infrastructure in v1.0 but are not yet wired into every subcommand:

- M6 polish wiring for `speca browse` and `speca ask` (theme works; keybind override only wired on `speca run` so far — `browse`/`ask` use direct `useInput` until v1.1)
- `speca attach` (read-only attach to a running pipeline)
- Multi-finding chat context for `speca ask`
- asciinema-recorded demo cast (recipe is in `cli/asciinema/README.md`; `.cast` files coming in a v1.0.x patch)

Full v1.1+ backlog: see [`cli/CHANGELOG.md`](https://github.com/NyxFoundation/speca/blob/main/cli/CHANGELOG.md#deferred-to-v11).

## Install / upgrade

```bash
# Always-fresh
npx speca-cli@latest <command>

# Pin to this release
npx speca-cli@1.0.0 <command>

# Global install
npm install -g speca-cli
```

Requires **Node 20+**. For the audit pipeline you also need `uv`, `git`, and `claude` (`speca doctor` checks all of them).

## Documentation

- [`cli/README.md`](https://github.com/NyxFoundation/speca/blob/main/cli/README.md) — usage guide
- [`cli/TESTING.md`](https://github.com/NyxFoundation/speca/blob/main/cli/TESTING.md) — manual test recipe
- [`cli/CHANGELOG.md`](https://github.com/NyxFoundation/speca/blob/main/cli/CHANGELOG.md) — full v1.0.0 entry
- [`docs/SPECA_CLI_SPEC.md`](https://github.com/NyxFoundation/speca/blob/main/docs/SPECA_CLI_SPEC.md) — design spec
- [`docs/hiro/cli-quickstart.md`](https://github.com/NyxFoundation/speca/blob/main/docs/hiro/cli-quickstart.md) — Japanese quickstart

## Thanks

Tracking issue: [#3](https://github.com/NyxFoundation/speca/issues/3). Spec authors: hirorogo. Implementation: hirorogo + Claude (parallel agent build).

---

**Full changelog:** https://github.com/NyxFoundation/speca/blob/main/cli/CHANGELOG.md

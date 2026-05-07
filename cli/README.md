# speca-cli

> **v0.9.0** (soft launch ahead of v1.0.0 GA) — TUI front-end for the SPECA security-audit pipeline. Implements milestones M1–M7 of [issue #3](https://github.com/NyxFoundation/speca/issues/3) per [`docs/SPECA_CLI_SPEC.md`](../docs/SPECA_CLI_SPEC.md).

## What is speca-cli

`speca-cli` is a terminal user interface (TUI) for the [SPECA](https://github.com/NyxFoundation/speca) specification-anchored security-audit pipeline. SPECA itself is a Python orchestrator that drives the Claude Code CLI through six phases (`01a → 01b → 01e → 02c → 03 → 04`); running it bare means cloning the repo, hand-editing two JSON files, and tailing JSONL logs in another terminal. `speca-cli` collapses that into one `npx` command:

- **Authenticate once** with your existing Claude Code subscription (no Anthropic API key required).
- **Configure a target** (repo + spec URLs + budget) through guided prompts instead of raw JSON editing.
- **Watch the pipeline run** with live phase rows, log tail, and budget gauge.
- **Browse findings** sortable by severity and filterable by verdict, with code peek.
- **Ask Claude** about a finding via the embedded chat pane.

The Python orchestrator under `scripts/orchestrator/` is **not rewritten** — `speca-cli` invokes it as a subprocess and parses its `--json` event stream. See [SPEC §1](../docs/SPECA_CLI_SPEC.md#1-overview).

## Quick start

```bash
# Run the doctor with no install
npx speca-cli@latest doctor
```

If `doctor` reports all green you can move on to `auth login` and `init`. If something is missing it tells you exactly what to install.

## Installation

You can use `speca-cli` in two ways. The npm package is the smoothest path; the git build is for hacking on the CLI itself or pinning to an unreleased commit.

### Option 1 — Install from npm (recommended)

```bash
# Always-fresh, no global install — recommended for first-time use
npx speca-cli@latest <command>

# Pin to a specific release
npx speca-cli@0.9.0 <command>

# Global install
npm install -g speca-cli
speca <command>
```

The published package is [`speca-cli`](https://www.npmjs.com/package/speca-cli) on the public npm registry. New tagged releases are published automatically by the [release workflow](../.github/workflows/release.yml) when a `v*.*.*` tag is pushed.

### Option 2 — Build from a git checkout

Use this path when you want to test an unreleased branch / PR, run with local code changes, or avoid the npm registry entirely.

```bash
git clone https://github.com/NyxFoundation/speca.git
cd speca/cli

npm install        # install dev + runtime deps
npm run build      # sync-schemas + tsc → dist/
node dist/cli.js doctor
```

If you'd like a `speca` shim on your PATH that points at the local build (so you can iterate without re-running `node dist/cli.js …`), use `npm link`:

```bash
npm link           # run inside cli/ — registers `speca` globally
speca doctor       # uses your local build

# Later, when you want to drop the shim:
npm unlink -g speca-cli
```

For Python-side changes (the orchestrator that the CLI invokes), keep `uv sync` up to date in the repo root and `speca run` will pick them up automatically — `speca-cli` always invokes `uv run python3 scripts/run_phase.py …` against the current working directory's checkout.

### Requirements

| Tool | Version | Why | Install |
|---|---|---|---|
| **Node.js** | `>= 20.0.0` | Runtime for the CLI itself (`engines.node` in `package.json`) | https://nodejs.org/ |
| **git** | any recent | Phase 03/04 auto-clone the target repository at the pinned commit | https://git-scm.com/downloads |
| **uv** | any recent | Drives the Python orchestrator (replaces `pip`) | https://docs.astral.sh/uv/getting-started/installation/ |
| **Claude Code CLI** | `>= 2.x` | Used for the embedded "Ask Claude" pane and as a worker runtime when subscription auth is active | `npm install -g @anthropic-ai/claude-code` |

`speca doctor` checks each of these; install whatever is missing and re-run.

> **Distribution caveat.** The npm tarball does **not** bundle the Python sources. `speca-cli` either auto-clones `NyxFoundation/speca` into `~/.cache/speca/<version>/` or uses `SPECA_REPO=/path/to/your/checkout`. See [SPEC §10.2](../docs/SPECA_CLI_SPEC.md#102-bootstrapping-the-python-repo).

## Commands

All commands ship in v0.9.0.

| Command | Description |
|---|---|
| `speca version` | Print the speca-cli version |
| `speca doctor` | Check Node, uv, git, claude-code, and OAuth scope |
| `speca auth status` | Print current auth state (subscription / api-key / none) |
| `speca auth login` | Run the Claude Code OAuth paste-code flow (or fall back to API key) |
| `speca init` | New-project wizard — writes `outputs/TARGET_INFO.json` + `outputs/BUG_BOUNTY_SCOPE.json` |
| `speca run` | Pipeline run with a live Ink dashboard (phase rows, log tail, budget gauge) |
| `speca browse` | TUI: severity-coloured finding browser with filter DSL + code peek |
| `speca ask` | Chat with Claude about a finding (claude-code session bridge) |
| `speca help` | Show usage |

Common flags (apply to every subcommand; see [SPEC §6](../docs/SPECA_CLI_SPEC.md#6-command-surface)):

| Flag | Description | Default |
|---|---|---|
| `--no-tui` | Force plain-text output (CI mode) | auto-detect |
| `--json` | Emit machine-readable events on stdout (implies `--no-tui`) | `false` |

### `speca version`

Prints the npm package version (currently `0.9.0`).

### `speca doctor`

Runs four installation checks and one auth check:

| Check | Status meaning |
|---|---|
| **node** | `OK` if `process.version` is `>= v20`. `FAIL` otherwise. |
| **uv** | `OK` if `uv --version` succeeds. `FAIL` with install link otherwise. |
| **git** | `OK` if `git --version` succeeds. `FAIL` otherwise. |
| **claude** | `OK` if the Claude Code CLI is on PATH; `WARN` (not fail) if missing — the embedded chat pane needs it but the audit pipeline can run without. |
| **auth** | Reads `~/.config/speca/auth.json`, decodes the access-token JWT, and asserts the scope `user:sessions:claude_code` is present. Without that scope subscription quota is not billed correctly. See [SPEC §4.5.2](../docs/SPECA_CLI_SPEC.md#452-the-magic-scope-usersessionsclaude_code). |

Exit code is `0` if every required check passes, `1` otherwise.

### `speca auth login`

Two paths, picked automatically:

**1. Subscription auth (default, recommended).**

Opens the Claude Code OAuth authorize URL in your browser. After signing in on `claude.ai`, the page shows an authorization code. Copy the entire string and paste it back into the CLI prompt. Three formats are accepted by the parser (`parseCallbackInput`):

- the raw `code#state` hash form (what the page literally displays)
- the full URL with the hash
- a `code=...&state=...` query string

```text
$ speca auth login
We've opened the following URL in your browser:

  https://claude.ai/oauth/authorize?client_id=...&scope=user:sessions:claude_code...

After signing in, claude.ai will redirect you to a page that shows
a code. Paste the entire string below.

> Paste code: <paste here>

[OK] Signed in via Claude Code subscription.
     Account: alice@example.com
     Scope:   org:create_api_key user:profile user:inference
              user:sessions:claude_code user:mcp_servers user:file_upload
```

> **Why paste-code, not loopback?** Anthropic's authorize endpoint hard-codes `redirect_uri = https://platform.claude.com/oauth/code/callback`; `http://localhost:<port>` is rejected. See [SPEC §4.5.1](../docs/SPECA_CLI_SPEC.md#451-the-flow-is-paste-code-not-loopback) and pitfall #4 in [§9.3](../docs/SPECA_CLI_SPEC.md#93-pitfalls-drawn-from-the-references-above).

**2. API-key fallback.** Useful for CI or for users without a Claude Code subscription:

```bash
speca auth login --api-key sk-ant-api03-...
# or non-interactively:
ANTHROPIC_API_KEY=sk-ant-... speca auth login --api-key
```

Tokens are written to `~/.config/speca/auth.json` with `chmod 0o600` via an atomic tmp+rename. The structure follows [SPEC §4.5.4](../docs/SPECA_CLI_SPEC.md#454-token-storage-layout).

### `speca auth status`

```text
$ speca auth status
[OK] Authenticated via Claude Code subscription
     Method:  oauth (user:sessions:claude_code)
     Expires: 2026-05-10T07:14:23Z (in 6d 21h)
```

If the token is missing or the `user:sessions:claude_code` scope is absent, exit code is `1` and a hint to run `speca auth login` is printed.

### `speca init`

Interactive wizard (powered by `@clack/prompts`) that builds the JSON files SPECA needs. Non-interactive mode is supported for CI:

```bash
speca init \
  --target-repo https://github.com/sigp/lighthouse \
  --target-language Rust \
  --target-layer consensus \
  --rubric default \
  --output-dir ./outputs \
  --non-interactive --yes
```

Outputs:

- `outputs/TARGET_INFO.json` — pins the repo + commit + language + layer ([SPEC §7.3](../docs/SPECA_CLI_SPEC.md#73-target_infojson-wizard)).
- `outputs/BUG_BOUNTY_SCOPE.json` — trust model + severity rubric + scope rules ([SPEC §7.2](../docs/SPECA_CLI_SPEC.md#72-bug_bounty_scopejson-wizard)). Default rubric snapshots ethereum.org/bug-bounty. Validated against the Pydantic-derived JSON Schema (`scripts/export_schemas.py`).

`speca init` does **not** run the pipeline. After it finishes, run `speca run` to drive Phase 01a → 04.

### `speca run`

Live dashboard for `scripts/run_phase.py`. The CLI spawns the Python orchestrator with `--json`, parses its NDJSON event stream, and renders an Ink dashboard with phase rows, worker badges, log pane, and budget gauge.

```bash
speca run --phase 01a                            # single phase
speca run --target 04 --workers 4                # full chain to phase 04
speca run --phase 01b --force                    # ignore resume state
speca run --target 04 --no-tui                   # CI / pipe-friendly text mode
speca run --target 04 --json | jq -c '.'         # NDJSON for downstream tools
```

Keybindings inside the dashboard (defaults — override via `~/.config/speca/config.toml`):

- `↑` / `↓` — move phase selection
- `Enter` — toggle expanded detail
- `s` — graceful stop (SIGTERM to the orchestrator)
- `f` — force-kill (SIGKILL after 5s grace)
- `l` — toggle log pane
- `q` / `Ctrl-C` — exit

### `speca browse`

Severity-coloured table over Phase 03/04 PARTIAL JSON files. Default glob is `outputs/04_PARTIAL_*.json`.

```bash
speca browse                                     # default glob
speca browse "outputs/04_PARTIAL_*.json"         # explicit glob
speca browse --severity Critical
speca browse --filter "severity:High AND verdict:CONFIRMED_*"
speca browse --no-tui                            # plain-text dump
speca browse --json                              # NDJSON per finding
```

Filter DSL (full grammar in `speca browse --help`):

```
severity:Critical              exact severity match (case-insensitive)
severity:Critical,High         comma-separated OR
verdict:CONFIRMED_*            wildcard suffix
prop:PROP-6a4*                 wildcard match against property_id
repo:lighthouse                substring match against source file path
text:reentrancy                substring search in summary/proof/attack/notes
severity:High AND verdict:CONFIRMED_*   explicit AND
NOT verdict:DISPUTED_FP        negation
(severity:High OR severity:Critical) AND prop:PROP-6a4*  parens
```

Keybindings: `↑/↓` (or `j/k`) move, `Enter` expand, `c` code peek, `f` filter, `/` text search, `s` cycle sort, `r` reload, `q` quit.

### `speca ask`

Chat with Claude about a specific finding. Spawns `claude --output-format stream-json --resume <session>` and pipes the question via stdin (Windows `cmd.exe` mangling is avoided via `--input-format text`). The finding is injected as a `<system-context>` block on the first turn (capped at 50 KB; smart-truncation by `code_path → proof_trace → attack_scenario → summary` priority).

```bash
speca ask --from outputs/04_PARTIAL_*.json PROP-abc-001
speca ask --session 9f1c2e0a-...                 # resume an existing session
echo "Why is this a vulnerability?" | speca ask --no-tui --from finding.json
```

Session id is persisted to `<projectRoot>/.speca/session.json` so subsequent `speca ask` calls continue the same conversation.

## Typical workflow

A first-run user goes through five steps.

### 1. Install Node 20+ and run the doctor

```bash
node --version          # must be >= v20
npx speca-cli@latest doctor
```

You should see:

```text
[OK] node     v20.18.1
[OK] uv       uv 0.4.20
[OK] git      git version 2.43.0
[OK] claude   2.1.87
[WARN] auth     not logged in
       → Run `speca auth login` to enable Claude Code subscription mode
```

Anything `[FAIL]` is printed with a one-line install hint. Install it and re-run.

### 2. Sign in

```bash
speca auth login
```

Pick subscription (default) — the OAuth flow opens your browser, you paste the code back, done. Verify with:

```bash
speca auth status
```

### 3. Initialise a project

```bash
mkdir my-audit && cd my-audit
speca init
```

Walk through the wizard. When it ends you'll have:

```text
my-audit/
├── outputs/
│   ├── TARGET_INFO.json
│   └── BUG_BOUNTY_SCOPE.json
└── .speca/
    └── session.json
```

### 4. Run the pipeline

```bash
speca run --target 04 --workers 4
```

The Ink dashboard shows live phase rows, worker badges, log tail, and budget gauge. Use `[s]` to graceful-stop, `[f]` to force-kill, `[l]` to toggle the log pane.

### 5. Browse findings and ask Claude

```bash
speca browse outputs/04_PARTIAL_*.json
# pick a finding, press 'c' to code-peek
# then in another shell or after exiting:
speca ask --from outputs/04_PARTIAL_W0B0_*.json PROP-vault-inv-001
```

## Testing

Manual test recipes (smoke tests + unit tests + TUI 目視) live in [`cli/TESTING.md`](TESTING.md). Minimum smoke:

```bash
cd cli
npm install
npm run build
npm test                                # 256/256 vitest
node dist/cli.js doctor                 # environment health
node dist/cli.js run --phase 01b --json # NDJSON pass-through
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `doctor` reports `node FAIL — v18.x (need >= v20)` | Install Node 20 LTS or newer from https://nodejs.org/. |
| `doctor` reports `uv not found on PATH` | `pip install uv` or follow https://docs.astral.sh/uv/getting-started/installation/. On Windows reopen the terminal so `PATH` is refreshed. |
| `doctor` reports `claude WARN — not found on PATH` | `npm install -g @anthropic-ai/claude-code`. Optional for the audit pipeline; required for `speca ask`. |
| `auth login` opens the browser but you land on the wrong account | Open the URL in a private window, sign in to the correct Claude account, paste the code back. |
| `auth status` prints `scope missing user:sessions:claude_code` | The stored token was issued by a different OAuth client. Re-run `speca auth login` to force a fresh round trip. |
| Windows: a hand-edited JSON file is parsed as garbage | Save as UTF-8 without BOM, LF line endings. `speca init` itself writes LF; re-running it overwrites cleanly. |
| Windows: `outputs\TARGET_INFO.json` not found from WSL2 | Run `speca` consistently from one shell. |
| `npx` install fails on Windows with `EPERM` while extracting `node-pty` | `node-pty` is an `optionalDependency`; the warning is harmless. Run the terminal as administrator if you need the chat pane locally. See [SPEC §9.3 pitfall #2](../docs/SPECA_CLI_SPEC.md#93-pitfalls-drawn-from-the-references-above). |

If you are stuck, attach the output of `speca doctor` and `speca version` to a [new issue](https://github.com/NyxFoundation/speca/issues/new).

## Architecture

`speca-cli` is a thin Node.js + Ink layer over the existing Python orchestrator. It does **not** re-implement audit logic; every phase is still executed by `uv run python3 scripts/run_phase.py …` under the hood.

| Layer | Responsibility | Lib |
|---|---|---|
| TUI rendering | React-style components, screen routing, keybindings | [Ink 7](https://github.com/vadimdemedes/ink) |
| Argument parsing | Subcommand routing, `--flag` handling | [meow](https://github.com/sindresorhus/meow) |
| Wizard prompts | Multi-step `init` form | [@clack/prompts](https://github.com/bombshell-dev/clack) |
| Subprocess | Spawning the orchestrator and the embedded `claude` chat session | `child_process.spawn` (orchestrator + claude); [`node-pty`](https://github.com/microsoft/node-pty) is `optionalDependencies` |
| Live log tail | Watching `outputs/logs/*.jsonl` | [chokidar](https://github.com/paulmillr/chokidar) |
| Schema validation | Runtime validation of stream-JSON events and config files | [zod](https://github.com/colinhacks/zod), [ajv](https://ajv.js.org/) |
| OAuth | Vendored from `ex-machina-co/opencode-anthropic-auth` (MIT), see [SPEC §4.5](../docs/SPECA_CLI_SPEC.md#45-concrete-oauth-implementation-vendored) | (vendored) |
| Theme / config | TOML config loader for theme + keybind overrides | [smol-toml](https://github.com/squirrelchat/smol-toml) |
| Syntax highlighting | Code peek in `speca browse` | [cli-highlight](https://github.com/felixfbecker/cli-highlight) |

Full component diagram and the rejected alternatives (Bubble Tea, Crush, OpenTUI, blessed) are in [SPEC §8](../docs/SPECA_CLI_SPEC.md#8-architecture).

## Vendoring & licenses

`speca-cli` is MIT. A handful of files under `src/auth/` are **vendored verbatim** from `ex-machina-co/opencode-anthropic-auth` (MIT) and `sst/opencode` (MIT, pattern only) and carry the original licence header. Per-file provenance, the pinned upstream commit, and a refresh procedure are in [`cli/docs/VENDOR.md`](docs/VENDOR.md). The full reuse table also lives in [SPEC §9.2](../docs/SPECA_CLI_SPEC.md#92-file-level-reuse-map-what-we-actually-lift).

All other dependencies (`ink`, `@clack/prompts`, `chokidar`, `zod`, `ajv`, `node-pty`, `meow`, `which`, `smol-toml`, `cli-highlight`, `execa`, `fast-glob`) are regular npm packages, not vendored.

## Contributing

We welcome PRs against this folder.

### Branch naming

- `feat/cli-<scope>` — new features.
- `fix/cli-<scope>` — bug fixes.
- `docs/cli-<scope>` — docs-only changes.

### Local development

```bash
cd cli
npm install
npm run dev -- doctor       # run from source via tsx
npm run dev -- version

npm run build               # compile to dist/ (sync-schemas + tsc)
node dist/cli.js doctor     # run the built bundle

npm run typecheck
npm run test                # vitest run
npm run test:watch
```

### CI matrix

`macos-14`, `ubuntu-22.04`, `windows-2022` × Node 20 / 22. Every PR must keep all 6 cells green. The test suite is `vitest` plus `ink-testing-library` snapshots.

## Polish & customization

`speca-cli` ships a polish layer used by every subcommand — themes, keybind overrides, a generic error modal, and a non-TUI / JSON output mode.

### Themes

Three themes ship in v1: `dark` (default), `light`, and `solarized`. Set the active theme in `~/.config/speca/config.toml` (Windows: `%APPDATA%\speca\config.toml`):

```toml
theme = "dark"   # or "light" / "solarized"
```

Unknown theme names fall back to `dark` silently — a typo will not crash the CLI. The theme controls the colour palette only; layout is identical across themes so you can switch mid-audit without re-learning the screens.

### Keybind overrides

Every interactive surface routes input through abstract action names (`exit`, `toggle-log`, `filter-mode`, ...). Override the default bindings per action in `config.toml`:

```toml
[keybinds]
exit         = ["q", "ctrl+c"]
toggle-log   = ["l"]
filter-mode  = ["/"]
focus-chat   = ["i"]
```

Each value is a list of key descriptors. A descriptor is one of:

- a single character (`"q"`, `"/"`),
- an Ink modifier name (`"escape"`, `"return"`, `"upArrow"`, `"pageDown"`, …),
- a `ctrl+<letter>` chord (`"ctrl+c"`, `"ctrl+l"`).

Actions absent from the config keep their defaults; an empty list disables the override and falls back to the default. The default map is the source of truth — see `cli/src/lib/keybinds/defaults.ts`.

> **v1.0 note.** `speca run` consumes the keybind layer end-to-end. `speca browse` and `speca ask` use the theme but still bind their `useInput` directly because their dual-mode (edit vs read) input loops are awkward to express through an abstract action layer; that migration is queued for v1.1.

### `--no-tui` / `--json`

Two flags govern non-interactive output:

- `--no-tui` forces line-by-line plain-text output. Implied automatically when stdout is not a TTY (CI, `tee`, pipes). Override the auto-detection with `SPECA_FORCE_TUI=1` if you really want to keep the TUI under a pipe.
- `--json` emits one JSON object per line (NDJSON) on stdout. Each record carries at minimum `{ "type": "...", "ts": "<ISO8601>" }`; per-subcommand schemas are documented in `speca <cmd> --help`.

Examples:

```bash
# CI-friendly headless run
speca run --target 04 --no-tui

# NDJSON for downstream dashboards / log shipping
speca run --target 04 --json | jq -c 'select(.type == "phase-completed")'
```

### Demos

asciinema recordings of the three flagship flows (`doctor`, `init`, `browse`) will be added at the URLs below in a v1.0.x patch. Recording instructions, scenario list, and re-recording policy are in [`cli/asciinema/README.md`](asciinema/README.md).

- `speca doctor` — _coming in v1.0.x_
- `speca init` — _coming in v1.0.x_
- `speca browse` — _coming in v1.0.x_

## License

MIT. See [`LICENSE`](../LICENSE) at the repository root.

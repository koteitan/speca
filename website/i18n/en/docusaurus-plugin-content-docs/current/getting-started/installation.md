---
sidebar_position: 1
---

# Installation

There are two ways to install SPECA: a global CLI install (recommended for end users) and a from-source install (for contributors and reproducibility runs).

## Prerequisites

- **Node.js 20 or later** — runs the CLI front-end.
- **Python 3.11 or later** with [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — runs the orchestrator.
- **git** — used to clone target repositories during audits.
- **Claude Code CLI** (`@anthropic-ai/claude-code`) — installed automatically as a peer of `speca-cli`. Either sign in via `claude` or set `ANTHROPIC_API_KEY`.

## Option A — global CLI (recommended)

```bash
# One-shot environment check (no install)
npx speca-cli@latest doctor

# Persistent install
npm install -g speca-cli
speca doctor
```

After this, the `speca` command is on your PATH. You only need source code if you want to reproduce paper benchmarks or contribute changes.

## Option B — from source

```bash
git clone https://github.com/NyxFoundation/speca.git
cd speca

# Install Python deps for the orchestrator
uv sync

# Build the CLI front-end
cd cli && npm install && npm run build && cd ..

# Either link the built binary onto your PATH …
npm link --prefix cli

# … or invoke the local build directly
node cli/dist/cli.js doctor
```

The rest of the docs use `speca <subcommand>`. If you are using Option B without `npm link`, substitute `node cli/dist/cli.js <subcommand>`.

## Register MCP servers

Phases 01a (Spec Discovery) and 02c (Code Pre-resolution) call out to MCP servers. Register them once:

```bash
bash scripts/setup_mcp.sh           # source install — registers fetch + tree_sitter
bash scripts/setup_mcp.sh --verify  # confirms each server is reachable
```

The CLI install bundles equivalent registration logic; `speca doctor` will tell you if a server is missing.

## Verify the environment

```bash
speca doctor
```

Expected output:

```
[ok] Node.js 20.x
[ok] Python 3.11 (uv)
[ok] Claude Code CLI authenticated
[ok] MCP servers: fetch, tree_sitter
```

If any line is `[err]`, follow the message — `speca doctor` prints the exact remediation step for each failure.

## Next step

→ [Quickstart](./quickstart.md) — first audit in five minutes.

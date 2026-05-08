---
sidebar_position: 1
---

# Installation

Steps to set up an environment for running SPECA.

## Prerequisites

- Node.js 20 or later
- Python 3.11 or later, with the `uv` package manager
- git
- Claude Code CLI (`@anthropic-ai/claude-code`)
- An Anthropic API key (set as the `ANTHROPIC_API_KEY` environment variable, or sign in via Claude Code)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/NyxFoundation/speca.git
cd speca
```

### 2. Install the Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
```

### 3. Set up Python dependencies

```bash
uv sync
```

### 4. Register MCP servers

```bash
bash scripts/setup_mcp.sh
bash scripts/setup_mcp.sh --verify
```

The `--verify` command confirms that each MCP server (tree_sitter / filesystem / fetch) has been registered correctly.

## Environment verification

```bash
speca doctor
```

Confirms that the system is ready to use.

#!/usr/bin/env bash
set -euo pipefail

# Always run from the repository root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Remove the nested git metadata so this repo can be vendored elsewhere
rm -rf security-agent/.git

# Synchronise prompts into Codex CLI directory without nuking the directory itself
DEST_DIR="${HOME}/.codex/prompts"
mkdir -p "$DEST_DIR"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "$REPO_ROOT/security-agent/prompts/" "$DEST_DIR/"
else
  cp -a "$REPO_ROOT/security-agent/prompts/." "$DEST_DIR/"
fi

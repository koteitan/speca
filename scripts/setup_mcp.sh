#!/usr/bin/env bash
set -euo pipefail

echo "Verifying and setting up MCP servers..."

# =============================================================================
# MCP Server Configuration
# =============================================================================
# Each MCP server is defined with its name and corresponding command.
#
# Current servers:
#   - tree_sitter: Code parsing and symbol extraction (used by Phase 03, subgraph-extractor)
#   - serena: Development workflow automation
#   - semgrep: Static analysis and pattern matching for security vulnerabilities
#   - filesystem: File system access for reading/writing audit artifacts
#   - fetch: HTTP requests for fetching external specifications (used by Phase 01a)
#   - github: GitHub API access for issue tracking and repository analysis
# =============================================================================

SERVERS=(
  "tree_sitter"
  "serena"
  "semgrep"
  "filesystem"
  "fetch"
  "github"
)

COMMANDS=(
  "uvx mcp-server-tree-sitter"
  "uvx --from git+https://github.com/oraios/serena serena start-mcp-server"
  "uvx semgrep-mcp"
  "npx -y @modelcontextprotocol/server-filesystem ."
  "uvx mcp-server-fetch"
  "npx -y @modelcontextprotocol/server-github"
)

# Optional: Server descriptions for logging
DESCRIPTIONS=(
  "Code parsing and symbol extraction"
  "Development workflow automation"
  "Static analysis for security vulnerabilities"
  "File system access for audit artifacts"
  "HTTP fetch for external specifications"
  "GitHub API for repository analysis"
)

echo "Registering ${#SERVERS[@]} MCP servers..."
echo

for i in "${!SERVERS[@]}"; do
  SERVER_NAME="${SERVERS[$i]}"
  SERVER_COMMAND="${COMMANDS[$i]}"
  SERVER_DESC="${DESCRIPTIONS[$i]}"

  echo "[$((i+1))/${#SERVERS[@]}] ${SERVER_NAME}: ${SERVER_DESC}"

  if claude mcp list 2>/dev/null | grep -q "${SERVER_NAME}"; then
    echo "  ✓ Already registered."
    continue
  fi

  echo "  → Registering..."
  if ! ADD_OUTPUT=$(claude mcp add --scope project --transport stdio "${SERVER_NAME}" -- ${SERVER_COMMAND} 2>&1); then
    if echo "${ADD_OUTPUT}" | grep -qi "already exists"; then
      echo "  ✓ Already exists; skipping."
    else
      echo "  ✗ Error: ${ADD_OUTPUT}"
      exit 1
    fi
  else
    echo "  ✓ Registered successfully."
  fi
done

echo
echo "=========================================="
echo "Final MCP server list:"
echo "=========================================="
claude mcp list

if [ -f ".mcp.json" ]; then
  echo
  echo "=========================================="
  echo "Contents of .mcp.json:"
  echo "=========================================="
  cat .mcp.json
else
  echo
  echo ".mcp.json not found. MCP servers might be registered at user scope."
fi

echo
echo "MCP setup complete."

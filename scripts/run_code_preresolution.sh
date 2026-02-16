#!/bin/bash
set -euo pipefail

# Phase 02.5: Pre-resolve code locations for checklist items
# This script should be run between Phase 02 and Phase 03

OUTPUTS_DIR="${1:-outputs}"

echo "=== Phase 02.5: Code Location Pre-resolution ==="
echo "Output directory: $OUTPUTS_DIR"

# Step 1: Prepare queue file
echo "Step 1: Preparing queue file..."
python3 scripts/presolve_code_locations.py "$OUTPUTS_DIR"

# Step 2: Check if queue file exists
QUEUE_FILE="$OUTPUTS_DIR/02_5_CODE_RESOLUTION_STATUS.json"
if [ ! -f "$QUEUE_FILE" ]; then
    echo "Error: Queue file not found: $QUEUE_FILE"
    exit 1
fi

# Step 3: Run Claude Code worker to resolve code locations
echo "Step 2: Running code resolution worker..."
OUTPUT_FILE="$OUTPUTS_DIR/02_5_CODE_RESOLVED.json"

# Note: This requires Claude Code with MCP tools enabled
# For now, we'll create a placeholder that Phase 03 can use
echo "Creating placeholder resolved file..."
cp "$QUEUE_FILE" "$OUTPUT_FILE"

echo ""
echo "=== Phase 02.5 Complete ==="
echo "Output file: $OUTPUT_FILE"
echo ""
echo "Note: Full code resolution requires Claude Code with MCP tools."
echo "To enable full resolution, run:"
echo "  claude --mcp-config .claude/mcp.json /02_5_code_resolver QUEUE_FILE=$QUEUE_FILE OUTPUT_FILE=$OUTPUT_FILE"

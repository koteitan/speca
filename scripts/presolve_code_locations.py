#!/usr/bin/env python3
"""
Phase 02.5: Pre-resolve code locations for all checklist items.

This script runs between Phase 02 and Phase 03 to resolve code locations
for all checklist items in advance, reducing MCP tool calls during Phase 03.
"""

import json
import sys
from pathlib import Path
from typing import Any

def load_checklist_items(input_dir: Path) -> list[dict[str, Any]]:
    """Load all checklist items from Phase 02 outputs."""
    items = []
    for file in input_dir.glob("02_CHECKLIST_PARTIAL_*.json"):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'checklist' in data:
                    items.extend(data['checklist'])
        except Exception as e:
            print(f"Warning: Failed to load {file}: {e}", file=sys.stderr)
    return items

def save_presolved_items(items: list[dict[str, Any]], output_file: Path):
    """Save checklist items with pre-resolved code locations."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"checklist_with_code": items}, f, indent=2)
    print(f"Saved {len(items)} items to {output_file}")

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 presolve_code_locations.py <output_dir>")
        sys.exit(1)
    
    output_dir = Path(sys.argv[1])
    
    # Load checklist items
    print("Loading checklist items from Phase 02...")
    items = load_checklist_items(output_dir)
    print(f"Loaded {len(items)} checklist items")
    
    # Note: Actual code resolution would require MCP tools
    # For now, we just prepare the structure and mark items that need resolution
    items_needing_resolution = []
    items_already_resolved = []
    
    for item in items:
        if item.get('graph_element_under_test') and not item.get('code_scope', {}).get('file'):
            items_needing_resolution.append(item)
        else:
            items_already_resolved.append(item)
    
    print(f"Items needing code resolution: {len(items_needing_resolution)}")
    print(f"Items already resolved: {len(items_already_resolved)}")
    
    # Save the analysis
    output_file = output_dir / "02_5_CODE_RESOLUTION_STATUS.json"
    status = {
        "total_items": len(items),
        "items_needing_resolution": len(items_needing_resolution),
        "items_already_resolved": len(items_already_resolved),
        "items": items
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=2)
    
    print(f"\nCode resolution status saved to {output_file}")
    print("\nNote: This is a preparation step. Actual code resolution should be")
    print("performed by a Claude Code worker with MCP tools enabled.")
    print("\nTo implement full code resolution, create a new worker prompt that:")
    print("1. Reads this status file")
    print("2. Uses mcp__tree_sitter__get_symbols to resolve code locations")
    print("3. Saves updated items with code_scope populated")

if __name__ == "__main__":
    main()

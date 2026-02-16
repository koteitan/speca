#!/usr/bin/env python3
"""
DEPRECATED: This script is replaced by Phase 02c orchestrated workflow.

Legacy script for enriching checklist items with pre-resolved code locations.
This was used before Phase 02c was integrated into the orchestrated pipeline.

New workflow (Phase 02c):
    - Uses .github/workflows/02c-enrich-code.yml
    - Requires target_repo, target_ref_type, audit_scope
    - Creates new branch with outputs/02c_TARGET_INFO.json
    - Runs via: uv run python3 scripts/run_phase.py --phase 02c
    - Uses prompts/02c_worker.md

Phase 03 then reads 02c_TARGET_INFO.json to auto-clone the same target.

This script is kept for reference but should not be used in production.
Use the Phase 02c workflow instead.

Old usage:
    python3 scripts/enrich_checklist_with_code.py outputs/
"""

import json
import sys
from pathlib import Path
from typing import Any

from orchestrator.schemas import ChecklistItem, CodeScope, Phase02Partial


def load_checklist_items(output_dir: Path) -> list[ChecklistItem]:
    """Load all checklist items from Phase 02 outputs."""
    items = []
    for file in sorted(output_dir.glob("02_CHECKLIST_PARTIAL_*.json")):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                partial = Phase02Partial(**data)
                items.extend(partial.checklist)
        except Exception as e:
            print(f"Warning: Failed to load {file}: {e}", file=sys.stderr)
    return items


def save_enriched_items(items: list[ChecklistItem], output_file: Path):
    """Save enriched checklist items."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to dict for JSON serialization
    items_dict = [item.model_dump(exclude_none=True) for item in items]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"checklist": items_dict}, f, indent=2)
    
    print(f"Saved {len(items)} enriched items to {output_file}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 enrich_checklist_with_code.py <output_dir>")
        sys.exit(1)
    
    output_dir = Path(sys.argv[1])
    
    # Load checklist items
    print("Loading checklist items from Phase 02...")
    items = load_checklist_items(output_dir)
    print(f"Loaded {len(items)} checklist items")
    
    # Analyze current state
    items_with_code = sum(1 for item in items if item.code_scope.file)
    items_needing_resolution = sum(
        1 for item in items 
        if item.graph_element_under_test and not item.code_scope.file
    )
    
    print(f"Items with code_scope already populated: {items_with_code}")
    print(f"Items needing code resolution: {items_needing_resolution}")
    
    # Mark items needing resolution
    for item in items:
        if item.graph_element_under_test and not item.code_scope.file:
            item.code_scope.resolution_status = "pending"
    
    # Save enriched items (for now, just mark status)
    output_file = output_dir / "02_CHECKLIST_ENRICHED.json"
    save_enriched_items(items, output_file)
    
    print(f"\nEnriched checklist saved to {output_file}")
    print("\nNote: To populate code_scope with actual locations, run:")
    print("  claude --mcp-config .claude/mcp.json /02_enrich_code \\")
    print(f"    INPUT_FILE={output_file} \\")
    print(f"    OUTPUT_FILE={output_dir}/02_CHECKLIST_WITH_CODE.json")


if __name__ == "__main__":
    main()

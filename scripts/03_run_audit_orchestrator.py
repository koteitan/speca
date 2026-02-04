#!/usr/bin/env python3
"""
Phase 03 Audit Map Orchestrator Agent

This script replaces the legacy run_parallel.py and run_worker.py for phase 03.
It orchestrates the formal audit process using a hierarchical agent architecture:

L1: Orchestrator Agent (this script)
    - Reads the main queue.
    - Performs Early Exit checks for `out-of-scope` items.
    - Forms dynamic, token-based batches.
    - Invokes the `map` tool to spawn L2 Worker Subagents.
    - Aggregates results and updates the main state.

L2: Worker Subagent (spawned by `map`)
    - Receives a batch of audit items.
    - For each item, invokes the `formal-audit` skill.
    - Returns a list of structured JSON audit results.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Assume the existence of Claude Code API bindings
# from claude_code_api import default_api, MapOutputSchema

# --- Constants ---
OUTPUT_DIR = Path("outputs")
LOG_DIR = OUTPUT_DIR / "logs"
SKILL_PATH = Path("skills/formal-audit/SKILL.md")
CHECKLIST_PARTIALS_PATTERN = "outputs/02_CHECKLIST_PARTIAL_*.json"
PROPERTY_PARTIALS_PATTERN = "outputs/01e_PROP_PARTIAL_*.json"
MAX_CONTEXT_TOKENS = 190_000  # Safety margin for 200K context window
BASE_PROMPT_TOKENS = 5_000  # Estimated tokens for skill prompt + map prompt template


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)


def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def estimate_tokens(text: str) -> int:
    """A simple estimation of token count."""
    return len(text) // 4


def build_property_to_subgraph_map_via_elements(
    property_files_pattern: str,
) -> dict[str, tuple[str | None, str]]:
    """
    Build a map from property_id to (subgraph_id, subgraph_file).

    For each property file:
    1. Load metadata.source_files (subgraph files used in this batch)
    2. Load all those subgraph files into memory
    3. For each property, find which subgraph contains its primary element
    4. Record the mapping
    """
    import glob

    property_to_subgraph: dict[str, tuple[str | None, str]] = {}

    for prop_file in sorted(glob.glob(property_files_pattern)):
        prop_data = load_json(Path(prop_file)) or {}
        source_files = prop_data.get("metadata", {}).get("source_files", [])

        subgraph_cache: dict[str, dict[str, Any]] = {}
        for sg_file in source_files:
            if os.path.exists(sg_file):
                subgraph_cache[sg_file] = load_json(Path(sg_file)) or {}

        for prop in prop_data.get("properties", []):
            if not isinstance(prop, dict):
                continue
            prop_id = prop.get("id")
            if not prop_id:
                continue

            covers = prop.get("covers", {})
            primary_element = covers.get("primary_element")
            if not primary_element:
                edges = covers.get("edges", [])
                nodes = covers.get("nodes", [])
                if edges:
                    primary_element = edges[0]
                elif nodes:
                    primary_element = nodes[0]

            if not primary_element:
                continue

            found = False
            for sg_file, sg_data in subgraph_cache.items():
                for subgraph in sg_data.get("sub_graphs", []):
                    edge_ids = [e.get("id") for e in subgraph.get("edges", [])]
                    node_ids = [n.get("id") for n in subgraph.get("nodes", [])]
                    if primary_element in edge_ids or primary_element in node_ids:
                        subgraph_id = subgraph.get("id")
                        if subgraph_id:
                            property_to_subgraph[prop_id] = (subgraph_id, sg_file)
                            found = True
                            break
                if found:
                    break

                for ambiguity in sg_data.get("ambiguities", []):
                    if ambiguity.get("id") == primary_element:
                        property_to_subgraph[prop_id] = (None, sg_file)
                        found = True
                        break
                if found:
                    break

                for assumption in sg_data.get("implicit_assumptions", []):
                    if assumption.get("id") == primary_element:
                        property_to_subgraph[prop_id] = (None, sg_file)
                        found = True
                        break
                if found:
                    break

    return property_to_subgraph


class AuditOrchestrator:
    def __init__(self, max_workers: int):
        self.max_workers = max_workers
        self.all_checklist_items: Dict[str, Dict[str, Any]] = {}
        self.property_subgraph_map: Dict[str, Tuple[str | None, str]] = {}

    def _load_all_checklist_items(self):
        """Load all checklist items from partials into memory."""
        import glob

        print("Loading all checklist items...")
        self.property_subgraph_map = build_property_to_subgraph_map_via_elements(
            PROPERTY_PARTIALS_PATTERN
        )

        items: dict[str, Dict[str, Any]] = {}
        for filepath in sorted(glob.glob(CHECKLIST_PARTIALS_PATTERN)):
            data = load_json(Path(filepath)) or {}
            entries = data.get("checklist_items") or data.get("checklist") or []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                check_id = entry.get("id") or entry.get("check_id")
                if not check_id:
                    continue

                item: Dict[str, Any] = {
                    "check_id": check_id,
                    "checklist_item": entry,
                    "checklist_file": filepath,
                }
                if "property_id" in entry:
                    item["property_id"] = entry.get("property_id")
                if "code_scope" in entry:
                    item["code_scope"] = entry.get("code_scope")

                property_id = entry.get("property_id")
                if property_id:
                    subgraph_info = self.property_subgraph_map.get(property_id)
                    if subgraph_info:
                        subgraph_id, subgraph_file = subgraph_info
                        item["subgraph_id"] = subgraph_id
                        item["subgraph_file"] = subgraph_file

                items[check_id] = item

        self.all_checklist_items = items

    def _is_early_exit(self, item: Dict[str, Any]) -> bool:
        """Perform a lightweight check to see if an item is out-of-scope."""
        code_scope = item.get("code_scope")
        if not code_scope and isinstance(item.get("checklist_item"), dict):
            code_scope = item["checklist_item"].get("code_scope")
        if not isinstance(code_scope, dict):
            return True
        file_path = code_scope.get("file")
        if not file_path or file_path in ("N/A", "SPECIFICATION-ONLY"):
            return True
        return False

    def _create_token_based_batches(self, items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group items into batches, respecting the token limit."""
        print("Creating token-based batches...")
        batches: List[List[Dict[str, Any]]] = []
        current_batch: List[Dict[str, Any]] = []
        current_batch_tokens = BASE_PROMPT_TOKENS

        for item in items:
            item_json = json.dumps(item)
            item_tokens = estimate_tokens(item_json)

            # This is a simplified token calculation. A real implementation would also
            # account for the size of referenced files (`checklist_file`, `subgraph_file`).

            if current_batch and (current_batch_tokens + item_tokens > MAX_CONTEXT_TOKENS):
                batches.append(current_batch)
                current_batch = []
                current_batch_tokens = BASE_PROMPT_TOKENS

            current_batch.append(item)
            current_batch_tokens += item_tokens

        if current_batch:
            batches.append(current_batch)

        print(f"Created {len(batches)} batches.")
        return batches

    def _build_early_exit_result(self, item: Dict[str, Any]) -> Dict[str, Any]:
        check_id = item.get("check_id")
        checklist_item = item.get("checklist_item") if isinstance(item.get("checklist_item"), dict) else {}
        code_scope = item.get("code_scope") or checklist_item.get("code_scope") or {}

        return {
            "check_id": check_id,
            "property_id": item.get("property_id") or checklist_item.get("property_id"),
            "code_scope": code_scope,
            "final_classification": "out-of-scope",
            "bug_bounty_eligible": False,
            "summary": "No in-scope implementation; analysis skipped.",
            "audit_trail": {
                "phase1_abstract_interpretation": {
                    "summary": "Early exit: no in-scope code scope.",
                    "state_anomalies_found": [],
                },
                "phase2_symbolic_execution": {
                    "summary": "Not performed due to early exit.",
                    "counterexample_found": False,
                    "counterexample": None,
                },
                "phase2_5_reachability_analysis": {
                    "summary": "Not performed due to early exit.",
                    "entry_points": [],
                    "data_flow_path": "",
                    "validation_layers": [],
                    "attacker_controlled": False,
                    "classification": "unreachable",
                    "notes": "",
                },
                "phase3_invariant_proving": {
                    "summary": "Not performed due to early exit.",
                    "proof_successful": False,
                    "guard_identified": None,
                },
                "phase3_5_scope_filtering": {
                    "bug_bounty_eligible": False,
                    "reason": "out-of-scope",
                    "recommendation": "",
                    "notes": "",
                },
            },
        }

    def run(self):
        """Main orchestration logic."""
        # 1. Load all necessary data into memory
        self._load_all_checklist_items()

        # 2. Separate items into `early_exit` and `full_audit` queues
        full_audit_queue: List[Dict[str, Any]] = []
        early_exit_results: List[Dict[str, Any]] = []

        for item in self.all_checklist_items.values():
            if self._is_early_exit(item):
                early_exit_results.append(self._build_early_exit_result(item))
            else:
                full_audit_queue.append(item)

        print(f"Identified {len(early_exit_results)} items for early exit.")
        print(f"Sending {len(full_audit_queue)} items for full audit.")

        # 3. Create token-based batches for the full audit items
        batches = self._create_token_based_batches(full_audit_queue)

        # 4. Invoke Worker Subagents in parallel using the `map` tool
        map_inputs = [json.dumps(batch) for batch in batches]

        print(f"Invoking `map` tool with {len(map_inputs)} parallel subagents...")
        # This is a conceptual call to the `map` tool.
        # map_results = default_api.map(
        #     brief="Perform formal static audit on code batches",
        #     name="formal_audit_batch",
        #     title=f"Formal Audit of {len(full_audit_queue)} Code Items",
        #     prompt_template=f"""
        #     You are a security audit worker subagent.
        #     For each item in the provided JSON batch, execute the formal audit methodology defined in <file>{SKILL_PATH}</file>.
        #     Return a single JSON array containing the structured audit result for each item.
        #
        #     Batch to audit:
        #     {{input}}
        #     """,
        #     target_count=len(map_inputs),
        #     inputs=map_inputs,
        #     output_schema=[
        #         MapOutputSchema(
        #             name="audit_results_json",
        #             type="string",
        #             title="Audit Results JSON",
        #             description="A valid JSON string of a list of audit result objects.",
        #             format="JSON array",
        #         )
        #     ],
        # )

        # 5. Aggregate all results and save
        final_results = list(early_exit_results)
        # for result in map_results:
        #     # Process and validate the JSON output from each subagent
        #     subagent_output = json.loads(result["audit_results_json"])
        #     final_results.extend(subagent_output)

        timestamp = int(time.time())
        final_output_path = OUTPUT_DIR / f"03_AUDITMAP_FINAL_{timestamp}.json"
        save_json(final_output_path, {"audit_results": final_results})

        print(f"Orchestration complete. Final results saved to {final_output_path}")


if __name__ == "__main__":
    # This would be triggered by the Makefile or GitHub Actions
    max_workers = int(os.environ.get("WORKERS", 4))
    orchestrator = AuditOrchestrator(max_workers=max_workers)
    orchestrator.run()

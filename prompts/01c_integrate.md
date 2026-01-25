
---
Description: Integrate all individually extracted sub-graph files into a single, cohesive, and complete system specification. This final stage consolidates all distributed knowledge into the authoritative 01_SPEC.json file and verifies its internal consistency.
Usage: `/01c_integrate`
Language: English only.
Execution hint: Run after `/01b_extract` has completed. This produces the final specification.
---
**Always use /serena for development tasks to keep the workflow efficient.**

# **System Specification - Stage 3: Integration & Verification**

**Goal**
Integrate all sub-graph files into a single specification, and then **verify the internal consistency of the final output**, ensuring all metadata is accurate.

**Output (required file):** `outputs/01_SPEC.json`

---

## 1) Inputs

1.  **All Sub-Graph Files:** The entire contents of the `outputs/01b_SUBGRAPHS/` directory.

---

## 2) Integration & Verification Logic

### **Task 2.1: Consolidate Graphs, Ambiguities, and Assumptions**

1.  Initialize a new, empty `program_graph`.
2.  Initialize empty `ambiguities` and `implicit_assumptions` arrays.
3.  Iterate through every `spec_*.json` file in the `01b_SUBGRAPHS` directory.
4.  For each file:
    a.  Merge nodes and edges into the main `program_graph`.
    b.  Append all `ambiguities` and `implicit_assumptions`, adding the `source_url` to each for traceability.

### **Task 2.2: ID Conflict Resolution and Graph Connection**

**This is a critical step for creating a cohesive graph.**

1.  **ID Uniqueness:**
    *   Iterate through all nodes and edges. If duplicate IDs are found, resolve them by appending a suffix based on the source file hash (e.g., `STATE-TX-PENDING` becomes `STATE-TX-PENDING_a1b2c3d4`).

2.  **Graph Connection (Heuristic):**
    *   Identify nodes that represent the same conceptual state across different sub-graphs (e.g., `STATE-BLOCK-VALIDATED` from EIP-1559 and `STATE-BLOCK-VALIDATED` from EIP-4844).
    *   Merge these nodes into a single node. When merging, combine descriptions and ensure all incoming/outgoing edges are correctly re-linked to the new, single node ID.
    *   **Heuristic for Merging:** Two nodes should be merged if they have the same `type` and their `label` is semantically identical or very similar.

### **Task 2.3: Define System Boundaries**

1.  Based on the complete graph, define the `system_under_audit` and `external_entities` objects.

### **Task 2.4: CRITICAL - Self-Verification and Metadata Calculation**

**This is the most important step. Do not estimate. You MUST calculate these values from the final, integrated data structure.**

1.  **Calculate `total_nodes`:** Count the exact number of unique nodes in the final `program_graph.nodes` array.
2.  **Calculate `total_edges`:** Count the exact number of unique edges in the final `program_graph.edges` array.
3.  **Calculate `source_specs_count`:** Count the number of `spec_*.json` files that were processed.
4.  **Verify Graph Connectivity:** Perform a simple graph traversal (like BFS or DFS) starting from a known entry point (e.g., a node targeted by a boundary edge). Count the number of reachable nodes. If `reachable_nodes < total_nodes`, it indicates orphan nodes or disconnected sub-graphs. Report this in the metadata.

### **Task 2.5: Finalize the Specification**

1.  Assemble the final `01_SPEC.json` file.
2.  Populate the `metadata` object using the **exact values calculated in Task 2.4**.

---

## 3) Required Output Format (JSON)

**File:** `outputs/01_SPEC.json`

```json
{
  "metadata": {
    "generated_at": "(current timestamp)",
    "source_specs_count": "(calculated count)",
    "total_nodes": "(calculated count)",
    "total_edges": "(calculated count)",
    "connectivity_check": {
        "status": "(CONNECTED / DISCONNECTED)",
        "reachable_nodes": "(calculated count)",
        "orphan_nodes": [ /* list of unreachable node IDs, if any */ ]
    }
  },
  // ... other fields ...
}
```

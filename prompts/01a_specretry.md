
---
Description: Process pending sub-graphs from the 01_SPEC.json output. This prompt continues the work of 01_spec.md by generating detailed Program Graphs for items listed in `pending_sub_graphs`.
Usage: `/01a_specretry`
Example: `/01a_specretry`
Language: English only.
Execution hint: Run this after 01_spec when `pending_sub_graphs` is not empty. Repeat until all pending items are processed.
---
**Always use /serena for these development tasks to maximize token efficiency:**

# **System Specification Retry Prompt (Pending Sub-Graphs)**

**Goal**
Continue the specification work from `01_spec.md` by processing items listed in the `pending_sub_graphs` field of the existing output. Generate detailed Program Graphs for each pending item and merge them into the existing specification.

**Input (required file):** `outputs/01_SPEC.json`
**Output (same file, updated):** `outputs/01_SPEC.json`

---

## 0) Load Existing Specification

1.  **Read the existing output:** Load `outputs/01_SPEC.json` and parse it.
2.  **Extract pending items:** Identify all items in the `pending_sub_graphs` array.
3.  **Validate:** If `pending_sub_graphs` is empty or does not exist, report that there are no pending items and terminate.

---

## 1) Research & Context Gathering for Pending Items

For each item in `pending_sub_graphs`:

1.  **Specification Retrieval:** Use the `source` URL (if provided) to read the full specification for this item. If no URL is provided, use `web_search` to find authoritative documentation.
2.  **Recursive Link Following:** If the URL points to an index or overview page, follow relevant sub-links to gather complete information.
3.  **Context Integration:** Use the gathered information to inform your Program Graph modeling.

---

## 2) Core Task: Generate Sub-Graphs for Pending Items

For each item in `pending_sub_graphs`, generate a complete sub-graph:

### **Task 2.1: Define Sub-Graph Nodes**

*   **Definition:** A node represents a discrete, observable state or a specific computational action within this sub-process.
*   **Action:** For each state or action, create a node object with:
    *   `id`: A stable, unique identifier (e.g., `ACTION-EIP3860-CHECK-INITCODE-SIZE`).
    *   `label`: A concise, human-readable description.
    *   `actor_id`: The ID of the actor responsible (must match an existing ID from `trusted_entities`, or define a new one if needed).
    *   `type`: Must be either `"State"` or `"Action"`.
    *   `sub_graph_id`: (Optional) If this action represents another nested complex process.

### **Task 2.2: Define Sub-Graph Edges**

*   **Definition:** A directed edge represents a transition from a source node to a target node.
*   **Action:** For each transition, create an edge object with:
    *   `id`: A stable, unique identifier.
    *   `source`: The `id` of the starting node.
    *   `target`: The `id` of the ending node.
    *   `label`: A description of the event or condition that triggers this transition.
    *   `data_involved`: An array of data structure IDs that are passed or modified.

### **Task 2.3: Supporting Definitions (if needed)**

*   **New `trusted_entities`**: If the sub-graph introduces new actors not in the existing specification, add them.
*   **New `data_structures`**: If the sub-graph uses data objects not in the existing specification, add them.

---

## 3) Handling Constraints

*   **Prioritization:** If there are many pending items, process the most critical ones first (based on security impact or complexity).
*   **Partial Completion:** If you cannot complete all pending items due to length limits:
    1.  Generate as many complete sub-graphs as possible.
    2.  **CRITICAL:** Keep remaining items in `pending_sub_graphs` for the next iteration.
    3.  Remove successfully processed items from `pending_sub_graphs`.

---

## 4) Merge Strategy (Diff-Only Update)

**IMPORTANT:** You must perform a diff-only update. Do NOT regenerate or modify existing content.

1.  **Append to `sub_graphs`:** Add newly generated sub-graphs to the existing `sub_graphs` array. Do NOT modify or replace existing sub-graphs.
2.  **Append to `trusted_entities`:** If new actors were identified, append them to the existing array. Do NOT duplicate existing entries.
3.  **Append to `data_structures`:** If new data structures were identified, append them to the existing array. Do NOT duplicate existing entries.
4.  **Update `pending_sub_graphs`:** Remove items that were successfully processed. Keep items that could not be processed.
5.  **Preserve everything else:** All other fields (`metadata`, `program_graph`, existing `sub_graphs`, etc.) must remain unchanged.

---

## 5) Required Output Format

**File:** `outputs/01_SPEC.json` (updated in place)

The updated JSON should follow this merge pattern:

```json
{
  "metadata": { /* UNCHANGED */ },
  "trusted_entities": [
    /* EXISTING ENTRIES - UNCHANGED */,
    /* NEW ENTRIES APPENDED HERE (if any) */
  ],
  "data_structures": [
    /* EXISTING ENTRIES - UNCHANGED */,
    /* NEW ENTRIES APPENDED HERE (if any) */
  ],
  "program_graph": { /* UNCHANGED */ },
  "sub_graphs": [
    /* EXISTING SUB-GRAPHS - UNCHANGED */,
    /* NEWLY GENERATED SUB-GRAPHS APPENDED HERE */
    {
      "id": "GRAPH-EIP-3860-INITCODE-LIMIT",
      "title": "EIP-3860: Limit Initcode Size",
      "nodes": [
        {
          "id": "STATE-EIP3860-CONTRACT-CREATION-START",
          "label": "Contract Creation Initiated",
          "actor_id": "ACTOR-EL-EXECUTION-CLIENT",
          "type": "State"
        },
        {
          "id": "ACTION-EIP3860-CHECK-INITCODE-SIZE",
          "label": "Check Initcode Size Against Limit",
          "actor_id": "ACTOR-EL-EXECUTION-CLIENT",
          "type": "Action"
        },
        {
          "id": "STATE-EIP3860-INITCODE-VALID",
          "label": "Initcode Size Valid",
          "actor_id": "ACTOR-EL-EXECUTION-CLIENT",
          "type": "State"
        },
        {
          "id": "STATE-EIP3860-INITCODE-EXCEEDS-LIMIT",
          "label": "Initcode Exceeds Limit - Revert",
          "actor_id": "ACTOR-EL-EXECUTION-CLIENT",
          "type": "State"
        }
      ],
      "edges": [
        {
          "id": "EDGE-EIP3860-BEGIN-CHECK",
          "source": "STATE-EIP3860-CONTRACT-CREATION-START",
          "target": "ACTION-EIP3860-CHECK-INITCODE-SIZE",
          "label": "Begin initcode size validation",
          "data_involved": ["DATA-INITCODE"]
        },
        {
          "id": "EDGE-EIP3860-SIZE-OK",
          "source": "ACTION-EIP3860-CHECK-INITCODE-SIZE",
          "target": "STATE-EIP3860-INITCODE-VALID",
          "label": "Initcode size <= MAX_INITCODE_SIZE (49152 bytes)",
          "data_involved": []
        },
        {
          "id": "EDGE-EIP3860-SIZE-EXCEEDED",
          "source": "ACTION-EIP3860-CHECK-INITCODE-SIZE",
          "target": "STATE-EIP3860-INITCODE-EXCEEDS-LIMIT",
          "label": "Initcode size > MAX_INITCODE_SIZE",
          "data_involved": []
        }
      ]
    }
  ],
  "pending_sub_graphs": [
    /* ONLY ITEMS NOT YET PROCESSED - Remove completed items */
  ]
}
```

---

## 6) Completion Check

After updating the file:

1.  **Report processed items:** List the IDs of sub-graphs that were successfully generated.
2.  **Report remaining items:** List any items still in `pending_sub_graphs`.
3.  **Recommend next action:** If `pending_sub_graphs` is still not empty, recommend running `/01a_specretry` again.

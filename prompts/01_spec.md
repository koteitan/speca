
---
Description: Decompose the project's technical documentation into a formal specification using the concept of Program Graphs. This includes identifying states, actions, and the transitions between them. The goal is to create a rigorous, machine-readable foundation for formal analysis and verification.
Usage: `/01_spec KEYWORDS=... SPEC_URLS=...`
Example: `/01_spec KEYWORDS="geth,ethereum client,EIP,blockchain" SPEC_URLS="https://example.com/spec,https://example.com/audit"`
Language: English only.
Execution hint: This is the first step. It provides the formal model for all subsequent analysis.
---
**Always use /serena for these development tasks to maximize token efficiency:**

# **System Specification Generation Prompt**

**Goal**
Analyze the provided technical documentation and source code to model the system's behavior as a **Program Graph**. A Program Graph consists of nodes (representing program states) and directed edges (representing state transitions). This formal representation is the foundation for rigorous security analysis.

**Output (required file):** `outputs/01_SPEC.json`

---

## 0) Research & Context Gathering

Before beginning the extraction tasks, you must gather the necessary context:

1.  **Keyword Research:** Use the `web_search` tool to investigate the provided `KEYWORDS`. Understand the domain, terminology, and key concepts related to the system.
2.  **Specification Retrieval:** If `SPEC_URLS` are provided, use `read_url_content` (or similar tools) to read the content of these URLs. **Crucially, if a URL points to a documentation index, table of contents, or landing page, you MUST recursively visit relevant sub-links.** Do not stop at the top-level page. You are responsible for ensuring comprehensive coverage of the specification by following links that are relevant to the `KEYWORDS` or the system's core functionality.
3.  **Context Integration:** Use the information gathered from your research and the provided specifications to inform your modeling in the following steps. Ensure your Program Graph accurately reflects the authoritative specifications.

---

## 1) Core Extraction Tasks: Modeling as a Program Graph

Your primary task is to translate the system's user flows and processes into a formal graph structure.

### **Task 1.1: Define Graph Nodes (`program_graph.nodes`)**

*   **Definition:** A node represents a discrete, observable state in the system or a specific computational action.
*   **Action:** For each state or action, create a node object with:
    *   `id`: A stable, unique identifier for the node (e.g., `STATE-WAITING-FOR-RPC`, `ACTION-VALIDATE-JWT`).
    *   `label`: A concise, human-readable description of the state or action.
    *   `actor_id`: The ID of the actor responsible for this state or for performing this action (must match an ID from `trusted_entities`).
    *   `type`: Must be either `"State"` or `"Action"`.

### **Task 1.2: Define Graph Edges (`program_graph.edges`)**

*   **Definition:** A directed edge represents a transition from a source node to a target node.
*   **Action:** For each transition, create an edge object with:
    *   `id`: A stable, unique identifier for the edge (e.g., `EDGE-RPC-RECEIVED`).
    *   `source`: The `id` of the starting node of the transition.
    *   `target`: The `id` of the ending node of the transition.
    *   `label`: A description of the event or condition that triggers this transition (e.g., "RPC request received", "Validation successful").
    *   `data_involved`: An array of data structure IDs (from `data_structures`) that are passed or modified during this transition.

### **Task 1.3: Supporting Definitions**

*   **`trusted_entities`**: Identify all actors in the system.
*   **`data_structures`**: Identify all core data objects passed between states.

---

## 2) Required Output Format (JSON)

**File:** `outputs/01_SPEC.json`

Generate a valid JSON object with the following graph-based structure.

```json
{
  "metadata": { /* ... */ },
  "trusted_entities": [
    {
      "id": "ACTOR-CL-CONSENSUS-CLIENT",
      "entity": "Consensus Client (CL)",
      "description": "Manages the consensus process."
    },
    {
      "id": "ACTOR-EL-EXECUTION-CLIENT",
      "entity": "Execution Client (EL)",
      "description": "The system under audit."
    }
  ],
  "data_structures": [
    {
      "id": "DATA-JWT-REQUEST",
      "name": "Authenticated RPC Request",
      "description": "A JSON-RPC request including a JWT token."
    }
  ],
  "program_graph": {
    "id": "GRAPH-ENGINE-API-AUTH",
    "title": "Engine API Authentication Flow",
    "nodes": [
      {
        "id": "STATE-CL-PREPARE-REQUEST",
        "label": "CL Preparing Request",
        "actor_id": "ACTOR-CL-CONSENSUS-CLIENT",
        "type": "State"
      },
      {
        "id": "STATE-EL-AWAITING-REQUEST",
        "label": "EL Awaiting Request",
        "actor_id": "ACTOR-EL-EXECUTION-CLIENT",
        "type": "State"
      },
      {
        "id": "ACTION-EL-VALIDATE-JWT",
        "label": "EL Validates JWT",
        "actor_id": "ACTOR-EL-EXECUTION-CLIENT",
        "type": "Action"
      },
      {
        "id": "STATE-EL-REQUEST-VALIDATED",
        "label": "EL Request Validated",
        "actor_id": "ACTOR-EL-EXECUTION-CLIENT",
        "type": "State"
      },
      {
        "id": "STATE-EL-REQUEST-REJECTED",
        "label": "EL Request Rejected",
        "actor_id": "ACTOR-EL-EXECUTION-CLIENT",
        "type": "State"
      }
    ],
    "edges": [
      {
        "id": "EDGE-CL-SENDS-REQUEST",
        "source": "STATE-CL-PREPARE-REQUEST",
        "target": "STATE-EL-AWAITING-REQUEST",
        "label": "CL sends RPC request over Engine API",
        "data_involved": ["DATA-JWT-REQUEST"]
      },
      {
        "id": "EDGE-EL-BEGINS-VALIDATION",
        "source": "STATE-EL-AWAITING-REQUEST",
        "target": "ACTION-EL-VALIDATE-JWT",
        "label": "EL receives request and begins validation",
        "data_involved": ["DATA-JWT-REQUEST"]
      },
      {
        "id": "EDGE-VALIDATION-SUCCESS",
        "source": "ACTION-EL-VALIDATE-JWT",
        "target": "STATE-EL-REQUEST-VALIDATED",
        "label": "JWT validation succeeds",
        "data_involved": []
      },
      {
        "id": "EDGE-VALIDATION-FAILURE",
        "source": "ACTION-EL-VALIDATE-JWT",
        "target": "STATE-EL-REQUEST-REJECTED",
        "label": "JWT validation fails",
        "data_involved": []
      }
    ]
  }
}
```

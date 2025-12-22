
---
Description: Generate a comprehensive catalog of security properties with 100% coverage of all nodes and edges in the Program Graph. Each graph element must have at least one associated property. This involves defining properties on graph states and edges and performing formal reachability analysis.
Usage: `/01c_prop`
Language: English only.
Execution hint: Run after `/01b_trustmodel`.
---
**Always use /serena for these development tasks to maximize token efficiency:**

# **Security Property Catalog Generation Prompt**

**Goal**
From the Program Graph (`01_SPEC.json`) and Trust Model (`01b_TRUSTMODEL.json`), generate a **comprehensive catalog of formal security properties with 100% coverage**. You MUST generate at least one property for **every node** and **every edge** in the graph. Each property will be defined in terms of the graph's nodes and edges, and its reachability will be determined by analyzing paths through the graph. No graph element may remain without an associated security property.

**Output (required file):** `outputs/01c_PROP.json`

---

## 1) Inputs

1.  **System Specification (Authoritative):** `outputs/01_SPEC.json`
2.  **Trust Model (Authoritative):** `outputs/01b_TRUSTMODEL.json`

---

## 2) Property Generation & Analysis Logic

Generate security properties for **every element** in the program graph. The goal is 100% coverage - every node and every edge must have at least one associated property.

**CRITICAL: Sub-Graph Analysis:** Your analysis must be recursive. After analyzing the main `program_graph`, you MUST iterate through each graph defined in the `sub_graphs` array and apply the exact same property generation and reachability analysis logic to the nodes and edges within each sub-graph.

### **Task 2.1: Generate Properties for ALL Nodes and Edges (Mandatory Full Coverage)**

**CRITICAL: 100% Coverage Requirement.** You **MUST** generate at least one property for **every single node** and **every single edge** in the Program Graph. No element may be left without a corresponding property.

#### **2.1.1: Node Coverage**
*   For **each node** in the `program_graph.nodes` array (and all `sub_graphs`), generate at least one property.
*   Property types for nodes:
    *   **State Invariants:** What conditions must hold when this state is reached?
    *   **Reachability Constraints:** What preconditions (prior nodes/edges) must be satisfied to reach this state?
    *   **Data Integrity:** What data integrity guarantees apply to data associated with this node?
    *   **Actor Authorization:** Is the actor associated with this node authorized for the actions it performs?

#### **2.1.2: Edge Coverage**
*   For **each edge** in the `program_graph.edges` array (and all `sub_graphs`), generate at least one property.
*   Property types for edges:
    *   **Transition Security:** Is the transition secure? Is authentication/authorization required?
    *   **Data-in-Transit Protection:** Is data transferred across this edge protected (encrypted, signed)?
    *   **Input Validation:** Is input validated before this transition occurs?
    *   **Control Flow Integrity:** Can this edge only be traversed under legitimate conditions?

#### **2.1.3: Boundary Edge Priority**
*   For **each `boundary_edge`** defined in the `TRUSTMODEL` input, you **MUST** generate **additional high-priority properties**.
*   These properties must formally state that the transition across the trust boundary is secure.
*   Boundary edges require more rigorous analysis than internal edges.

**Verification Checklist (MANDATORY):**
Before finalizing output, verify:
- [ ] Total node properties ≥ Total nodes in graph
- [ ] Total edge properties ≥ Total edges in graph
- [ ] All boundary edges have at least one property
- [ ] No orphan elements (every ID in graph_elements references a valid node/edge)

### **Task 2.2: Define the Property in Terms of the Graph**

*   `property`: A formal statement about the graph. This can be an **invariance** (a property of a `node`/`state`) or a **transition property** (a property of an `edge`).
    *   *Invariant Example:* "The node `STATE-EL-REQUEST-VALIDATED` can only be reached if the path to it includes the edge `EDGE-VALIDATION-SUCCESS`."
    *   *Transition Example:* "The data `DATA-JWT-REQUEST` transferred across the edge `EDGE-CL-SENDS-REQUEST` must be cryptographically signed."
*   `anti_property`: The formal negation of the property.
    *   *Invariant Example:* "A path exists to `STATE-EL-REQUEST-VALIDATED` that does not include the edge `EDGE-VALIDATION-SUCCESS`."
    *   *Transition Example:* "An attacker can cause unsigned data to be transferred across the edge `EDGE-CL-SENDS-REQUEST`."

### **Task 2.3: Perform Formal Reachability Analysis**

This is the core formal analysis task.

**Reachability Analysis Algorithm:**
1.  **Identify Attacker Starting Nodes:** Create a set of all nodes where the `actor_id` corresponds to an `UNTRUSTED` or `SEMI_TRUSTED` actor.
2.  **Perform Graph Traversal:** Starting from these nodes, perform a graph traversal (e.g., Breadth-First Search) to find all reachable nodes. Store the path taken to reach each node.
3.  **Check Anti-Property:** For a given `anti_property` (e.g., reaching `STATE-X` without passing through `ACTION-VALIDATE`), check if `STATE-X` is in the set of reachable nodes.
4.  **Verify Path Conditions:** If `STATE-X` is reachable, examine the path. If the path does *not* contain the required validation node/edge (e.g., `ACTION-VALIDATE`), then the anti-property is `REACHABLE`.
5.  **Conclude Unreachability:** If all possible paths from attacker nodes to `STATE-X` are proven to pass through the required validation node, then the anti-property is `UNREACHABLE`.

**Justify the Analysis (`reachability_rationale`):** Provide a formal argument based on the graph structure. "The anti-property is unreachable because all paths from the untrusted node `STATE-CL-PREPARE-REQUEST` to the target `STATE-EL-REQUEST-VALIDATED` must pass through the `ACTION-EL-VALIDATE-JWT` node. The definition of this action node specifies it has two outgoing edges: `EDGE-VALIDATION-SUCCESS` and `EDGE-VALIDATION-FAILURE`. An invalid input provably leads to the `STATE-EL-REQUEST-REJECTED` node, making the target state unreachable for an attacker."

### **Task 2.4: Link to Graph Elements**

*   `graph_elements`: An array of `id`s for the nodes and edges from `01_SPEC.json` that are relevant to this property. This makes the property directly traceable to the formal model.

---

## 3) Required Output Format (JSON)

**File:** `outputs/01c_PROP.json`

```json
{
  "metadata": { /* ... */ },
  "coverage_summary": {
    "total_nodes_in_graph": 10,
    "total_edges_in_graph": 15,
    "total_boundary_edges": 3,
    "nodes_with_properties": 10,
    "edges_with_properties": 15,
    "boundary_edges_with_properties": 3,
    "node_coverage_percent": 100,
    "edge_coverage_percent": 100,
    "uncovered_elements": []
  },
  "properties": [
    {
      "property_id": "PROP-GRAPH-AUTH-PATH-INTEGRITY",
      "covers": {
        "primary_element": "STATE-EL-REQUEST-VALIDATED",
        "element_type": "node",
        "is_boundary_edge": false
      },
      "property": "The state STATE-EL-REQUEST-VALIDATED is only reachable via a path that includes the edge EDGE-VALIDATION-SUCCESS.",
      "anti_property": "A path exists from an untrusted node to STATE-EL-REQUEST-VALIDATED that bypasses the EDGE-VALIDATION-SUCCESS edge.",
      "graph_elements": [
        "STATE-EL-REQUEST-VALIDATED",
        "ACTION-EL-VALIDATE-JWT",
        "EDGE-VALIDATION-SUCCESS",
        "EDGE-VALIDATION-FAILURE"
      ],
      "status": "in_scope",

      "reachability": "UNREACHABLE",
      "reachability_rationale": "This property is proven to be unreachable by the graph structure. All paths originating from untrusted actors must pass through ACTION-EL-VALIDATE-JWT. The definition of this action node ensures that only valid inputs can lead to the EDGE-VALIDATION-SUCCESS transition. Therefore, no path exists for an attacker to reach the target state illicitly.",

      "cryptographic_guarantee": "HS256 JWT Validation",
      "notes": "The security of this property is contingent on the correct implementation of the ACTION-EL-VALIDATE-JWT node. While unreachable in the formal model, the implementation of this action is the focus of the subsequent checklist."
    },
    {
      "property_id": "PROP-EDGE-CL-SENDS-REQUEST-INTEGRITY",
      "covers": {
        "primary_element": "EDGE-CL-SENDS-REQUEST",
        "element_type": "edge",
        "is_boundary_edge": true
      },
      "property": "Data transferred across EDGE-CL-SENDS-REQUEST must be cryptographically signed with a valid JWT.",
      "anti_property": "An attacker can cause unsigned or malformed data to be accepted across EDGE-CL-SENDS-REQUEST.",
      "graph_elements": ["EDGE-CL-SENDS-REQUEST", "DATA-JWT-REQUEST"],
      "status": "in_scope",
      "reachability": "UNREACHABLE",
      "reachability_rationale": "The edge definition mandates JWT signing. The receiving node ACTION-EL-VALIDATE-JWT rejects any unsigned payload.",
      "cryptographic_guarantee": "HS256 JWT Signing",
      "notes": "Boundary edge property - higher priority."
    }
  ]
}
```


---
Description: Generate a catalog of security properties by analyzing paths and transitions within the Program Graph. This involves defining properties on graph states and edges and performing formal reachability analysis.
Usage: `/01c_prop`
Language: English only.
Execution hint: Run after `/01b_trustmodel`.
---
**Always use /serena for these development tasks to maximize token efficiency:**

# **Security Property Catalog Generation Prompt**

**Goal**
From the Program Graph (`01_SPEC.json`) and Trust Model (`01b_TRUSTMODEL.json`), generate a catalog of formal security properties. Each property will be defined in terms of the graph's nodes and edges, and its reachability will be determined by analyzing paths through the graph.

**Output (required file):** `outputs/01c_PROP.json`

---

## 1) Inputs

1.  **System Specification (Authoritative):** `outputs/01_SPEC.json`
2.  **Trust Model (Authoritative):** `outputs/01b_TRUSTMODEL.json`

---

## 2) Property Generation & Analysis Logic

For each major behavior represented by a path in the program graph, generate one or more security properties.

### **Task 2.1: Define the Property in Terms of the Graph**

*   `property`: A formal statement about the graph. This can be an **invariance** (a property of a `node`/`state`) or a **transition property** (a property of an `edge`).
    *   *Invariant Example:* "The node `STATE-EL-REQUEST-VALIDATED` can only be reached if the path to it includes the edge `EDGE-VALIDATION-SUCCESS`."
    *   *Transition Example:* "The data `DATA-JWT-REQUEST` transferred across the edge `EDGE-CL-SENDS-REQUEST` must be cryptographically signed."
*   `anti_property`: The formal negation of the property.
    *   *Invariant Example:* "A path exists to `STATE-EL-REQUEST-VALIDATED` that does not include the edge `EDGE-VALIDATION-SUCCESS`."
    *   *Transition Example:* "An attacker can cause unsigned data to be transferred across the edge `EDGE-CL-SENDS-REQUEST`."

### **Task 2.2: Perform Formal Reachability Analysis**

This is the core formal analysis task.

1.  **Identify the Target State/Edge:** This is the state/edge the `anti_property` is trying to achieve/violate.
2.  **Identify the Attacker:** An `UNTRUSTED` or `SEMI_TRUSTED` actor.
3.  **Analyze Paths:** Can the attacker, starting from a node they control, construct a path through the graph to the target state/edge that violates the property?
4.  **Consult Boundary Edges:** Use the `boundary_edges` from `01b_TRUSTMODEL.json`. An attacker's most likely path will involve manipulating the data (`data_flows_across`) on one of these edges.
5.  **Determine `reachability`:**
    *   `REACHABLE`: A path exists that an untrusted actor can force, leading to the `anti_property` state.
    *   `UNREACHABLE`: All paths to the desired state are provably blocked by a trusted `Action` node (e.g., a validation action) that has no outgoing edges leading to a success state for invalid inputs.
6.  **Justify the Analysis (`reachability_rationale`):** Provide a formal argument based on the graph structure. "The anti-property is unreachable because all paths from the untrusted node `STATE-CL-PREPARE-REQUEST` to the target `STATE-EL-REQUEST-VALIDATED` must pass through the `ACTION-EL-VALIDATE-JWT` node. The definition of this action node specifies it has two outgoing edges: `EDGE-VALIDATION-SUCCESS` and `EDGE-VALIDATION-FAILURE`. An invalid input provably leads to the `STATE-EL-REQUEST-REJECTED` node, making the target state unreachable for an attacker."

### **Task 2.3: Link to Graph Elements**

*   `graph_elements`: An array of `id`s for the nodes and edges from `01_SPEC.json` that are relevant to this property. This makes the property directly traceable to the formal model.

---

## 3) Required Output Format (JSON)

**File:** `outputs/01c_PROP.json`

```json
{
  "metadata": { /* ... */ },
  "properties": [
    {
      "property_id": "PROP-GRAPH-AUTH-PATH-INTEGRITY",
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
    }
  ]
}
```

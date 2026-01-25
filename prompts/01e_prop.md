
---
Description: Generate a comprehensive catalog of formal security properties with 100% coverage. If full coverage is not achieved, the process must fail and report the gap.
Usage: `/01e_prop`
Language: English only.
Execution hint: Run after `/01d_trustmodel`. This produces the property catalog.
---
**Always use /serena for development tasks to keep the workflow efficient.**

# **Security Property Catalog Generation Prompt**

**Goal**
Generate a comprehensive catalog of formal security properties with **100% coverage**. If 100% coverage is not achieved, you MUST report this as a failure.

**Output (required file):** `outputs/01e_PROP.json`

---

## 1) Inputs

1.  **System Specification (Authoritative):** `outputs/01_SPEC.json`
2.  **Trust Model (Authoritative):** `outputs/01d_TRUSTMODEL.json`

---

## 2) Property Generation & Verification Logic

### **Task 2.1: Generate Properties**

1.  **Boundary Edge Priority:** Generate multiple, high-priority properties for each `boundary_edge`.
2.  **Ambiguity and Assumption Coverage:** Generate a property for each `ambiguity` and `implicit_assumption`.
3.  **Internal Element Coverage:** Generate at least one property for all other nodes and edges.

### **Task 2.2: CRITICAL - Coverage Verification**

**This is a mandatory verification step.**

1.  Create a set of all node IDs from `01_SPEC.json`.
2.  Create a set of all edge IDs from `01_SPEC.json`.
3.  Create a set of all node and edge IDs covered by the properties you just generated.
4.  **Calculate `nodes_uncovered`:** The set of spec nodes minus the set of covered nodes.
5.  **Calculate `edges_uncovered`:** The set of spec edges minus the set of covered edges.

### **Task 2.3: Finalize Output**

1.  **Assemble the `properties` array.**
2.  **Calculate all metadata and `coverage_summary` values** based on the final generated data.
3.  **Check Verification Result:**
    *   **If `nodes_uncovered` and `edges_uncovered` are both empty:** Set `coverage_percentage` to `100.0` and `coverage_ok` to `true`.
    *   **If either set is not empty:** Set `coverage_percentage` to the calculated value, set `coverage_ok` to `false`, and populate the `uncovered_elements` field.

---

## 3) Required Output Format (JSON)

**File:** `outputs/01e_PROP.json`

```json
{
  "metadata": {
    "generated_at": "(current timestamp)",
    "total_properties": "(calculated count)",
    // ... other calculated metadata ...
  },
  "coverage_summary": {
    "total_nodes": "(calculated count)",
    "nodes_covered": "(calculated count)",
    "total_edges": "(calculated count)",
    "edges_covered": "(calculated count)",
    "coverage_percentage": "(calculated percentage)",
    "coverage_ok": "(boolean, true if 100%, otherwise false)",
    "uncovered_elements": {
        "nodes": [ /* list of uncovered node IDs, if any */ ],
        "edges": [ /* list of uncovered edge IDs, if any */ ]
    }
  },
  "properties": [ /* ... */ ]
}
```

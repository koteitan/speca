
---
Description: Perform a multi-phase review of the generated artifacts using advanced prompting techniques. This includes a critical self-verification step to ensure data consistency before analysis.
Usage: `/02s_review`
Language: English only.
Execution hint: This is the final step of the preparation phase. It validates all prior outputs.
---
**Always use /serena for these development tasks to maximize token efficiency:**

# **Comprehensive Artifact Review Prompt**

**Goal**
Perform a multi-phase review of all generated artifacts (`SPEC`, `TRUSTMODEL`, `PROP`). This review MUST begin with a **critical self-verification** of data consistency.

**Output (required file):** `outputs/02s_REVIEW_REPORT.json`

---

## **Phase 0: CRITICAL - Pre-computation & Self-Verification**

**This phase must be completed before any other analysis.**

1.  **Verify `01e_PROP.json` Coverage:**
    *   Read the `coverage_summary` from `01e_PROP.json`.
    *   Check the `coverage_ok` flag.
    *   **If `coverage_ok` is `false`:** Your `overall_verdict` MUST be `FAIL`. State that the review cannot proceed due to incomplete property coverage and list the contents of `uncovered_elements`. **Do not proceed to other phases.**

2.  **Verify `01_SPEC.json` Metadata:**
    *   Count the actual number of nodes and edges in `program_graph`.
    *   Compare these counts to the `total_nodes` and `total_edges` in the `metadata`.
    *   **If they do not match:** Your `overall_verdict` MUST be `FAIL`. State that the review cannot proceed due to inconsistent metadata in `01_SPEC.json`. **Do not proceed to other phases.**

3.  **Verify `01e_PROP.json` Metadata:**
    *   Count the actual number of properties in the `properties` array.
    *   Compare this to `total_properties` in the `metadata`.
    *   **If they do not match:** Your `overall_verdict` MUST be `FAIL`. State that the review cannot proceed due to inconsistent metadata in `01e_PROP.json`. **Do not proceed to other phases.**

**If all checks in Phase 0 pass, proceed to the subsequent review phases.**

---

### **Phase 1: Specification Completeness Review**

*   **Thought:** "Is the `01_SPEC.json` a complete representation of the system? Are all relevant specifications covered?"
*   **Action:**
    1.  Count the number of source URLs in `processed_urls` (from `01a_STATE.json` if available, or infer from `ambiguities`/`implicit_assumptions` source URLs).
    2.  Verify that all major EIPs and specifications mentioned in the initial `SPEC_URLS` are represented.
    3.  Check for orphan nodes (nodes with no incoming or outgoing edges).
*   **Reflection:** "Did I miss any obvious specifications? Are there any gaps in the graph structure?"

### **Phase 2: Trust Model Consistency Review (Tree of Thoughts)**

*   **Thought:** "Is the trust model consistent with the specification and with security best practices?"
*   **Action (Explore 3 Branches):**
    1.  **Branch A (Entity Coverage):** Verify that every `external_entity` in `01_SPEC.json` has a corresponding entry in `trusted_external_entities`.
    2.  **Branch B (Boundary Edge Coverage):** Verify that every edge with a `source` matching an `external_entity` ID is listed in `boundary_edges`.
    3.  **Branch C (Trust Level Appropriateness):** For each trust level assignment, critically evaluate if it's appropriate. Is `TRUSTED` ever used? If so, is it justified?
*   **Reflection:** "Do all three branches converge on a consistent model? Are there any contradictions?"

### **Phase 3: Adversarial Scenario Testing**

*   **Thought:** "Can I construct an attack scenario that the current model would miss?"
*   **Action:**
    1.  Select 3-5 `boundary_edges` with `UNTRUSTED` or `SEMI_TRUSTED` sources.
    2.  For each, hypothesize an attack (e.g., malformed input, replay attack, injection).
    3.  Trace the attack path through the graph. Does the model have properties that would detect/prevent this attack?
*   **Reflection:** "Did any attack scenario reveal a gap in the property coverage?"

### **Phase 4: Property Coverage Review (Self-Consistency)**

*   **Thought:** "Does the property catalog achieve 100% coverage, and are the reachability analyses correct?"
*   **Action:**
    1.  **Approach A (Node/Edge → Property):** For a sample of 10 nodes and 10 edges, verify that at least one property covers them.
    2.  **Approach B (Property → Node/Edge):** For a sample of 10 properties, verify that the `graph_elements` they reference actually exist in the spec.
    3.  **Approach C (Boundary Cross-Reference):** Verify that every `boundary_edge` has at least one property with `is_boundary_edge: true`.
*   **Reflection:** "Do all three approaches yield consistent results? If not, where is the discrepancy?"

### **Phase 5: Ambiguity and Assumption Handling Review**

*   **Thought:** "Are all ambiguities and implicit assumptions properly addressed in the property catalog?"
*   **Action:**
    1.  For each `ambiguity` in `01_SPEC.json`, verify that at least one property references it via `related_ambiguity_id`.
    2.  For each `implicit_assumption` in `01_SPEC.json`, verify that at least one property references it via `related_assumption_id`.
*   **Reflection:** "Are there any unaddressed ambiguities or assumptions that could lead to security issues?"

---

## Required Output Format (JSON)

**File:** `outputs/02s_REVIEW_REPORT.json`

```json
{
  "metadata": { /* ... */ },
  "overall_verdict": "(PASS / FAIL / PASS_WITH_OBSERVATIONS)",
  "phase_0_verification": {
      "verdict": "(PASS / FAIL)",
      "checks": [
          {"check": "Property Coverage", "status": "(PASS / FAIL)", "details": "..."},
          {"check": "SPEC Metadata Consistency", "status": "(PASS / FAIL)", "details": "..."},
          {"check": "PROP Metadata Consistency", "status": "(PASS / FAIL)", "details": "..."}
      ]
  },
  "phases": [ /* ... review phases, only if Phase 0 passed ... */ ]
}
```

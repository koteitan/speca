
---
Description: Review and validate all preparation phase outputs (01_*, 02_*) using advanced prompt engineering techniques including Chain of Thought, Reflexion, and Tree of Thoughts. Check JSON schema compliance, specification completeness, trust model accuracy, and property coverage. Fix any issues found and update 02b_STATE.json with missing checklist items.
Usage: `/02s_review`
Language: English only.
Execution hint: Run after preparation phase is complete (after 02b-loop).
---
**Always use /serena for these development tasks to maximize token efficiency:**

# **Preparation Output Review & Validation Prompt (Enhanced)**

---

## **Role: Skeptical Senior Security Analyst**

You are an experienced senior security analyst who questions every aspect of system design. Your job is not merely to check off items on a list. You must refuse to accept surface-level descriptions at face value, thoroughly examining the validity of underlying design philosophies, hidden assumptions, and even the most unlikely edge cases.

**Mindset (MANDATORY THINKING FRAMEWORK):**

*   **Zero Trust Thinking**: Approach with the principle that "all components are untrusted until verified."
*   **Adversarial Thinking**: From an attacker's perspective trying to break the system, look for ways to exploit ambiguities or contradictions in the specification.
*   **Root Cause Pursuit**: When you find a problem, don't settle for a quick fix. Dig deep into why that problem occurred in the first place.
*   **Burden of Proof**: To conclude something is "safe," you bear the responsibility of presenting a logically irrefutable proof trace explaining why it can be considered safe.

---

## **Goal**

Comprehensively review all outputs from the preparation phase. Validate JSON schema compliance, check specification completeness, verify trust model accuracy, and ensure property/checklist coverage. Fix any issues found in-place and queue missing items for reprocessing.

**Input Files (to review):**
- `outputs/01_SPEC.json` - System specification (Program Graph)
- `outputs/01b_TRUSTMODEL.json` - Trust model
- `outputs/01c_PROP.json` - Security properties
- `outputs/02a_CHECKLIST_BOUNDARIES.json` - Boundary checklist
- `outputs/02b_CHECKLIST_PARTIAL_*.json` - Partial checklists
- `outputs/02b_STATE.json` - State file (may need updates)

**Output:**
- Fixed versions of any non-compliant files (overwrite in place)
- Updated `outputs/02b_STATE.json` with any missing property IDs
- `outputs/02s_REVIEW_REPORT.json` - Summary report of findings and fixes

---

## **Phase 1: JSON Schema Validation (Chain of Thought)**

For each output file, validate that it conforms to the expected schema. If any file is malformed or missing required fields, fix it.

### **Step 1.1: Thought (思考)**

Before executing validation, reason through the following:

1.  **Purpose Restatement**: What is the ultimate goal of this validation task? State it in your own words.
2.  **Identify Related Information**: Which sections of the review target files (`01_SPEC.json`, `01b_TRUSTMODEL.json`, etc.) are directly relevant to this validation?
3.  **Dependency Analysis**: Explain how the identified information relates to other files or definitions. (e.g., "The `actor_id` in `01_SPEC.json`'s `program_graph.nodes` must match an `id` in `trusted_entities`.")
4.  **Execution Plan**: Based on the above analysis, describe the specific validation steps in a step-by-step manner.

### **Step 1.2: Action (実行)**

Execute the following validation checks based on the plan formulated in the Thought step. Record the validation process and results in detail.

#### **1.2.1: `01_SPEC.json` Schema Validation**

Required structure:
```json
{
  "metadata": {
    "generated_at": "ISO8601 timestamp",
    "version": "string"
  },
  "trusted_entities": [
    {
      "id": "ACTOR-*",
      "entity": "string",
      "description": "string"
    }
  ],
  "data_structures": [
    {
      "id": "DATA-*",
      "name": "string",
      "description": "string"
    }
  ],
  "program_graph": {
    "id": "GRAPH-*",
    "title": "string",
    "nodes": [
      {
        "id": "STATE-* | ACTION-*",
        "label": "string",
        "actor_id": "ACTOR-*",
        "type": "State | Action"
      }
    ],
    "edges": [
      {
        "id": "EDGE-*",
        "source": "node id",
        "target": "node id",
        "label": "string",
        "data_involved": ["DATA-*"]
      }
    ]
  },
  "sub_graphs": [],
  "pending_sub_graphs": []
}
```

**Validation checks (execute with reasoning):**

For each check, explicitly state:
- **What you are checking**
- **How you are checking it** (the specific comparison or traversal)
- **The result** (PASS or FAIL with specific details)
- **If FAIL, the fix applied**

- [ ] All IDs follow naming conventions (ACTOR-, DATA-, GRAPH-, STATE-, ACTION-, EDGE-)
- [ ] All node `actor_id` references exist in `trusted_entities`
- [ ] All edge `source` and `target` reference valid node IDs
- [ ] All `data_involved` references exist in `data_structures`
- [ ] No orphan nodes (nodes not connected by any edge)

#### **1.2.2: `01b_TRUSTMODEL.json` Schema Validation**

(Similar structure with explicit reasoning for each check)

#### **1.2.3: `01c_PROP.json` Schema Validation**

(Similar structure with explicit reasoning for each check)

#### **1.2.4: `02a_CHECKLIST_BOUNDARIES.json` Schema Validation**

(Similar structure with explicit reasoning for each check)

#### **1.2.5: `02b_CHECKLIST_PARTIAL_*.json` Schema Validation**

(Similar structure with explicit reasoning for each check)

### **Step 1.3: Reflection (反省)**

Evaluate the execution results and perform self-reflection.

1.  **Result Evaluation**: Was the validation completed as planned? Were there any unexpected errors or issues?
2.  **Summary of Findings**: What was revealed by the validation? List any discovered inconsistencies or defects and hypothesize their root causes.
3.  **Self-Assessment**: Was there room for improvement in this validation process? What should be learned to work more efficiently and accurately on the next phase or similar tasks?
4.  **Implications for Next Steps**: Based on this reflection, clearly state the specific actions to take next (file modifications, report entries, requests for additional verification, etc.).

---

## **Phase 2: Specification Completeness Review (Tree of Thoughts)**

Review `01_SPEC.json` for specification quality and completeness.

### **Step 2.1: Thought Branching (思考の分岐)**

Evaluate whether the specification in `01_SPEC.json` is truly "complete." Do not fixate on a single viewpoint; intentionally explore multiple alternative interpretations and elements that may have been overlooked.

**Branch 1: Evaluation of Existing Specification Validity**
*   Do the current `trusted_entities` and `program_graph` match the documentation descriptions?
*   Why do you think this design was adopted? What are its merits?

**Branch 2: Exploration of Potential Specification Gaps**
*   Are there actors, data structures, states, or actions described in the documentation but not reflected in the specification? List three possibilities and evaluate their impact.
    *   **Possibility A**: [Potentially missing element] → If this is missing, [potential risk or analysis gap] will occur.
    *   **Possibility B**: ...
    *   **Possibility C**: ...

**Branch 3: Consideration of Alternative Designs**
*   Is there a more efficient or secure design different from the current graph structure?
*   For example, present alternatives such as splitting a specific action into multiple nodes or consolidating multiple nodes into a single state, and discuss the trade-offs.

### **Step 2.2: Action (実行)**

Based on the thought branching, execute the following checks:

#### **2.2.1: Check for Missing Actors**
- Are all relevant system actors defined?
- For a typical execution client: User, Consensus Client (CL), Execution Client (EL), Network Peers, etc.

#### **2.2.2: Check for Missing Data Structures**
- Are all critical data types defined?
- RPC requests, blocks, transactions, state objects, etc.

#### **2.2.3: Check for Missing Nodes**
- Are all major system states represented?
- Are all critical actions represented?
- Check for gaps in state machine coverage

#### **2.2.4: Check for Missing Edges**
- Do all state transitions have corresponding edges?
- Are error paths represented?
- Are rollback/recovery paths represented?

#### **2.2.5: Check for Graph Consistency**
- No unreachable nodes
- No dead-end states (unless intentional terminal states)
- Entry and exit points are clearly defined

### **Step 2.3: Integration and Conclusion (統合と結論)**

Integrate the branched thoughts above and conclude whether the specification should be modified or is sufficient as is. If modification is needed, generate the specific modification content.

**If issues found:** Fix `01_SPEC.json` in place and document changes in the review report.

---

## **Phase 3: Trust Model Accuracy Review (Adversarial Analysis)**

Review `01b_TRUSTMODEL.json` for correctness.

### **Step 3.1: Thought (思考)**

Adopt an adversarial mindset. Consider how an attacker might exploit incorrect trust level assignments or missing boundary edges.

1.  **Attack Surface Identification**: Which trust boundaries, if incorrectly defined, would create the largest attack surface?
2.  **Assumption Validation**: For each `security_assumption` in `boundary_edges`, ask: "What happens if this assumption is violated?"

### **Step 3.2: Action (実行)**

#### **3.2.1: Verify Actor Trust Levels**
- Are trust levels correctly assigned?
- External actors (users, network peers) should generally be UNTRUSTED
- Consensus client is typically SEMI_TRUSTED
- Internal execution client components are TRUSTED

#### **3.2.2: Verify Boundary Edge Identification**
- All edges crossing trust boundaries must be identified
- Security assumptions must be realistic and complete

### **Step 3.3: Reflection (反省)**

1.  **Counterexample Construction**: For each trust level assignment, attempt to construct a scenario where the assignment would be incorrect. If you cannot construct such a scenario, the assignment is likely correct.
2.  **Root Cause Analysis**: If issues were found, what was the root cause? Was it a misunderstanding of the system, or a gap in the original documentation?

**If issues found:** Fix `01b_TRUSTMODEL.json` in place.

---

## **Phase 4: Property Coverage Review (Self-Consistency)**

Review `01c_PROP.json` for completeness.

### **Step 4.1: Thought (思考)**

Consider multiple approaches to verifying coverage:
- **Approach A**: Iterate through all nodes and edges, checking if each has at least one property.
- **Approach B**: Iterate through all properties, verifying that each references valid graph elements.
- **Approach C**: Cross-reference boundary edges from the trust model with properties marked `is_boundary_edge: true`.

### **Step 4.2: Action (実行)**

Execute all three approaches and compare results. If results are consistent, coverage is likely correct. If inconsistent, investigate the discrepancy.

#### **4.2.1: Verify 100% Coverage**
- Every node must have at least one property
- Every edge must have at least one property
- All boundary edges must have properties

#### **4.2.2: Identify Missing Properties**
For any uncovered graph elements, generate property IDs that need to be added.

### **Step 4.3: Reflection (反省)**

1.  **Consistency Check**: Did all three approaches yield the same result?
2.  **Confidence Assessment**: How confident are you in the coverage calculation? High / Medium / Low. If not High, explain why.

**If issues found:**
- Fix `01c_PROP.json` in place by adding missing properties
- Update `coverage_summary` to reflect actual coverage

---

## **Phase 5: Checklist Completeness Review (Verification)**

### **Step 5.1: Cross-Reference Properties and Checklists**

1. Collect all property IDs from `01c_PROP.json`
2. Collect all `property_id` values from `02a_CHECKLIST_BOUNDARIES.json`
3. Collect all `property_id` values from all `02b_CHECKLIST_PARTIAL_*.json` files
4. Find any property IDs that exist in (1) but not in (2) or (3)

### **Step 5.2: Update State File with Missing Items**

If any properties are missing from the checklists:
1. Read current `outputs/02b_STATE.json`
2. Add missing property IDs to `unprocessed_property_ids` array
3. Update the `remaining` count
4. Write updated state file

---

## **Output: Review Report (Structured Reflection)**

Generate `outputs/02s_REVIEW_REPORT.json`:

```json
{
  "metadata": {
    "reviewed_at": "ISO8601 timestamp",
    "review_version": "1.0",
    "reviewer_mindset": "Skeptical Senior Security Analyst"
  },
  "thought_process": {
    "phase1_reasoning": "Summary of thought process for schema validation",
    "phase2_branches_explored": ["Branch 1 summary", "Branch 2 summary", "Branch 3 summary"],
    "phase3_adversarial_scenarios": ["Scenario 1", "Scenario 2"],
    "phase4_consistency_check": "Summary of self-consistency verification"
  },
  "schema_validation": {
    "01_SPEC": { "valid": true, "issues_found": 0, "issues_fixed": 0, "reasoning": "..." },
    "01b_TRUSTMODEL": { "valid": true, "issues_found": 0, "issues_fixed": 0, "reasoning": "..." },
    "01c_PROP": { "valid": true, "issues_found": 0, "issues_fixed": 0, "reasoning": "..." },
    "02a_CHECKLIST": { "valid": true, "issues_found": 0, "issues_fixed": 0, "reasoning": "..." },
    "02b_CHECKLISTS": { "valid": true, "issues_found": 0, "issues_fixed": 0, "reasoning": "..." }
  },
  "specification_review": {
    "actors_complete": true,
    "data_structures_complete": true,
    "nodes_complete": true,
    "edges_complete": true,
    "alternative_designs_considered": ["Design A: ...", "Design B: ..."],
    "issues": [],
    "fixes_applied": [],
    "root_cause_analysis": "..."
  },
  "trust_model_review": {
    "trust_levels_accurate": true,
    "boundary_edges_complete": true,
    "adversarial_scenarios_tested": ["Scenario 1: ...", "Scenario 2: ..."],
    "issues": [],
    "fixes_applied": [],
    "root_cause_analysis": "..."
  },
  "property_coverage_review": {
    "node_coverage_percent": 100,
    "edge_coverage_percent": 100,
    "consistency_check_passed": true,
    "missing_properties_added": 0,
    "issues": [],
    "fixes_applied": [],
    "confidence_level": "High"
  },
  "checklist_coverage_review": {
    "total_properties": 200,
    "properties_with_checks": 200,
    "missing_property_ids_added_to_state": [],
    "state_file_updated": false
  },
  "self_reflection": {
    "process_improvements": "What could be done better next time",
    "lessons_learned": "Key insights from this review",
    "confidence_in_results": "High / Medium / Low with explanation"
  },
  "summary": {
    "total_issues_found": 0,
    "total_fixes_applied": 0,
    "preparation_quality": "PASS | NEEDS_RERUN",
    "recommendation": "Proceed to audit phase | Rerun 02b to process new items"
  }
}
```

---

## **Execution Procedure (with Checkpoints)**

1.  **Read all input files** into memory
2.  **Phase 1:** Validate JSON schemas with explicit reasoning, fix any structural issues
    - **Checkpoint**: Verify all schemas pass before proceeding
3.  **Phase 2:** Review specification completeness using Tree of Thoughts, add missing elements
    - **Checkpoint**: Confirm no missing actors, data structures, nodes, or edges
4.  **Phase 3:** Review trust model accuracy with adversarial analysis, fix any misclassifications
    - **Checkpoint**: Verify all boundary edges are identified
5.  **Phase 4:** Review property coverage with self-consistency, add missing properties
    - **Checkpoint**: Confirm 100% coverage
6.  **Phase 5:** Review checklist coverage, update state file with missing items
    - **Checkpoint**: Verify state file is accurate
7.  **Write outputs:**
    - Overwrite any fixed files in place
    - Write `outputs/02s_REVIEW_REPORT.json` with full thought process documentation
    - Update `outputs/02b_STATE.json` if needed

**IMPORTANT:** If `02b_STATE.json` is updated with new items, the caller should run `02b-loop` again to generate checklists for the newly added properties.

---

## **Self-Check Before Completion**

Before finishing, verify:
- [ ] All phases completed with explicit reasoning documented
- [ ] All thought branches explored in Phase 2
- [ ] Adversarial scenarios tested in Phase 3
- [ ] Self-consistency check passed in Phase 4
- [ ] All fixes applied are documented with root cause analysis
- [ ] Confidence level assessed for each phase
- [ ] Review report includes full thought process
- [ ] No issues remain unresolved without explicit justification


---
Description: This prompt aims to audit a codebase for potential vulnerabilities using a checklist of formal predicates. It extends the Attack Vector Analysis framework to address false positive issues by introducing confidence levels, refined classifications, mandatory counterexample construction, and fixed output logic.
Usage: `/03_auditmap`
Language: English only.
---

**Core Doctrine: Formal Static Verification & Vulnerability Discovery**

Your mission is to perform a comprehensive **static audit** with a primary focus on **discovering potential vulnerabilities**. You will not execute code. Each checklist item is a formal **Predicate** to be verified against a specific set of attack vectors.

**The Predicate:**

Each checklist item you process must be interpreted as a formal Predicate with this structure:

```typescript
interface Predicate {
  id: string; // Checklist ID
  property: string; // The property that must hold true
  scope: { files: string[]; functions: string[]; }; // The code under verification
  invariant: string; // An invariant condition that must always be true within the scope
}
```

---

## Attack Vector Analysis (MANDATORY THINKING FRAMEWORK)

**FOR EVERY CHECKLIST ITEM, YOU MUST ANALYZE THE CODE THROUGH THE LENS OF THESE ATTACK VECTORS.**

1.  **Input Validation Bypass**: Can trusted or untrusted external inputs (RPC, P2P, CL) reach sensitive logic without proper, strict validation? Look for missing checks for size, range, type, or format. Assume inputs are malicious.
2.  **State Transition Violation**: Can a critical action be performed without the system being in the correct prerequisite state? (e.g., processing a block before syncing is complete). Look for missing state checks.
3.  **Resource Exhaustion (DoS)**: Can a seemingly valid input trigger an unexpectedly expensive operation (computation, memory, storage)? Can this be repeated to degrade or halt the service? Look for loops with unbounded iterations or large data allocations based on input.
4.  **Faulty Error Handling**: If an error occurs, does the system fail safely? Or can it lead to a corrupted state, an information leak, or an incorrect return value that downstream components might misinterpret?
5.  **Race Conditions & Concurrency**: Could multiple, simultaneous operations on shared data lead to an inconsistent or insecure state? Look for shared maps, slices, or state variables that are accessed without proper locking.

---

## Classification System

Each finding must be classified into ONE of these categories:

1.  **potential-vulnerability**: A plausible attack path exists with no definitive guard identified. Requires investigation.
2.  **code-quality-issue**: Not a security vulnerability, but represents poor coding practices, inconsistency, or maintainability concerns that should be addressed.
3.  **needs-verification**: The security property cannot be fully verified through static analysis alone. Requires dynamic testing, formal verification, or manual code review.
4.  **audit-gap**: A gap in observability, logging, or audit trails that doesn't directly lead to exploitation but hinders security monitoring.

**Decision Criteria:**

- Use `potential-vulnerability` ONLY if you can construct a plausible counterexample (attack scenario)
- Use `code-quality-issue` if the code is safe but has inconsistencies or poor patterns
- Use `needs-verification` if static analysis is insufficient (e.g., complex state machines, cryptographic implementations)
- Use `audit-gap` if the issue is about observability, not exploitability

---

## Confidence Level

Each finding must include a confidence level:

- **High**: Strong evidence of the issue, clear attack path or clear code quality problem
- **Medium**: Moderate evidence, attack path requires specific conditions
- **Low**: Weak evidence, attack path is theoretical or requires multiple unlikely conditions

---

## Counterexample Construction (MANDATORY)

**For every item classified as `potential-vulnerability`, you MUST construct a concrete counterexample.**

A counterexample must include:
1.  **Preconditions**: What state must the system be in?
2.  **Attack Sequence**: What specific inputs or operations trigger the issue?
3.  **Expected Outcome**: What bad thing happens?

**Example:**
```
Counterexample:
1. Preconditions: Contract has 1000 ETH balance, attacker has 0 ETH
2. Attack Sequence: 
   - Attacker calls withdraw() with amount = type(uint256).max
   - Integer overflow in balance check: balance + amount wraps to small value
   - Check passes: balance + amount < balance (due to overflow)
3. Expected Outcome: Attacker withdraws more than balance, contract drained
```

**If you cannot construct a plausible counterexample, DO NOT classify as `potential-vulnerability`.**

---

## Autonomous, Iterative Execution Doctrine

1.  **Automatic Input Discovery (Run 1 Only):** Scan `outputs/` for `02[ab]_*.json`, merge them, and create the initial queue.
2.  **State-Driven Batch Processing (All Runs):** Process a batch of 20 items from `outputs/03_STATE.json`.
3.  **Strict Output Formatting:** Use `audit_items` (for findings) and `verified_items` (for passes). **DO NOT** use `annotations`.
4.  **Robust State Update:** The state file **MUST** only be updated **AFTER** the partial output file has been successfully written.

---

## Output: `outputs/03_AUDITMAP_PARTIAL_<N>.json`

**Enhanced Requirements:**

```json
{
  "metadata": {
    "run_id": 5,
    "timestamp": "2025-12-23T19:30:00Z",
    "batch_size": 20,
    "processed_ids_start": "CHECK-ID-001",
    "processed_ids_end": "CHECK-ID-020"
  },
  "audit_items": [
    {
      "check_id": "...",
      "file": "...",
      "line": 123,
      "classification": "potential-vulnerability",
      "summary": "Unbounded loop in X function based on user-provided list length.",
      "attack_vector": "Resource Exhaustion",
      "severity": "High",
      "confidence": "High",
      "counterexample": {
        "preconditions": "Attacker controls input array length",
        "attack_sequence": [
          "1. Attacker submits transaction with 10000-element array",
          "2. Function iterates over entire array without gas checks",
          "3. Block processing exceeds gas limit"
        ],
        "expected_outcome": "DoS via block stuffing or node resource exhaustion"
      },
      "evidence": {
        "phase1_static": "Loop at line 123 iterates over user-controlled array",
        "phase2_verification": "No length check before loop, no gas metering inside loop"
      }
    }
  ],
  "verified_items": [
    {
      "check_id": "...",
      "classification": "PASS",
      "evidence": {
        "source_file": "...",
        "line_range": "...",
        "guard_identified": "require(amount <= balance) at line 45 prevents underflow",
        "analysis": "..."
      }
    }
  ],
  "summary": {
    "total_processed": 20,
    "passed": 15,
    "potential_vulnerabilities": 2,
    "code_quality_issues": 1,
    "needs_verification": 1,
    "audit_gaps": 1
  }
}
```

**Mandatory Fields:**
- `attack_vector`: MUST be one of the 5 specified vectors (no "Unknown")
- `severity`: MUST be "Critical", "High", "Medium", or "Low" (no "Unknown")
- `confidence`: MUST be "High", "Medium", or "Low"
- `classification`: MUST be one of the 4 categories
- `counterexample`: MUST be present for `potential-vulnerability` classification

---

## Procedure (Step-by-step for one autonomous run)

**CRITICAL: Follow this exact order to prevent data loss**

### **Step 1: Preflight & State Management**

1. Check if `outputs/03_STATE.json` exists.
2. **If it does NOT exist (first run):**
   - Scan `outputs/` for all files matching `02*.json` or `02[ab]_*.json`
   - Read all these files and extract all checklist items
   - Merge them into a single list of `unprocessed_checklist_ids`
   - Create initial state object and write to `outputs/03_STATE.json`
3. **If it DOES exist:**
   - Load `outputs/03_STATE.json`
   - Read the `unprocessed_checklist_ids` array
4. Extract the first **20 items** (or remaining items if fewer than 20) as your `current_batch`
5. Calculate `run_number` from existing PARTIAL files or state metadata

### **Step 2: Execute Three-Phase Analysis**

For each `check_id` in your `current_batch`:

**Phase 1: Static Analysis**
1. Map the predicate to specific code locations
2. Perform static detection of the property
3. Analyze data flow
4. Analyze call graph

**Phase 2: Counterexample Construction (NEW)**
1. **Attempt to construct a concrete counterexample**
   - Define preconditions
   - Define attack sequence
   - Define expected outcome
2. If a plausible counterexample can be constructed, proceed to Phase 3
3. If no plausible counterexample can be constructed, classify as PASS

**Phase 3: Guard/Invariant Search**
1. Search for guards that would prevent the counterexample
2. Search for invariants that make the counterexample impossible
3. If definitive guards exist → PASS
4. If no definitive guards exist → Finding (with appropriate classification)

**Phase 4: Classification Decision**
1. If counterexample exists AND no guards → `potential-vulnerability`
2. If code has issues but no exploitability → `code-quality-issue`
3. If static analysis is insufficient → `needs-verification`
4. If issue is observability-related → `audit-gap`
5. If guards exist or no counterexample → PASS

**Phase 5: Confidence Assessment**
1. Evaluate the strength of evidence
2. Assign confidence level (High/Medium/Low)

### **Step 3: Write Output File (DO THIS FIRST)**

**THIS STEP MUST HAPPEN BEFORE STEP 4**

1. Construct the complete JSON output object
2. **Write this JSON to `outputs/03_AUDITMAP_PARTIAL_<RUN_NUMBER>.json`**
3. Verify the file was written successfully

### **Step 4: Update State File (DO THIS LAST)**

**ONLY PROCEED TO THIS STEP AFTER STEP 3 COMPLETES SUCCESSFULLY**

1. Load the current `outputs/03_STATE.json`
2. Remove all items in `current_batch` from `unprocessed_checklist_ids`
3. Update metadata
4. **Overwrite `outputs/03_STATE.json` with the updated state**

---

## Enhanced Decision Tree

```
For each checklist item:

1. Can I construct a plausible counterexample?
   ├─ NO → Search for positive evidence of safety
   │        ├─ Found → PASS (verified_items)
   │        └─ Not Found → PASS with note (verified_items)
   │
   └─ YES → Search for guards/invariants
            ├─ Definitive guard found → PASS (verified_items)
            │
            └─ No definitive guard → Classify the finding:
                ├─ Exploitable? → potential-vulnerability
                ├─ Code quality only? → code-quality-issue
                ├─ Need dynamic test? → needs-verification
                └─ Observability gap? → audit-gap
```

---

## Quality Requirements

### For `audit_items` with `potential-vulnerability`:
- MUST have a concrete counterexample with all three components
- MUST have High or Medium confidence (Low confidence should be `needs-verification`)
- MUST reference specific code locations
- MUST explain why no guard exists

### For `audit_items` with `code-quality-issue`:
- MUST explain the code quality problem
- MUST explain why it's not exploitable
- SHOULD suggest improvement

### For `audit_items` with `needs-verification`:
- MUST explain why static analysis is insufficient
- MUST suggest what type of verification is needed (dynamic testing, formal proof, manual review)

### For `verified_items`:
- MUST identify the specific guard or invariant
- MUST explain why the counterexample is impossible

---

## Self-Check Before Completion

Before finishing each run, verify:
- [ ] All 20 items in `current_batch` have been processed
- [ ] Each item is in either `audit_items` or `verified_items` (not both, not neither)
- [ ] All `potential-vulnerability` items have concrete counterexamples
- [ ] All items have valid `attack_vector`, `severity`, `confidence`, and `classification`
- [ ] No "Unknown" values in any field
- [ ] Output file `03_AUDITMAP_PARTIAL_<N>.json` has been written
- [ ] State file `03_STATE.json` has been updated AFTER output file
- [ ] Summary counts match the actual items

---

## Examples

### Example 1: Potential Vulnerability

```json
{
  "check_id": "CHECK-REENTRANCY-001",
  "file": "contracts/Vault.sol",
  "line": 45,
  "classification": "potential-vulnerability",
  "summary": "External call before state update allows reentrancy",
  "attack_vector": "State Transition Violation",
  "severity": "Critical",
  "confidence": "High",
  "counterexample": {
    "preconditions": "Attacker deploys malicious contract with fallback function",
    "attack_sequence": [
      "1. Attacker calls withdraw(100 ETH)",
      "2. Line 45: contract sends ETH to attacker",
      "3. Attacker's fallback calls withdraw(100 ETH) again",
      "4. Balance not yet updated, check passes",
      "5. Repeat until drained"
    ],
    "expected_outcome": "Complete drainage of contract balance"
  },
  "evidence": {
    "phase1_static": "External call at line 45, balance update at line 48",
    "phase2_verification": "No reentrancy guard, no checks-effects-interactions pattern"
  }
}
```

### Example 2: Code Quality Issue

```json
{
  "check_id": "CHECK-GAS-PATTERN-001",
  "file": "core/vm/interpreter.go",
  "line": 200,
  "classification": "code-quality-issue",
  "summary": "Inconsistent gas handling: direct subtraction vs UseGas method",
  "attack_vector": "Faulty Error Handling",
  "severity": "Low",
  "confidence": "High",
  "counterexample": null,
  "evidence": {
    "phase1_static": "Line 200 uses direct subtraction, line 179 uses UseGas()",
    "phase2_verification": "Both patterns are functionally safe but inconsistent. Direct subtraction bypasses tracing hooks in non-debug mode."
  },
  "recommendation": "Standardize on one pattern or document why both are needed"
}
```

### Example 3: Needs Verification

```json
{
  "check_id": "CHECK-CRYPTO-001",
  "file": "crypto/bls12381/bls12_381.go",
  "line": 156,
  "classification": "needs-verification",
  "summary": "BLS signature verification implementation requires formal verification",
  "attack_vector": "Input Validation Bypass",
  "severity": "High",
  "confidence": "Medium",
  "counterexample": {
    "preconditions": "Attacker crafts malformed BLS signature",
    "attack_sequence": [
      "1. Attacker submits signature with invalid point encoding",
      "2. Verification may accept invalid signature due to edge case",
      "3. Invalid block accepted"
    ],
    "expected_outcome": "Consensus failure or invalid state acceptance"
  },
  "evidence": {
    "phase1_static": "Complex cryptographic implementation at line 156",
    "phase2_verification": "Static analysis cannot verify cryptographic correctness. Requires: (1) Formal verification of implementation against spec, (2) Fuzzing with invalid inputs, (3) Test vectors from EIP"
  },
  "verification_required": "Formal proof or extensive fuzzing"
}
```

---

## Notes on Improvement

This improved version addresses the key issues:

1. **Reduces False Positives**: Mandatory counterexample construction ensures findings are concrete
2. **Better Classification**: Four categories instead of binary, reducing ambiguity
3. **Confidence Levels**: Allows expressing uncertainty without rejecting findings
4. **Code Quality Separation**: Distinguishes security issues from maintainability issues
5. **Clearer Criteria**: Decision tree and examples guide consistent classification
6. **Fixed Output Bug**: State file updated after output file to prevent data loss

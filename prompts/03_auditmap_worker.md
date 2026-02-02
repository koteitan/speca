
---
Description: [PARALLEL WORKER] Comprehensive static audit with vulnerability discovery using formal predicates, attack vector analysis, mandatory counterexample construction, and robust batch processing.
Usage: `/03_auditmap_worker WORKER_ID=... QUEUE_FILE=... [TIMESTAMP=...] [ITERATION=...]`
Example: `/03_auditmap_worker WORKER_ID=0 QUEUE_FILE=outputs/03_QUEUE_0.json TIMESTAMP=1700000000 ITERATION=1`
Language: English only.
Execution hint: This is a worker prompt for parallel execution. Called by run_worker.py.
---

**Core Doctrine: Formal Static Verification & Vulnerability Discovery**

This is a **parallel worker** for the static audit phase. Your mission is to perform a comprehensive **static audit** with a primary focus on **discovering potential vulnerabilities**. You will not execute code. Each checklist item is a formal **Predicate** to be verified against a specific set of attack vectors.

## Worker Configuration

This is **parallel worker `WORKER_ID`**. You have a dedicated queue file that only you read from and write to.

- **`WORKER_ID`**: The numeric ID of this worker (0, 1, 2, ...)
- **`QUEUE_FILE`**: Path to this worker's queue file (e.g., `outputs/03_QUEUE_0.json`)
- **`TIMESTAMP`**: Unix timestamp for this iteration (used in output naming)
- **`ITERATION`**: The current iteration number for this worker

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

**FOR EVERY CHECKLIST ITEM, YOU MUST ANALYZE THE CODE THROUGH ALL FIVE ATTACK VECTORS.**

**DO NOT SKIP ANY VECTOR. EACH VECTOR MUST BE EXPLICITLY ANALYZED.**

1.  **Input Validation Bypass**: Can trusted or untrusted external inputs (RPC, P2P, CL) reach sensitive logic without proper, strict validation? Look for missing checks for size, range, type, or format. Assume inputs are malicious. Consider: boundary values, type confusion, encoding issues, malformed data.

2.  **State Transition Violation**: Can a critical action be performed without the system being in the correct prerequisite state? (e.g., processing a block before syncing is complete). Look for missing state checks. Consider: TOCTOU (Time-of-Check-Time-of-Use), reentrancy, out-of-order execution.

3.  **Resource Exhaustion (DoS)**: Can a seemingly valid input trigger an unexpectedly expensive operation (computation, memory, storage)? Can this be repeated to degrade or halt the service? Look for loops with unbounded iterations or large data allocations based on input. Consider: algorithmic complexity attacks, memory bombs, disk exhaustion.

4.  **Faulty Error Handling**: If an error occurs, does the system fail safely? Or can it lead to a corrupted state, an information leak, or an incorrect return value that downstream components might misinterpret? Consider: panic recovery, error propagation, partial state updates, information disclosure in error messages.

5.  **Race Conditions & Concurrency**: Could multiple, simultaneous operations on shared data lead to an inconsistent or insecure state? Look for shared maps, slices, or state variables that are accessed without proper locking. Consider: read-modify-write races, double-checked locking, channel races.

---

## Classification System

Each finding must be classified into ONE of these categories:

1.  **potential-vulnerability**: A plausible attack path exists with no definitive guard identified. Requires investigation.
2.  **code-quality-issue**: Not a security vulnerability, but represents poor coding practices, inconsistency, or maintainability concerns that should be addressed.
3.  **needs-verification**: The security property cannot be fully verified through static analysis alone. Requires dynamic testing, formal verification, or manual code review.
4.  **audit-gap**: A gap in observability, logging, or audit trails that doesn't directly lead to exploitation but hinders security monitoring.

**Decision Criteria:**

- Use `potential-vulnerability` ONLY if you can construct a plausible counterexample (attack scenario) AND cannot find a definitive guard
- Use `code-quality-issue` if the code is safe but has inconsistencies or poor patterns
- Use `needs-verification` if static analysis is insufficient (e.g., complex state machines, cryptographic implementations)
- Use `audit-gap` if the issue is about observability, not exploitability

---

## Confidence Level

Each finding must include a confidence level:

- **High**: Strong evidence of the issue, clear attack path or clear code quality problem
- **Medium**: Moderate evidence, attack path requires specific conditions
- **Low**: Weak evidence, attack path is theoretical or requires multiple unlikely conditions

**IMPORTANT**: If confidence is Low for a `potential-vulnerability`, reconsider classifying it as `needs-verification` instead.

---

## Counterexample Construction (MANDATORY)

**For every item, you MUST attempt to construct a concrete counterexample.**

A counterexample must include:
1.  **Preconditions**: What state must the system be in? Be specific.
2.  **Attack Sequence**: What specific inputs or operations trigger the issue? Provide step-by-step actions.
3.  **Expected Outcome**: What bad thing happens? Quantify the impact if possible.

**Minimum Requirements for Counterexample Attempts:**

You MUST try at least the following types of counterexamples:

- **Boundary values**: MaxUint, MinInt, zero, empty strings, null pointers
- **Type confusion**: Unexpected types, malformed data structures
- **Timing attacks**: TOCTOU, race conditions, reentrancy
- **Combination attacks**: Multiple operations in sequence or parallel
- **Edge cases**: Off-by-one, overflow/underflow, uninitialized state

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

**If you cannot construct a plausible counterexample after trying all types above, classify as PASS (verified_items).**

---

## Guard/Invariant Evaluation (STRICT CRITERIA)

When evaluating guards, you MUST verify:

1. **Implementation correctness**: Does the guard actually work as intended?
2. **Completeness**: Does the guard cover all attack paths?
3. **Bypass resistance**: Can the guard be circumvented?
4. **Error handling**: What happens if the guard fails?

**A guard is "STRONG" ONLY if:**
- It is mathematically or logically impossible to bypass
- It has been verified in the actual implementation (not just assumed)
- It handles all error cases correctly
- It cannot be disabled or circumvented

**DO NOT classify a guard as STRONG just because it exists.**

---

## Worker Execution Logic

### **Task 1: Read Worker Queue**

1. Read the worker queue file `QUEUE_FILE`
2. Get the list of `items` (all assigned checklist IDs)
3. Get the list of `processed` (already done checklist IDs)
4. Calculate remaining: checklist IDs in `items` but not in `processed`
5. If no remaining items, terminate successfully
6. Take **first 20 items** as your `current_batch`

### **Task 2: Execute Five-Phase Analysis**

For each `check_id` in your `current_batch` (EXACTLY 20 items or fewer):

**Phase 1: Static Analysis (ALL 5 ATTACK VECTORS)**
1. Map the predicate to specific code locations
2. **FOR EACH OF THE 5 ATTACK VECTORS:**
   - Analyze the code through that vector's lens
   - Document findings or lack thereof
   - **DO NOT skip any vector**
3. Perform data flow analysis
4. Perform call graph analysis

**Phase 2: Counterexample Construction (MANDATORY)**
1. **Attempt to construct concrete counterexamples for ALL attack vectors**
   - Boundary values (MaxUint, 0, empty, null)
   - Type confusion (unexpected types, malformed data)
   - Timing attacks (TOCTOU, reentrancy)
   - Combination attacks (multiple operations)
   - Edge cases (off-by-one, overflow, uninitialized)
2. **Document ALL attempts** (successful or not)
3. If at least one plausible counterexample can be constructed, proceed to Phase 3
4. If NO plausible counterexample can be constructed after trying all types, classify as PASS

**Phase 3: Guard/Invariant Search (STRICT EVALUATION)**
1. Search for guards that would prevent each counterexample
2. **For each guard found:**
   - Verify its implementation (not just its existence)
   - Check completeness (does it cover all paths?)
   - Test bypass resistance (can it be circumvented?)
   - Verify error handling (what if it fails?)
3. Classify guard strength:
   - **STRONG**: Mathematically/logically impossible to bypass, verified in implementation
   - **MODERATE**: Effective but has edge cases or assumptions
   - **WEAK**: Easily bypassed or incomplete
4. If definitive STRONG guards exist for all counterexamples → PASS
5. If no definitive guards exist or guards are WEAK/MODERATE → Finding (proceed to Phase 4)

**Phase 4: Classification Decision**
1. If counterexample exists AND no STRONG guards → `potential-vulnerability`
2. If code has issues but no exploitability → `code-quality-issue`
3. If static analysis is insufficient → `needs-verification`
4. If issue is observability-related → `audit-gap`
5. If STRONG guards exist or no counterexample → PASS

**Phase 5: Confidence Assessment**
1. Evaluate the strength of evidence
2. Assign confidence level (High/Medium/Low)
3. If Low confidence for `potential-vulnerability`, reconsider as `needs-verification`

### **Task 3: Write Outputs**

**THIS STEP MUST HAPPEN BEFORE UPDATING THE QUEUE FILE**

1. **Generate Partial Audit Map:**
   * Create `outputs/03_AUDITMAP_PARTIAL_W{WORKER_ID}_{TIMESTAMP}_{ITERATION}.json`
   * Set `metadata.batch_number` to `ITERATION`
   * Verify that:
     - All items in batch are included
     - Each item is in either `audit_items` or `verified_items` (not both, not neither)
     - All `potential-vulnerability` items have concrete counterexamples
     - All items have `counterexample_attempts` documented
     - No "Unknown" values in any field
     - Summary counts match the actual items

2. **Update Worker Queue File:**
   * Add ALL processed items to the `processed` array
   * **IMPORTANT:** Only update YOUR queue file, not others
   * Overwrite `QUEUE_FILE`

---

## Output Format

**Partial Audit Map:** `outputs/03_AUDITMAP_PARTIAL_W{WORKER_ID}_{TIMESTAMP}_{ITERATION}.json`
```json
{
  "metadata": {
    "worker_id": 0,
    "batch_number": 1,
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
        "phase1_static": "Loop at line 123 iterates over user-controlled array. All 5 attack vectors analyzed.",
        "phase2_counterexample_attempts": "Tried: boundary (0, MaxInt), combination (nested calls), edge case (uninitialized)",
        "phase3_guard_search": "No length check before loop, no gas metering inside loop"
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
        "counterexample_attempts": "Tried: overflow (MaxUint), underflow (0), TOCTOU (concurrent access)",
        "guard_identified": "require(amount <= balance) at line 45 prevents underflow. Guard verified in implementation: SubBalance() returns error on underflow.",
        "guard_strength": "STRONG - mathematically impossible to bypass",
        "analysis": "All 5 attack vectors analyzed. No exploitable path found."
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
- `counterexample_attempts`: MUST be present for ALL items (audit_items AND verified_items)

---

## Enhanced Decision Tree

```
For each checklist item:

1. Analyze through ALL 5 attack vectors (mandatory)

2. Attempt to construct counterexamples for each vector:
   - Boundary values
   - Type confusion
   - Timing attacks
   - Combination attacks
   - Edge cases

3. Can I construct at least one plausible counterexample?
   ├─ NO → Search for positive evidence of safety
   │        ├─ Found → PASS (verified_items) with documented attempts
   │        └─ Not Found → PASS with note (verified_items) with documented attempts
   │
   └─ YES → Search for guards/invariants (STRICT evaluation)
            ├─ STRONG guard found (verified, complete, bypass-resistant) → PASS (verified_items)
            │
            └─ No STRONG guard → Classify the finding:
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
- MUST explain why no STRONG guard exists
- MUST document all counterexample attempts

### For `audit_items` with `code-quality-issue`:
- MUST explain the code quality problem
- MUST explain why it's not exploitable
- SHOULD suggest improvement
- MUST document counterexample attempts (to prove non-exploitability)

### For `audit_items` with `needs-verification`:
- MUST explain why static analysis is insufficient
- MUST suggest what type of verification is needed (dynamic testing, formal proof, manual review)
- MUST document counterexample attempts (to show what couldn't be verified)

### For `verified_items`:
- MUST identify the specific guard or invariant
- MUST verify the guard's implementation (not just existence)
- MUST explain why the counterexample is impossible
- MUST document all counterexample attempts (to show thoroughness)

---

## Self-Check Before Completion

Before finishing each batch, verify:
- [ ] Processed EXACTLY 20 items (or remaining items if fewer than 20)
- [ ] Did NOT process more than 20 items
- [ ] All 5 attack vectors analyzed for each item
- [ ] All items have documented counterexample attempts
- [ ] Each item is in either `audit_items` or `verified_items` (not both, not neither)
- [ ] All `potential-vulnerability` items have concrete counterexamples
- [ ] All items have valid `attack_vector`, `severity`, `confidence`, and `classification`
- [ ] No "Unknown" values in any field
- [ ] All guards have been verified (not just assumed)
- [ ] Output file has been written
- [ ] Worker queue file has been updated AFTER output file
- [ ] Summary counts match the actual items

---

## Examples

### Example 1: Potential Vulnerability (with documented attempts)

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
    "phase1_static": "External call at line 45, balance update at line 48. All 5 attack vectors analyzed.",
    "phase2_counterexample_attempts": "Tried: reentrancy (successful), TOCTOU (successful), overflow (N/A), boundary (N/A), combination (successful - reentrancy + gas manipulation)",
    "phase3_guard_search": "No reentrancy guard found. No checks-effects-interactions pattern. Mutex not used. Guard strength: NONE"
  }
}
```

### Example 2: Verified Item (with documented attempts)

```json
{
  "check_id": "CHECK-UNDERFLOW-001",
  "classification": "PASS",
  "evidence": {
    "source_file": "contracts/Token.sol",
    "line_range": "45-50",
    "counterexample_attempts": "Tried: underflow (amount > balance), overflow (MaxUint), TOCTOU (concurrent transfer), reentrancy (transfer in callback), combination (multiple transfers)",
    "guard_identified": "require(balance >= amount) at line 47 prevents underflow. Verified in implementation: SafeMath.sub() reverts on underflow.",
    "guard_strength": "STRONG - mathematically impossible to bypass. Solidity 0.8+ has built-in overflow protection.",
    "guard_completeness": "Covers all paths. No way to bypass the check.",
    "guard_error_handling": "Reverts transaction on failure, no partial state update.",
    "analysis": "All 5 attack vectors analyzed. No exploitable path found."
  }
}
```

### Example 3: Needs Verification (with documented attempts)

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
      "2. Verification may accept invalid signature due to edge case in point decompression",
      "3. Invalid block accepted"
    ],
    "expected_outcome": "Consensus failure or invalid state acceptance"
  },
  "evidence": {
    "phase1_static": "Complex cryptographic implementation at line 156. All 5 attack vectors analyzed.",
    "phase2_counterexample_attempts": "Tried: invalid encoding (possible), boundary values (possible), type confusion (possible), malformed data (possible). Cannot verify correctness statically.",
    "phase3_guard_search": "Input validation exists but cannot verify cryptographic correctness through static analysis.",
    "verification_required": "Formal proof or extensive fuzzing. Requires: (1) Formal verification of implementation against spec, (2) Fuzzing with invalid inputs, (3) Test vectors from EIP"
  }
}
```

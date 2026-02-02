
---
Description: [PARALLEL WORKER] Rigorous, neutral formal review of audit findings from a worker-specific queue.
Usage: `/04_review_worker WORKER_ID=... QUEUE_FILE=... [TIMESTAMP=...] [ITERATION=...]`
Example: `/04_review_worker WORKER_ID=0 QUEUE_FILE=outputs/04_QUEUE_0.json TIMESTAMP=1700000000 ITERATION=1`
Language: English only.
Execution hint: This is a worker prompt for parallel execution. Called by run_worker.py.
---

**Core Doctrine: Rigorous, Neutral Formal Review**

This is a **parallel worker** for the audit review phase. Your mission is to act as a **neutral, rigorous formal verification expert**. For every `audit_item` presented, you must **objectively evaluate** whether it represents a genuine vulnerability, a false positive, or falls into another category. You must not have a default assumption in either direction.

## Worker Configuration

This is **parallel worker `WORKER_ID`**. You have a dedicated queue file that only you read from and write to.

- **`WORKER_ID`**: The numeric ID of this worker (0, 1, 2, ...)
- **`QUEUE_FILE`**: Path to this worker's queue file (e.g., `outputs/04_QUEUE_0.json`)
- **`TIMESTAMP`**: Unix timestamp for this iteration (used in output naming)
- **`ITERATION`**: The current iteration number for this worker

---

## Formal Verification Mindset (MANDATORY)

1.  **Counterexample Evaluation is Primary**: First, evaluate the counterexample provided by the 03 stage. Is it plausible? Can it actually occur in practice?
2.  **Guard/Invariant Search is Secondary**: If the counterexample is plausible, search for guards or invariants that would prevent it. Be thorough but realistic.
3.  **Evidence-Based Judgment**: Every verdict must be supported by concrete evidence from the codebase. Speculation is not acceptable.
4.  **Traceability is Non-Negotiable**: Every claim must be backed by a `proof_trace`—a sequence of code locations (`file:line`) that logically supports your conclusion.

---

## Verdict Categories

Each reviewed item must receive ONE of these verdicts:

### 1. **CONFIRMED_VULNERABILITY**
- The counterexample is plausible AND no definitive guard exists
- The issue can lead to security compromise (loss of funds, DoS, unauthorized access, etc.)
- Requires immediate remediation

### 2. **LIKELY_VULNERABILITY**
- The counterexample is plausible but requires specific conditions
- Guards exist but may be insufficient or bypassable
- Requires deeper investigation or dynamic testing to confirm

### 3. **VERIFIED_SAFE**
- A definitive guard or invariant makes the counterexample impossible
- The security property is explicitly enforced in the code
- No remediation needed

### 4. **FALSE_POSITIVE**
- The counterexample is not plausible (based on incorrect assumptions)
- OR the concern is not actually a security issue
- No remediation needed

### 5. **CODE_QUALITY_ISSUE**
- The issue is real but does not lead to exploitability
- Represents poor coding practices, inconsistency, or maintainability concerns
- Should be addressed but not a security priority

### 6. **REQUIRES_MANUAL_REVIEW**
- Static analysis is insufficient to make a determination
- Requires dynamic testing, formal verification, or expert domain knowledge
- Human review is necessary

---

## Verdict Decision Criteria

Use this decision tree for every item:

```
1. Evaluate the counterexample from 03 stage:
   ├─ Is it plausible?
   │  ├─ NO → FALSE_POSITIVE
   │  └─ YES → Continue to step 2
   │
2. Search for guards/invariants:
   ├─ Definitive guard found?
   │  ├─ YES → VERIFIED_SAFE
   │  └─ NO or PARTIAL → Continue to step 3
   │
3. Assess exploitability:
   ├─ Can lead to security compromise?
   │  ├─ YES, definitely → CONFIRMED_VULNERABILITY
   │  ├─ YES, but requires specific conditions → LIKELY_VULNERABILITY
   │  ├─ NO, but code quality issue → CODE_QUALITY_ISSUE
   │  └─ UNCERTAIN → Continue to step 4
   │
4. Can static analysis determine the answer?
   ├─ YES → Re-evaluate steps 1-3
   └─ NO → REQUIRES_MANUAL_REVIEW
```

---

## Evidence Standards

### For CONFIRMED_VULNERABILITY:
- MUST demonstrate that the counterexample is realistic
- MUST show that no effective guard exists
- MUST explain the security impact
- SHOULD provide a proof-of-concept scenario

### For LIKELY_VULNERABILITY:
- MUST demonstrate that the counterexample is possible under certain conditions
- MUST show that guards are insufficient or conditional
- MUST explain what conditions enable the vulnerability
- SHOULD suggest what testing would confirm it

### For VERIFIED_SAFE:
- MUST identify the specific guard or invariant
- MUST show how it prevents the counterexample
- MUST verify the guard cannot be bypassed
- SHOULD reference test coverage if available

### For FALSE_POSITIVE:
- MUST explain why the counterexample is not plausible
- OR explain why the concern is not a security issue
- MUST provide concrete evidence from the code

### For CODE_QUALITY_ISSUE:
- MUST explain the code quality problem
- MUST explain why it's not exploitable
- SHOULD suggest improvements

### For REQUIRES_MANUAL_REVIEW:
- MUST explain why static analysis is insufficient
- MUST specify what type of review is needed
- SHOULD provide guidance for the manual reviewer

---

## Worker Execution Logic

### **Task 1: Read Worker Queue**

1. Read the worker queue file `QUEUE_FILE`
2. Get the list of `items` (all assigned audit item IDs)
3. Get the list of `processed` (already done audit item IDs)
4. Calculate remaining: audit item IDs in `items` but not in `processed`
5. If no remaining items, terminate successfully
6. Take **first 10 items** as your `current_batch` (reduced from 20 for deeper analysis)

### **Task 2: Execute Formal Review**

For each `item` in your `current_batch`:

**Phase 1: Counterexample Evaluation**
1. Read the counterexample from the 03 stage
2. Evaluate its plausibility:
   - Are the preconditions realistic?
   - Is the attack sequence feasible?
   - Would the expected outcome actually occur?
3. Rate plausibility: High / Medium / Low

**Phase 2: Guard/Invariant Search**
1. Search for guards that would prevent the counterexample
2. For each guard found:
   - Document its location
   - Assess its effectiveness (Complete / Partial / Insufficient)
   - Determine if it can be bypassed
3. Document all guards in `guard_analysis`

**Phase 3: Exploitability Assessment**
1. If counterexample is plausible AND no effective guard:
   - Assess security impact (Critical / High / Medium / Low)
   - Assess exploitability (High / Medium / Low)
   - Consider: Is this a vulnerability or code quality issue?
2. If counterexample is plausible BUT effective guard exists:
   - Verdict: VERIFIED_SAFE
3. If counterexample is not plausible:
   - Verdict: FALSE_POSITIVE
   - Explain why

**Phase 4: Verdict Decision**
1. Apply the decision tree from the "Verdict Decision Criteria" section
2. Choose ONE verdict from the 6 categories
3. Ensure the verdict is supported by evidence

**Phase 5: Proof Trace Construction**
1. Build a logical sequence of code locations
2. Each entry should be `file:line - description`
3. The trace should tell a story that supports your verdict

**Phase 6: Generate Result**
1. Construct the `reviewed_item` object with all required fields
2. Store in memory

### **Task 3: Write Outputs**

**THIS STEP MUST HAPPEN BEFORE UPDATING THE QUEUE FILE**

1. **Generate Partial Review:**
   * Create `outputs/04_REVIEW_PARTIAL_W{WORKER_ID}_{TIMESTAMP}_{ITERATION}.json`
   * Set `metadata.batch_number` to `ITERATION`
   * Verify that all items in batch have been reviewed
   * Verify verdict counts in metadata match actual items

2. **Update Worker Queue File:**
   * Add ALL processed items to the `processed` array
   * **IMPORTANT:** Only update YOUR queue file, not others
   * Overwrite `QUEUE_FILE`

---

## Output Format

**Partial Review:** `outputs/04_REVIEW_PARTIAL_W{WORKER_ID}_{TIMESTAMP}_{ITERATION}.json`
```json
{
  "metadata": {
    "worker_id": 0,
    "batch_number": 1,
    "timestamp": "2025-12-24T00:00:00Z",
    "batch_size": 10,
    "items_reviewed": 10,
    "verdicts": {
      "CONFIRMED_VULNERABILITY": 1,
      "LIKELY_VULNERABILITY": 2,
      "VERIFIED_SAFE": 3,
      "FALSE_POSITIVE": 2,
      "CODE_QUALITY_ISSUE": 1,
      "REQUIRES_MANUAL_REVIEW": 1
    }
  },
  "reviewed_items": [
    {
      "original_item": {
        "check_id": "...",
        "file": "...",
        "line": 123,
        "classification": "potential-vulnerability",
        "summary": "...",
        "attack_vector": "...",
        "severity": "High",
        "confidence": "High",
        "counterexample": { ... }
      },
      "verdict": "CONFIRMED_VULNERABILITY",
      "security_impact": "Critical",
      "exploitability": "High",
      "reasoning": "The counterexample is realistic and demonstrates a clear attack path. The identified guard at line 85 is insufficient because it only checks X but not Y. An attacker can bypass it by...",
      "counterexample_evaluation": {
        "plausibility": "High",
        "assessment": "The attack sequence is realistic. Preconditions are easily achievable. The expected outcome matches the code behavior."
      },
      "guard_analysis": {
        "guards_found": [
          {
            "location": "contract.sol:85",
            "type": "require statement",
            "effectiveness": "Partial",
            "reason": "Only checks X, does not prevent Y"
          }
        ],
        "bypass_possible": true,
        "bypass_method": "Attacker can set Y to malicious value before calling function"
      },
      "proof_trace": [
        "contract.sol:152 - Vulnerable function entry",
        "contract.sol:85 - Insufficient guard (only checks X)",
        "contract.sol:160 - State modification before external call",
        "contract.sol:165 - External call allows reentrancy"
      ],
      "recommendation": "Add reentrancy guard or follow checks-effects-interactions pattern"
    }
  ]
}
```

---

## Quality Requirements

### Every reviewed_item MUST include:
- `original_item`: The complete audit item from 03 stage
- `verdict`: One of the 6 verdict categories
- `reasoning`: Detailed explanation (minimum 3 sentences)
- `counterexample_evaluation`: Assessment of the counterexample's plausibility
- `guard_analysis`: Documentation of guards found (or statement that none exist)
- `proof_trace`: Sequence of code locations supporting the verdict

### For CONFIRMED_VULNERABILITY and LIKELY_VULNERABILITY:
- MUST include `security_impact` (Critical/High/Medium/Low)
- MUST include `exploitability` (High/Medium/Low)
- MUST include `recommendation` for remediation
- SHOULD include `cve_reference` if applicable

### For VERIFIED_SAFE:
- MUST identify the specific guard or invariant
- MUST explain how it prevents the counterexample
- MUST verify the guard cannot be bypassed

### For FALSE_POSITIVE:
- MUST explain the flaw in the original analysis
- MUST provide concrete evidence

---

## Balanced Review Guidelines

### Avoid These Biases:

1. **False Positive Bias**: Don't assume everything is a false positive
2. **Confirmation Bias**: Don't only look for evidence supporting one verdict
3. **Availability Bias**: Don't over-weight recent or memorable vulnerabilities
4. **Complexity Bias**: Don't dismiss issues just because the code is complex

### Best Practices:

1. **Steel Man the Argument**: Consider the strongest version of the 03 stage's claim
2. **Devil's Advocate**: After reaching a verdict, argue against it to test robustness
3. **Multiple Perspectives**: Consider the issue from attacker, defender, and auditor perspectives
4. **Edge Cases**: Explicitly consider edge cases and boundary conditions
5. **Assume Malicious Input**: Always assume inputs are adversarially chosen

---

## Self-Check Before Completion

Before finishing each batch, verify:
- [ ] All 10 items in `current_batch` have been reviewed
- [ ] Each item has exactly ONE verdict from the 6 categories
- [ ] All verdicts are supported by concrete evidence
- [ ] All `proof_trace` entries reference actual code locations
- [ ] Counterexample evaluation is present for all items
- [ ] Guard analysis is present for all items
- [ ] Output file has been written
- [ ] Worker queue file has been updated AFTER output file
- [ ] Verdict counts in metadata match actual reviewed_items

---

## Examples

### Example 1: CONFIRMED_VULNERABILITY

```json
{
  "original_item": {
    "check_id": "CHECK-REENTRANCY-001",
    "file": "contracts/Vault.sol",
    "line": 45,
    "classification": "potential-vulnerability",
    "summary": "External call before state update allows reentrancy",
    "attack_vector": "State Transition Violation",
    "severity": "Critical",
    "confidence": "High",
    "counterexample": {
      "preconditions": "Attacker deploys malicious contract",
      "attack_sequence": ["1. Call withdraw()", "2. Reenter in fallback", "3. Drain funds"],
      "expected_outcome": "Complete drainage"
    }
  },
  "verdict": "CONFIRMED_VULNERABILITY",
  "security_impact": "Critical",
  "exploitability": "High",
  "reasoning": "The counterexample is realistic and demonstrates a classic reentrancy vulnerability. The external call at line 45 occurs before the balance update at line 48. No reentrancy guard exists. The checks-effects-interactions pattern is violated. An attacker can easily deploy a malicious contract with a fallback function that reenters withdraw().",
  "counterexample_evaluation": {
    "plausibility": "High",
    "assessment": "All preconditions are trivial to achieve. The attack sequence is standard reentrancy. The expected outcome is guaranteed by the code structure."
  },
  "guard_analysis": {
    "guards_found": [],
    "bypass_possible": true,
    "bypass_method": "No guard exists. Direct exploitation is possible."
  },
  "proof_trace": [
    "contracts/Vault.sol:42 - withdraw() function entry, no reentrancy guard",
    "contracts/Vault.sol:43 - require(balance[msg.sender] >= amount) - check passes on first call",
    "contracts/Vault.sol:45 - msg.sender.call{value: amount}() - external call before state update",
    "contracts/Vault.sol:48 - balance[msg.sender] -= amount - state update AFTER external call",
    "Attacker fallback - reenters withdraw(), balance still shows original value, check passes again"
  ],
  "recommendation": "Add nonReentrant modifier or move state update before external call"
}
```

### Example 2: VERIFIED_SAFE

```json
{
  "original_item": {
    "check_id": "CHECK-OVERFLOW-001",
    "file": "contracts/Token.sol",
    "line": 67,
    "classification": "potential-vulnerability",
    "summary": "Addition may overflow",
    "attack_vector": "Input Validation Bypass",
    "severity": "High",
    "confidence": "Medium",
    "counterexample": {
      "preconditions": "balance[user] = MAX_UINT - 1",
      "attack_sequence": ["1. Transfer 2 tokens", "2. Overflow to 1"],
      "expected_outcome": "Balance wraps around"
    }
  },
  "verdict": "VERIFIED_SAFE",
  "security_impact": "None",
  "exploitability": "None",
  "reasoning": "The counterexample would be valid in Solidity <0.8.0, but this contract uses Solidity 0.8.19 (verified at line 2). Solidity 0.8+ has built-in overflow protection that reverts on overflow. The addition at line 67 will automatically revert if it would overflow. No explicit check is needed.",
  "counterexample_evaluation": {
    "plausibility": "Low",
    "assessment": "The attack sequence assumes overflow is possible, but Solidity 0.8+ prevents this automatically."
  },
  "guard_analysis": {
    "guards_found": [
      {
        "location": "contracts/Token.sol:2",
        "type": "Solidity version",
        "effectiveness": "Complete",
        "reason": "pragma solidity ^0.8.19 provides automatic overflow protection"
      }
    ],
    "bypass_possible": false,
    "bypass_method": "None. Language-level protection cannot be bypassed."
  },
  "proof_trace": [
    "contracts/Token.sol:2 - pragma solidity ^0.8.19",
    "contracts/Token.sol:67 - balance[to] += amount",
    "Solidity 0.8+ documentation - automatic overflow/underflow checks",
    "If overflow occurs, transaction reverts automatically"
  ],
  "recommendation": "None. The code is safe."
}
```

### Example 3: CODE_QUALITY_ISSUE

```json
{
  "original_item": {
    "check_id": "CHECK-GAS-PATTERN-001",
    "file": "core/vm/interpreter.go",
    "line": 200,
    "classification": "code-quality-issue",
    "summary": "Inconsistent gas handling patterns",
    "attack_vector": "Faulty Error Handling",
    "severity": "Low",
    "confidence": "High",
    "counterexample": null
  },
  "verdict": "CODE_QUALITY_ISSUE",
  "security_impact": "None",
  "exploitability": "None",
  "reasoning": "The inconsistency between direct gas subtraction (line 200) and UseGas() method (line 179) is a code quality issue, not a security vulnerability. Both patterns are functionally equivalent for single-threaded execution. The direct pattern is used for performance in the hot interpreter loop. However, this inconsistency makes the code harder to audit and maintain.",
  "counterexample_evaluation": {
    "plausibility": "N/A",
    "assessment": "No counterexample provided. This is a code quality concern, not an exploitability concern."
  },
  "guard_analysis": {
    "guards_found": [
      {
        "location": "core/vm/interpreter.go:197",
        "type": "Underflow check",
        "effectiveness": "Complete",
        "reason": "if contract.Gas < cost { return ErrOutOfGas }"
      }
    ],
    "bypass_possible": false,
    "bypass_method": "Both patterns include underflow protection. No bypass possible."
  },
  "proof_trace": [
    "core/vm/interpreter.go:197-201 - Direct pattern with check",
    "core/vm/contract.go:129-138 - UseGas() method with same check",
    "core/vm/interpreter.go single-threaded - No race condition possible",
    "Both patterns are safe, just inconsistent"
  ],
  "recommendation": "Standardize on one pattern or add documentation explaining why both are needed. Consider adding a comment at line 200 explaining the performance optimization."
}
```

### Example 4: REQUIRES_MANUAL_REVIEW

```json
{
  "original_item": {
    "check_id": "CHECK-CRYPTO-001",
    "file": "crypto/bls12381/bls12_381.go",
    "line": 156,
    "classification": "needs-verification",
    "summary": "BLS signature verification requires formal verification",
    "attack_vector": "Input Validation Bypass",
    "severity": "High",
    "confidence": "Medium",
    "counterexample": {
      "preconditions": "Attacker crafts malformed signature",
      "attack_sequence": ["1. Submit invalid point encoding", "2. Verification accepts", "3. Invalid block accepted"],
      "expected_outcome": "Consensus failure"
    }
  },
  "verdict": "REQUIRES_MANUAL_REVIEW",
  "security_impact": "Potentially High",
  "exploitability": "Unknown",
  "reasoning": "Static analysis cannot verify the correctness of cryptographic implementations. The BLS signature verification at line 156 involves complex elliptic curve operations. While the code appears to follow the specification, subtle implementation errors in cryptographic code can lead to signature forgery or invalid signature acceptance. This requires specialized review.",
  "counterexample_evaluation": {
    "plausibility": "Unknown",
    "assessment": "The counterexample is theoretically possible if the implementation has bugs, but static analysis cannot determine if such bugs exist in cryptographic code."
  },
  "guard_analysis": {
    "guards_found": [
      {
        "location": "crypto/bls12381/bls12_381.go:145-160",
        "type": "Point validation",
        "effectiveness": "Unknown",
        "reason": "Implementation appears correct but requires expert review"
      }
    ],
    "bypass_possible": "Unknown",
    "bypass_method": "Cannot be determined through static analysis"
  },
  "proof_trace": [
    "crypto/bls12381/bls12_381.go:156 - Signature verification implementation",
    "crypto/bls12381/bls12_381.go:145 - Point deserialization",
    "crypto/bls12381/bls12_381.go:160 - Pairing check",
    "EIP-2537 specification - BLS12-381 requirements"
  ],
  "recommendation": "Requires: (1) Formal verification against EIP-2537 spec, (2) Cryptographic expert review, (3) Fuzzing with invalid inputs, (4) Test vectors from reference implementation",
  "manual_review_type": "Cryptographic expert review + formal verification"
}
```

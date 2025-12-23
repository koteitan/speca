
---
Description: This version introduces a mandatory **Attack Vector Analysis** framework to shift the focus from simple verification to proactive vulnerability discovery. It builds upon the successful iterative and autonomous execution logic of V2.
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

**FOR EVERY CHECKLIST ITEM, YOU MUST ANALYZE THE CODE THROUGH THE LENS OF THESE ATTACK VECTORS. If any vector is plausible, you MUST classify the item as `needs-investigation` and place it in `audit_items`.**

1.  **Input Validation Bypass**: Can trusted or untrusted external inputs (RPC, P2P, CL) reach sensitive logic without proper, strict validation? Look for missing checks for size, range, type, or format. Assume inputs are malicious.
2.  **State Transition Violation**: Can a critical action be performed without the system being in the correct prerequisite state? (e.g., processing a block before syncing is complete). Look for missing state checks.
3.  **Resource Exhaustion (DoS)**: Can a seemingly valid input trigger an unexpectedly expensive operation (computation, memory, storage)? Can this be repeated to degrade or halt the service? Look for loops with unbounded iterations or large data allocations based on input.
4.  **Faulty Error Handling**: If an error occurs, does the system fail safely? Or can it lead to a corrupted state, an information leak, or an incorrect return value that downstream components might misinterpret?
5.  **Race Conditions & Concurrency**: Could multiple, simultaneous operations on shared data lead to an inconsistent or insecure state? Look for shared maps, slices, or state variables that are accessed without proper locking.

---

## Autonomous, Iterative Execution Doctrine

1.  **Automatic Input Discovery (Run 1 Only):** Scan `outputs/` for `02[ab]_*.json`, merge them, and create the initial queue.
2.  **State-Driven Batch Processing (All Runs):** Process a batch of 20 items from `outputs/03_STATE.json`.
3.  **Strict Output Formatting:** Use `audit_items` (for findings) and `verified_items` (for passes). **DO NOT** use `annotations`.
4.  **State Update and Continuation:** Correctly update `outputs/03_STATE.json` with the remaining items.

---

## Output: `outputs/03_AUDITMAP_PARTIAL_<N>.json`

```json
{
  "metadata": { ... },
  "audit_items": [
    {
      "check_id": "...",
      "file": "...",
      "line": 123,
      "classification": "needs-investigation",
      "summary": "Potential DoS vector: Unbounded loop in X function based on user-provided list length.",
      "attack_vector": "Resource Exhaustion"
    }
  ],
  "verified_items": [ ... ]
}
```

---

## Procedure (Step-by-step for one autonomous run)

1.  **Preflight & State Management**
    -   Load or create the `unprocessed_checklist_ids` queue, same as V2.
    -   Define your `current_batch`.

2.  **Execute Two-Phase Static Verification + Attack Vector Analysis**
    -   For each `check_id` in your `current_batch`:
        -   First, perform the **Two-Phase Static Verification** (Static Analysis + Evidence Verification).
        -   Second, **critically re-evaluate** your findings using the **Attack Vector Analysis** framework.
        -   Based on the Attack Vector Analysis, make a final decision: is it a `PASS` (`verified_items`) or a `FINDING` (`audit_items`)?
        -   Generate a list of these final results in memory.

3.  **Emit Final JSON**
    -   Iterate through your in-memory results.
    -   Sort each result into the `audit_items` or `verified_items` list.
    -   Construct the final JSON output, including the `metadata` and `next_state`.
    -   Write the result to `outputs/03_AUDITMAP_PARTIAL_<RUN_NUMBER>.json`.
    -   Overwrite `outputs/03_STATE.json` with the `next_state` object.

---

## Two-Phase Static Verification Procedure

### **Phase 1: Static Analysis**
1.  **Predicate Mapping**
2.  **Static Detection**
3.  **Data Flow Analysis**
4.  **Call Graph Analysis**

### **Phase 2: Evidence Verification**
1.  **Evidence Existence**
2.  **Evidence Correlation**

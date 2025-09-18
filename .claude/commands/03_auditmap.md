---

**Description:** Audit **local implementation** corresponding to one or more `normative_spec.id` values (from `security-agent/outputs/01_SPEC.json`). Use `02_ORDER.json` to drive the **exact function order**. Add inline `@audit / @audit-ok` comments; produce/merge `03_AUDITMAP.json`; increment `review_count` in `02_ORDER.json`.
**Strict rules:**
• **Workspace only** — never reference spec repos (`execution-specs`, `consensus-specs`) inside findings.
• **Fusaka scope only** — Osaka (EL) normatives map to **local EL code**; Fulu (CL) normatives map to **local CL code**.

**Usage:** `/02_order <NORMATIVE_IDS>`
**Arguments:**

* **NORMATIVE\_IDS**: Comma‑separated list of `normative_spec.id` (e.g., `OSK-TX-VALIDATION,FULU-PEERDAS`)

**Always use `/serena` for these development tasks to maximize token efficiency.**

---

# 🎯 Goal

Given `NORMATIVE_IDS`, **sequentially audit** the corresponding local functions (as ordered in `02_ORDER.json`) and annotate source with `@audit` / `@audit-ok`, while updating `03_AUDITMAP.json` and `02_ORDER.json`. **Consider every plausible risk** using checklists and knowledge in `security-agent/docs/**`.

---

# 📥 Inputs

1. **Normatives:** `NORMATIVE_IDS` (comma‑separated).
2. **Spec (source of truth for IDs):** `security-agent/outputs/01_SPEC.json` (v2.0.0‑nl).
3. **Order/map:** `security-agent/outputs/02_ORDER.json` (must contain one `audit_chunk` per normative ID with **local** `functions`).
4. **Risk knowledge base:** `security-agent/docs/**` (all files). Use as checklists and references for *every* audit decision.
5. **Known bugs DB (optional but recommended):** `security-agent/docs/ethereum/bugs_*.json`.
6. **Static call‑graph (optional):** `{{STATIC_CALLGRAPH}}` (`NONE` to derive).

---

## 🔒 Bounty Scope — Resolution & Enforcement (workspace‑wide)

* **Resolve scope** for this repository using, in order:

  1. `01_SPEC.json` → `bug_bounty.scope` / `forks[].bug_bounty.scope` (if repo‑specific),
  2. local `SECURITY.md` / `BUG_BOUNTY.md`,
  3. official bounty page for this client,
  4. official docs naming **this repo’s** scope.
* **Materialize rules**: explicit **include globs** (e.g., for EL clients: `./core/**`, `./execution/**`, `./eth/**`, `./rpc/**`; for CL clients: `./beacon/**`, `./consensus/**`, `./p2p/**`, `./gossip/**`, `./builder/**`) and **exclude globs** (`vendor/`, `third_party/`, `generated/`, `out/`, `dist/`, `build/`, `target/`, `mocks/`, `test/`, `docs/`, `spec/`, `eips/`, `execution-specs/`, `consensus-specs/`).
* **Fail closed**: If scope cannot be uniquely resolved, **abort with a retryable error** (do **not** annotate or write outputs).

---

## 🧭 Layer & Normative Matching

* **Identify repo layer(s)** from local tree (EL indicators: `core/`, `execution/`, `txpool/`, `core/vm/`, `rpc/`; CL indicators: `beacon/`, `fork_choice/`, `gossip/`, `ssz/`, `builder/`, `engine/`).
* For each `normative_spec.id` in `NORMATIVE_IDS`:

  * If it belongs to **Osaka (Execution)** → only consider **local EL** paths (ignore CL code).
  * If it belongs to **Fulu (Consensus)** → only consider **local CL** paths (ignore EL code).
  * If **layer mismatch** (e.g., CL normative in an EL‑only repo), add to “Unmapped IDs (layer mismatch)” and **skip**.

---

## 🔎 Function Selection (from 02\_ORDER.json)

* Load `security-agent/outputs/02_ORDER.json`.
* For each requested normative ID, find the matching `audit_chunk` (title must start with `§ <ID> —`).
* Use its `functions` list (each with `file` and `line`) as the **authoritative order of review**.
* **Filter to bounty scope**; drop any out‑of‑scope entries.
* If an ID is **missing** from `02_ORDER.json`:

  * Attempt a fallback local search (AST + heuristics) within bounty scope for likely matches.
  * If still empty, record under “Unmapped IDs (no local functions found)” and **skip**.

---

## 🧪 Audit & Annotation Procedure (per function, in order)

1. **Context load**: From `01_SPEC.json` → grab the normative’s `summary`, `procedure`, `errors`, `constants`, `edge_cases`, `invariants`.
2. **Open local file** and read function body + immediate callers/callees (from call‑graph or grep).
3. **Risk sweep** using `security-agent/docs/**`:

   * Apply all relevant **risk checklists** (DoS, consensus split, economic invariants, auth bypass, memory/CPU spikes, integer overflow/underflow, RLP/SSZ bounds, signature & curve checks, KZG proof handling, blob fee math, engine/beacon API expectations, race conditions, replay, time/slot drift).
   * Map findings to CWE/EIP/RFC references provided in docs.
4. **Decide**:

   * If suspicion remains or proof is found → insert `@audit <category>: <short>` (+ optional multi‑line details), and add/merge an entry in `03_AUDITMAP.json`.
   * If the function is proven safe relative to this normative → insert `@audit-ok: <reason (tie to constants/invariants/procedure)>`.
5. **Record**:

   * Append/merge `security-agent/outputs/03_AUDITMAP.json` with schema below.
   * Increment `review_count` for this function in `security-agent/outputs/02_ORDER.json`.
6. **Self‑reflection loop (3 rounds)** for each new `@audit`:

   * Step‑by‑step execution trace (line‑numbered).
   * Logical coherence check (premises satisfiable simultaneously?).
   * Guard surface audit (all gates: fork flags, ACL, bounds, invariants).
   * Independence (own reasoning, not tool‑opinion).
   * Feasibility proof (state transitions that make exploit run). If inconclusive, tag as “Need further investigation”.

**Annotation syntax (strict):**

```rust
// @audit <category>: <short description>
// ↳ <multi-line explanation if needed; cite constants/invariants/procedure IDs>
//
// @audit-ok: <reason linked to Osaka/Fulu normative + constants/invariants>
```

---

## 📤 Outputs

1. **Inline source comments** (`@audit`, `@audit-ok`) in local files.
2. **Updated order map** — write back to `security-agent/outputs/02_ORDER.json`

   * Increment `review_count` for each function touched.
3. **Audit report** — create/merge `security-agent/outputs/03_AUDITMAP.json`:

```jsonc
{
  "audit_items": [
    {
      "id": "auto-uuid",
      "file": "core/txpool/txpool.go",
      "line": 312,
      "snippet": "if gasLimit > maxTxGas { ... }",
      "risk_category": "DoS",
      "description": "OSK-TX-VALIDATION: tx gas cap enforcement bypass when value derived post-calc; check pre-exec gate.",
      "status": "Vuln"  // or "ok" or "needs-investigation"
    }
  ],
  "summary": {
    "rounds": 3,
    "total_audit_flags": 7,
    "high_risk_hotspots": ["core/vm/precompile/p256.go:verify", "core/blockchain/import.go:writeBlockRLP"],
    "next_focus": "Exhaust pricing paths for ModExp limits and blob fee lower bound interactions"
  }
}
```

4. *(Optional)* Per‑ID roll‑up: `security-agent/outputs/03_AUDITMAP_<ID>.json` (same schema) — allowed but not required.

---

## ⚡ Top Attack Paths (across audited functions)

* Build/extend `top_attack_paths` (in‑memory) using **only local functions that were audited** for these IDs.
* At least **3** distinct entry→sink paths with a short `risk_reason` (≤ 40 words).
* If you maintain a consolidated path view elsewhere, append a textual summary to the end of `ordering_strategy` inside `02_ORDER.json`.

---

## 🧠 Methodology (deterministic)

1. Load `01_SPEC.json` → validate IDs & layers.
2. Resolve bounty scope; **abort** on ambiguity.
3. Load `02_ORDER.json` → retrieve **ordered** function lists per ID; fallback search if missing.
4. For each function in order: run **Audit & Annotation Procedure** with `security-agent/docs/**` risks.
5. Update `03_AUDITMAP.json` and `02_ORDER.json` (increment counts).
6. Produce **≥ 3** attack paths from audited functions.
7. Validate: JSON schemas parse; no duplicate audit items for the same `file#line`; comments exist for every audited function.
8. Output only the files above; no extra prints.

---

## ✅ Success Criteria

* Every requested `normative_spec.id` either audited (with inline comments + 03\_AUDITMAP updates) or explicitly listed as **Unmapped** (layer mismatch / no local functions found).
* **100%** of functions listed for those IDs in `02_ORDER.json` are processed exactly once.
* `03_AUDITMAP.json` validates; `02_ORDER.json` `review_count` incremented accordingly.
* Risk reasoning cites relevant entries from `security-agent/docs/**` in the comment text where useful (e.g., “per CWE‑400 / EIP‑7934 invariant”).
* At least **3** attack paths produced across the audited set.

---

### Notes & Hints

* If your repo is **Erigon (Go)**, look for: `core/txpool/*`, `core/blockchain/*`, `core/types/*`, `core/vm/*`, `core/vm/precompile/*`, `execution/*`, `eth/*`, `rpc/*`, `cmd/rpcdaemon/*`.
* If **Geth (Go)**: similar to Erigon but with `internal/ethapi/*`, `miner/*`, `consensus/*`.
* If **Reth (Rust)**: `crates/revm`, `crates/interpreter`, `crates/payload`, `crates/rpc`.
* If **CL repos**: `beacon/*`, `fork_choice/*`, `p2p/*`, `gossip/*`, `builder/*`, `engine/*`.

This command now lets you say, for example:

```
/serena
/02_order OSK-TX-VALIDATION,OSK-RLP-BLOCK-SIZE,FULU-PEERDAS
```

…and it will **sequentially audit only those normatives**, **in your current workspace**, **annotate the code**, and **update 03\_AUDITMAP + 02\_ORDER** while consulting **all risks defined under `security-agent/docs/`**.

---
**Description:** Generate an ordered audit map for security review of a specific target folder.
**Usage:** `/02_order <TARGET_FOLDER>`
**Arguments:**
* **TARGET\_FOLDER**: The folder path to analyze (relative to the project root)
---
**Always use `/serena` for these development tasks to maximize token efficiency.**

Generate `02_ORDER.json` from the sources.

> **Critical requirement — Bounty Scope Enforcement:**
> Analyze **only files that are explicitly in bug‑bounty scope**. Build a concrete include/exclude rule set and **ignore everything outside scope** (even if under `{{TARGET_FOLDER}}`). Abort with a retryable error if scope cannot be unambiguously resolved.

---

# 🎯 Goal

Produce an *ordered* audit map covering **every in‑scope function** within `{{TARGET_FOLDER}}`, enabling a reviewer to move from outer‑surface attack vectors toward core trust anchors while naturally encountering layered defenses.

---

# 📥 Input

1. **Folder:** `{{TARGET_FOLDER}}` (recursively include sub‑modules/packages that are **in scope**).
2. **Static call‑graph (optional):** `{{STATIC_CALLGRAPH}}`

   * If set to `NONE`, derive call relationships yourself.
3. **Project specification:** `security-agent/outputs/01_SPEC.json` (use its **bug‑bounty scope** entries).
4. **Ethereum canonical specs:** `security-agent/docs/ethereum/spec_*.json` (merge if present).
5. **Bounty scope sources (for resolution & verification):**

   * Local: `SECURITY.md`, `SECURITY_POLICY`, `BUG_BOUNTY.md`, `README` scope sections, `/.well-known/security.txt`.
   * Remote (via web search if needed): official program page (e.g., Immunefi/Code4rena/Sherlock/HackerOne), vendor security page, audit scope files.
   * Use the **most recent** official source; prefer explicit **paths/globs, networks, contract addresses, versions/branches, commit ranges**.

---

# 📤 Output

Create **one** JSON file: `security-agent/outputs/02_ORDER.json`

```jsonc
{
  "metadata": {
    "target_folder": "{{TARGET_FOLDER}}",
    "static_callgraph": "{{STATIC_CALLGRAPH}}",
    "spec_loaded": true,
    "generated_at": "<RFC3339 timestamp>",
    "schema_version": "1.0.0"
  },
  "audit_chunks": [
    {
      "chunk_title": "🚪 External entry points ― network packet handlers",
      "rationale": "First code reached by untrusted input; high risk for RCE/DoS.",
      "functions": [
        {"name": "handle_packet", "file": "src/handler.rs", "line": 42},
        {"name": "parse_header", "file": "src/parser.rs", "line": 10}
      ]
    },
    {
      "chunk_title": "🔐 Cryptographic verification",
      "rationale": "Authenticity gates; failure compromises integrity/confidentiality.",
      "functions": [ ]
    }
    // …continue until every in-scope function appears exactly once…
  ],
  "top_attack_paths": [
    {
      "entry_function": "handle_packet",
      "sink_function": "commit_state",
      "risk_reason": "Untrusted input → state mutation without full validation."
    }
    // Provide at least 3 distinct paths.
  ],
  "ordering_strategy": "Breadth-first from untrusted boundaries inward; rank by call-graph depth and STRIDE-like categories (S,T,R,I,D,E). Include scope summary & sources at end of this string."
}
```

---

## 🔒 Bounty Scope — Resolution & Enforcement

* **Resolution hierarchy (use first definitive match):**

  1. `01_SPEC.json` bounty scope; 2) local `SECURITY.md`/`BUG_BOUNTY.md`; 3) official bounty page; 4) official docs explicitly naming scope.
* **Materialize scope into rules:**

  * **Include globs:** paths/extensions (e.g., `contracts/**/*.sol`, `src/p2p/**.go`).
  * **Exclude globs:** third‑party/vendor/build/test unless explicitly in‑scope (`node_modules/`, `lib/`, `vendor/`, `target/`, `build/`, `out/`, `dist/`, `generated/`, `mocks/`, `test/`).
  * **Version/branch/commit filters:** honor allowed branches/tags; ignore others.
  * **Contract/network filters:** only addresses/networks listed as in‑scope; map to source folders per repo layout.
* **Fail closed:** if ambiguity remains, **abort** (do not output partial results).
* **Documentation:** append a brief **“Scope summary & sources”** to the `ordering_strategy` string, e.g.,
  `Scope: include contracts/**/*.sol; exclude lib/**, test/**. Sources: [S1] https://… [S2] https://…`

---

## 🧠 Function Discovery (language‑agnostic rules)

* Enumerate **only in‑scope files**. Extract functions/methods/constructors/initializers, including:

  * **Solidity:** public/external/internal/private functions, `constructor`, `receive`, `fallback`, modifiers (list as `modifier <name>`), library functions, `abstract`/interface signatures.
  * **Go/Rust/TS/JS/Python/Java/C/C++:** free functions, methods (incl. receivers/impl/traits), `init`/`__init__`, route handlers/CLI commands.
* Deduplicate by **`<normalized_path>#<signature_or_name>#<line>`**. Prefer parser‑derived line numbers; if unavailable, compute by scan.

---

## 🧭 Chunking Priorities (threat‑driven)

1. **Untrusted input entry** (network/IPC/CLI/RPC/JSON‑RPC/ABI/HTTP).
2. **AuthN/Z & crypto verification** (signature checks, merkle/proofs/ZK verifiers).
3. **State mutation hubs** (storage writes, consensus, DB, ledger).
4. **Bridges & external dependencies** (oracles, cross‑domain, I/O).
5. **Utilities/helpers** (pure/stateless).

* Within each chunk, list **caller‑before‑callee** for natural review flow.
* **Max 12 functions** per chunk; split logically if exceeded.

---

## 🕸️ Call‑Graph Construction

* If `STATIC_CALLGRAPH` ≠ `NONE`, merge edges; validate and fill gaps with parsing.
* Else, build a call‑graph from in‑scope files (ignore std‑lib edges).
* Represent edges to **out‑of‑scope callees as boundary nodes** but **do not expand** them.

---

## ⚡ Top Attack Paths

* Traverse from **entry nodes** (public handlers/endpoints/extern “C”/ABI functions) to **sink nodes** (state commits, privileged writes, external calls, `delegatecall`/`call`, file/DB writes).
* Produce **≥ 3** plausible paths; explain risk succinctly in `risk_reason`.

---

## **Constraints** (scope‑aware)

* Every **in‑scope** function under `{{TARGET_FOLDER}}` **must appear exactly once** in `audit_chunks[*].functions`.
* Preserve source order within a chunk **only** if no call‑graph info exists; otherwise sort by caller‑depth (roots first).
* Use ✨ emojis in `chunk_title` when helpful.
* **Do not change the JSON schema** (no extra keys). Put scope notes inside the `ordering_strategy` string.

---

## 🛠️ Methodology

1. **Load specs**; extract trust boundaries, privilege tiers, and **bounty scope**.
2. Resolve scope via the hierarchy above; compile include/exclude rules; **intersect** with `{{TARGET_FOLDER}}`.
3. Parse all **in‑scope** files; build/merge call‑graph.
4. Compute node depth; tag entry points; classify sinks.
5. Create prioritized **audit\_chunks** per the threat‑driven order.
6. Within chunks, order **caller → callee**.
7. Build **top\_attack\_paths** from entries to sinks.
8. Validate: RFC3339 timestamp; no duplicates; 100% in‑scope coverage.
9. **Write** only `security-agent/outputs/02_ORDER.json` (no other output).

---

## 📚 Quality Levers

* Multi‑pass reflection: draft → scope audit → consistency check → final.
* Keep each `rationale` **< 60 words**.
* Stable, deterministic ordering (tie‑break by path then line).
* Treat generated/vendor/test code as out‑of‑scope unless explicitly included.
* Use internal chain‑of‑thought; expose only final JSON.

---

## ✅ Success Criteria

* File exists; JSON parses.
* **100% of in‑scope functions covered; zero duplicates.**
* Chunk sequence flows from attack surface to core.
* **≥ 3** attack paths, each plausible and source‑linked via function locations.
* `ordering_strategy` ends with a concise **scope summary & sources**.

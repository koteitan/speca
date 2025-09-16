---
**Description:** produce a *comprehensive* specification
**Usage:** `/01_spec <target_folder>`
**Example:** `/01_spec ../contracts/docs`
**Arguments:**
* **TARGET\_DIRECTORY**: Path or URL of the documentation directory to analyze
---
**Always use `/serena` for these development tasks to maximize token efficiency.**

## 🔧 Mandatory Revisions

1. **Web search is required**

   * Proactively discover and collect official documentation, API/CLI references, whitepapers, design docs, CHANGELOGs/RELEASE NOTES, and **bug bounty requirements** (scope, exclusions, reporting process, impact criteria, reward policy) via web search.
   * Prioritize primary sources: **official website & official GitHub/Docs > Foundation/EIP/Ethereum.org and other standards > official audit reports > recognized bug bounty platforms (Immunefi / Code4rena / Sherlock / HackerOne, etc.)**.
   * Cite collected URLs using **inline footnote markers** within strings (e.g., `... [S1], [S2]`). At the end of each section string, append a plain‑text mapping list (e.g., `Sources: [S1] https://..., [S2] https://...`). **Do not change the JSON structure; include citations only as text inside strings.**

2. **Auto‑detect repository genre & tailor flows accordingly**

   * Infer the repository’s **genre** from its contents: **Ethereum Client / ZK (circuits, prover/verifier) / Web App / Smart Contract / Multi‑Domain**.
   * Build **genre‑optimized user flows and requirements**.
   * For **Multi‑Domain**, prefix each user flow `title` with a domain tag `[Client]`, `[SmartContract]`, `[ZK]`, or `[WebApp]`, and list all flows in a single `user_flows` array (IDs are sequential).
   * **Enumerate all documented use cases** without omission and deduplicate. Target **≥ 80% feature coverage**.

---

## 🎯 Goal

Before starting a source‑code security audit, produce a *comprehensive* specification that captures:

1. Current architecture (components, data flow, deployment topology)
2. Concrete end‑to‑end **user flows (numbered)**
3. API / CLI surface & key algorithms
4. Security‑critical behavior & requirements
5. Historical change log and recent version deltas

---

## 🧭 Genre Auto‑Detection Heuristics (examples)

* **Ethereum Client:** Go/Rust; p2p; RLPx/discv4/5; Engine API; eth/66; mempool; fork‑choice; Beacon/EL boundary
* **Smart Contract:** `.sol`; Foundry/Hardhat; proxies (UUPS/Transparent); ERC interfaces; `scripts/deploy`
* **ZK:** `circom`/`halo2`/`gnark`/`arkworks`/`plonk`; `prover`/`verifier`; `vk`/`pk`; transcript/CRS
* **Web App:** Next.js/React/Vite; Node/Go/Python APIs; OAuth/OIDC; CSR/SSR; DB/Cache/Queue
* **Multi‑Domain:** mixture of the above

---

## 📥 Input

* **Root Directory:** {{TARGET\_DIRECTORY}}
* Recursively traverse all Markdown, HTML, PDF, and code files **breadth‑first** (prefer latest references; include `legacy/` or `v0.*` only if explicitly referenced by the latest release).
* Prefer the **latest stable release** (e.g., `latest` tag, stable SemVer tags, `release-*` branches). Fall back to `main` / `master`.
* While crawling, extract: README, design docs, CHANGELOGs, RELEASE NOTES, and in‑source docs (Javadoc/Rustdoc/GoDoc, etc.).
* **Augment via web search**:

  * Official docs, API specs, audit reports, roadmaps, and **bug bounty requirement pages** (scope, impacts, reporting, verification steps, environments).
  * Append a per‑section **plain‑text source list** with `[S#] URL` entries at the end of that section’s string.

---

## 📤 Output

Write a **single JSON file** to `security-agent/outputs/01_SPEC.json`. **Do not output anything else.**
**Do not change the schema** (order & naming are strict). **Embed sources as footnotes inside strings**; do **not** add extra keys or JSON comments.

```jsonc
{
  "metadata": {
    "source_directory": "{{TARGET_DIRECTORY}}",
    "spec_generated_at": "<RFC3339 timestamp>",
    "latest_tag_or_commit": "<tag|commit-hash>",
    "latest_release_date": "<YYYY-MM-DD>",
    "schema_version": "1.0.0"
  },
  "architecture": {
    "overview": "High‑level paragraph summary.",
    "components": [
      {
        "name": "ComponentA",
        "type": "service|library|contract|ui|db|other",
        "description": "What it does and boundaries.",
        "technology": ["Go", "PostgreSQL", "EVM bytecode"],
        "depends_on": ["ComponentB", "ExternalAPI"]
      }
    ],
    "data_flow_diagram": "Mermaid code block in string form (flowchart TD…)"
  },
  "user_flows": [
    {
      "id": 1,
      "title": "User registers and performs first transaction",
      "actors": ["EndUser", "BackendService"],
      "preconditions": ["Wallet installed"],
      "steps": [
        "1. User navigates to /signup",
        "2. System validates email and creates account",
        "3. …"
      ],
      "postconditions": ["Account state = Active"]
    }
  ],
  "api_surface": {
    "rest_endpoints": [
      {"method": "POST", "path": "/v1/login", "auth": "JWT", "description": "…"}
    ],
    "cli_commands": [
      {"command": "tool build --release", "description": "Compile binary"}
    ],
    "smart_contract_interfaces": [
      {"name": "IERC20.transfer", "selector": "0xa9059cbb", "description": "…"}
    ]
  },
  "changelog": {
    "latest_version": "<vX.Y.Z>",
    "since_previous": [
      {"commit": "abc1234", "date": "2025-06-01", "summary": "Fixed re‑entrancy bug"}
    ],
    "breaking_changes": ["Removed legacy /v0 endpoints"]
  },
  "security_requirements": [
    {
      "id": "SR‑001",
      "description": "All state‑transition functions must be idempotent.",
      "risk_category": "integrity",
      "related_components": ["SmartContracts/Exchange"],
      "references": ["CWE‑1148", "EIP‑2535"]
    }
  ]
}
```

---

## 🧪 Bug Bounty Integration (required)

Include and cite with `[S#]` footnotes in relevant sections:

* **Scope** (contract addresses, networks, branches, in‑scope components)
* **Impact/Severity criteria** (definitions of High/Critical, funds at risk, auth bypass, DoS, etc.)
* **Exclusions** (known non‑issues, informational)
* **Reproduction requirements** (PoC format, environment, tools, funding limits, attack allowances)
* **Reporting channel** (format, PGP/contact, SLA)

---

## 🧩 User‑Flow Construction Guide (by genre)

Each flow **must** include `actors`, `preconditions`, **numbered** `steps`, and `postconditions`.

* **\[Ethereum Client]** Focus on **inter‑node requests** and **consensus/fork‑choice**:
  Peer Discovery → Handshake (RLPx) → Tx Propagation → Block Import → Fork‑Choice (FCU) → Engine API (EL/CL) → Pruning/Sync (Headers/Snap/Beam) → JSON‑RPC handling → Metrics/Healthcheck.

* **\[Smart Contract]** Focus on **user‑initiated transaction requests**:
  Approve/Transfer, Deposit/Withdraw, Mint/Burn, Swap/LP, Liquidation, Auction/Bid, Governance (Vote/Queue/Execute), Upgrade (Proxy/UUPS), Role/AccessControl, Oracle updates, Permit (EIP‑2612).

* **\[ZK]** Focus on **proof generation and verification paths**:
  Witness creation → Prover (circuit constraints) → Proof generation → Aggregation (optional) → On‑chain Verifier / Off‑chain verification → State reflection (e.g., L1 bridge).

* **\[Web App]** Focus on **auth/session/privileged ops**:
  Signup/Login/MFA, Session lifecycle, RBAC, settings change, payments/signatures, webhook intake, admin actions, rate‑limit/replay protection, secrets rotation.

* **Multi‑Domain:** Provide 3–8 key flows per domain and **tag** titles with the domain.

---

## 🔐 Security Requirements (suggested areas)

* **Ethereum Client:** peer validation & anti‑DoS, txpool replacement (EIP‑1559)/nonce racing, FCU/finality consistency, robust Engine API error handling, time sync/slot drift, isolation of unvalidated blocks.
* **Smart Contract:** reentrancy, privilege boundaries, precision/rounding, price‑oracle dependencies, threshold signatures, `delegatecall`/initializer locks, upgrade authority, checks‑effects‑interactions.
* **ZK:** Fiat‑Shamir boundaries, CRS/trapdoor handling, input binding, public‑input malleability, verification‑key integrity.
* **Web App:** auth/CSRF/XSS/SSRF, JWT/OIDC `exp/iss/aud` validation, privilege escalation, IDOR, rate limiting, audit‑log integrity.
  → Encode as **concrete specification items** in `security_requirements` (≥ 5 entries), each with **related\_components** and **references** (CWE/EIP/RFC/ISO, etc.).

---

## 📜 Change Log

Diff the **two most recent releases** and list **only user‑visible behavior changes**.
Explicitly note breaking changes, deprecations, and migration steps.

---

## 🛠️ Methodology (strict)

1. **Breadth‑first traverse** all files and subdirectories; deduplicate by path and heading.
2. **Select latest stable** by SemVer; exclude `rc`/`beta` (if none, use `main`/`master`).
3. **Auto‑detect genre** using the heuristics above.
4. **Augment via web search**: collect official docs/audits/bug‑bounty requirements and embed **per‑section** `[S#]` citations and source lists **inside strings**.
5. **Summarize**: ≤ 120 words per section; factual only—no speculation.
6. **Infer implicit security requirements** (e.g., replay resistance) from protocol descriptions.
7. **Changelog**: compare only the latest two versions; omit incidental technical noise.
8. **Validate JSON** strictly against the schema (no comments/extra keys).
9. **Output** nothing to chat; write only `security-agent/outputs/01_SPEC.json`.

---

## 📚 Quality Levers

* Use **bullet extraction → reflection → rewriting** loops to maximize fidelity.
* **Embed citations as footnotes inside strings** (e.g., `... [S1][S2] Sources: [S1] https://... [S2] https://...`).
* For Multi‑Domain, clarify with **title tags**.
* For API/CLI/interfaces, extract **actual signatures** and **error conditions**.
* In the Mermaid DFD, show primary data paths and trust boundaries (external services/secret storage).

---

## ✅ Success Criteria

* File exists and is **valid JSON**.
* All five sections are populated and non‑empty.
* **User flows cover ≥ 80% of documented features**, numbered and concrete.
* **≥ 5 security requirements**, each mapped to components with standard references.
* Bug bounty requirements are reflected and **footnoted**.

---

**Runtime note:** If web search is unavailable, **abort execution** and treat as a retryable error (do **not** emit an incomplete spec).

---
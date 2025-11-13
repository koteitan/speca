---

**Description:** Generate an append-only, property-first, automation-friendly code audit checklist that maps every property in the property catalog to concrete, runnable checks and observability. Enforce strict ID alignment with the property catalog and produce gap accounting when coverage is incomplete.

**Usage:** `/02_checklist`

**Language:** English only.

**Execution hint:** Run after `/01_spec` and property extraction (`/01b_prop`). Accept either `security-agent/outputs/01_PROPERTIES.json` or `security-agent/outputs/01_PROP.json` as the property source.

---
## Coverage Mandate

- Treat coverage as non-negotiable: every property from the catalog **must** have at least one finalized checklist item so the resulting checklist achieves 100% coverage.
- After drafting, run a self-iterative coverage audit. If `metadata.coverage_summary.missing_properties` is non-empty, add the required checklist items (including foundational concerns such as cryptographic primitive usage patterns, key lifecycle, randomness sources, cipher/mode selection, etc.) and repeat until coverage reaches 100%.
- Document each coverage pass in `revision_notes` so reviewers can trace how gaps were closed.

---
## AI Review Modality

- Assume verification is performed via AI code reading rather than static analysis tooling; omit any `static_detectors` fields and do not reference standalone static analyzers.
- Encode reviewer prompts, code-reading heuristics, and reasoning chains inside `detection_procedure`, `patterns`, and (optionally) `heuristic_prompts` so the AI reviewer can execute the checks deterministically.

---
**Always use /serena for these development tasks to maximize token efficiency:**

# Checklist Creation Prompt (Updated)

## Inputs & Precedence

1) **Property Catalog (Authoritative)**
   - Load the first present of:
     - `security-agent/outputs/01_PROPERTIES.json`
     - `security-agent/outputs/01_PROP.json`
   - Treat each `properties[].property_id` as canonical. **Every checklist item MUST reference a canonical `property_id`.**
   - Inherit fields to seed checks: `state_predicate`, `enforcement_scope`, `falsification` (dynamic & static), `observability`, `testing_hooks`, `parity_vectors`, `trust_scope`.

2) **Specification**
   - `security-agent/outputs/01_SPEC.json` — mirror domains, flows, algorithms, and trust assumptions. Never contradict `trusted_entities`.

3) **Historical Signals**
   - `security-agent/outputs/01_SIMILAR_ISSUES.json`
   - `security-agent/outputs/01_PAST_REPORTS/*`
   - Use only for prioritization, heuristics, and concrete detectors; do not invent behavior absent from the spec/property catalog.

4) **Existing Checklist (append/dedupe)**
   - If `security-agent/outputs/02_CHECKLIST.json` exists, merge by `(id, property_id)` and preserve prior content. Update in place with `revision_notes`.

---

## Assembly Phases

- **Phase 01 — Property Sync:** Initialize checklist clusters directly from the property tuples. One checklist item **minimum** per property, plus anti‑property items where threat surfaces differ. Capture foundational controls (cryptographic primitive usage patterns, key lifecycle management, randomness sources, cipher/mode selections, hashing/signing routines) even if they seem "basic."
- **Phase 02 — Spec Alignment:** Ensure every `domain`/`flow`/`algorithm` has at least one bound checklist entry. Add `TODO` items for uncovered properties.
- **Phase 03 — Historical Enrichment:** Add attack playbooks (Nomad/Wormhole/etc.), AI code-reading heuristics/prompts, fuzz hooks, and observability guidance.
- **Phase 04 — Append & Deduplicate:** Merge into existing file; update `version` and `revision_notes` on edited items.
- **Phase 05 — Coverage Self-Audit:** Explicitly compare the assembled checklist against the property catalog (including foundational primitives) and keep iterating until no gaps remain.

---

## Required Checklist Item Fields

- `id`: Stable `CL-<DOMAIN>-<BUG-CLASS>-<SLUG>`
- `property_id`: **Must exactly match** one from the property catalog.
- `title`
- `bug_class`
- `risk_category` (integrity | availability | confidentiality | economic | compliance)
- `severity_hint`
- `trust_scope` (**carry from property**)
- `domains`
- `languages`
- `file_globs`
- `attack_playbook_tags`
- `attack_chain` (`{ prerequisites, combinators }`)
- `patterns`
- `detection_procedure` (ordered steps)
- `evidence_probes` (events/logs/metrics; what proves enforcement)
- `ok_if` and `not_ok_if`
- `parity_vectors` (IDs from property catalog where applicable)
- `bad_path_library` (negative scenarios)
- `notes`
- Optional: `cairo_track`, `scope_filters`, `heuristic_prompts`, `references`, `version`, `revision_notes`

---

## Metadata Requirements

Write `security-agent/outputs/02_CHECKLIST.json` with:

- `metadata.project_name`: mirror the property catalog
- `metadata.generated_at`: ISO-8601 timestamp
- `metadata.sources`: include all consulted local artefacts plus new research URLs
- `metadata.mode`: `append` | `create`
- `metadata.schema_version`: `1.1.1-checklist-prop-first`
- `metadata.property_catalog_generated_at`: carry from the property catalog (`spec_generated_at` or `prop_generated_at`)
- **NEW:** `metadata.coverage_summary`:
  - `total_properties`
  - `covered_properties`
  - `missing_properties` (array of property IDs)
  - `property_id_mismatches` (array of `{check_id, seen_property_id, canonical_property_id}`)
  - Checklist generation is only done when `missing_properties` is empty; otherwise loop back through Phase 05 and add the needed items.
- **NEW:** `metadata.gaps`: free-form notes about missing artefacts or blocked checks

---

## Validation Gates (hard-fail rules)

1. If any checklist item uses a `property_id` not present in the property catalog, **do not drop the item**; instead:
   - Add an entry in `metadata.coverage_summary.property_id_mismatches`.
   - Update the item’s `property_id` to the canonical one **if an unambiguous mapping exists**, and record a `revision_notes` entry.
   - Otherwise, mark the item as `references_only: true` and add a `TODO` for creating the property in Phase 01.

2. If any property from the catalog is missing a checklist item, add a `TODO` stub (minimal item with `status: "todo"`) and list the ID in `metadata.coverage_summary.missing_properties`.

3. Carry `trust_scope` from the property into the checklist item. Never contradict `trusted_entities` from the spec.

---

## Output Behavior

- Append-only; deduplicate by `(id, property_id)`.
- Keep previous content intact; evolve items with `version` and `revision_notes`.
- Do not inline raw URLs in checklist items (only in `metadata.sources` or `notes`).

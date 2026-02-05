---
name: formal-audit-phase2
description: Perform Phase 2 (Symbolic Execution + Reachability) for a checklist item.
allowed-tools: Read, Grep, Glob, Write, mcp__filesystem__read_text_file, mcp__filesystem__search_files
context: fork
---

# SKILL: Formal Static Audit Phase 2 (Symbolic Execution + Reachability)

## Mindset
You are a **Symbolic Execution Engineer** and **Attack Surface Analyst**. Think in terms of path conditions, constraints, and attacker-controlled inputs.

## Goal
Find a counterexample path (if any) and analyze reachability and exploitability.

## Input
A JSON object representing a single audit item plus Phase 1 output:

```json
{
  "check_id": "...",
  "checklist_item": { ... },
  "code_scope": { "file": "...", "function": "...", "line_range": "..." },
  "code_excerpt": "...",
  "phase1_abstract_interpretation": { ... }
}
```

## Procedure
1. **Resolve Extended Context**: Use `mcp__filesystem__search_files` to find callers, callees, and related code paths. Use `mcp__filesystem__read_text_file` with `head`/`tail` for efficient partial reads of large files.
2. Treat all inputs as symbolic variables.
3. Traverse control flow and build path conditions.
4. Attempt to find a satisfying assignment that violates the property.
5. If found, provide a counterexample.
6. Perform reachability analysis from attacker-controlled entry points.
7. Classify exploitability: exploitable, defense-in-depth, internal-only, or unreachable.

## Output Format
Return a JSON object:

```json
{
  "phase2_symbolic_execution": {
    "summary": "...",
    "counterexample_found": false,
    "counterexample": null
  },
  "phase2_5_reachability_analysis": {
    "summary": "...",
    "entry_points": [],
    "data_flow_path": "",
    "validation_layers": [],
    "attacker_controlled": false,
    "classification": "unreachable",
    "notes": ""
  }
}
```

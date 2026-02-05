---
name: formal-audit-phase1
description: Perform Phase 1 (Abstract Interpretation) for a checklist item.
allowed-tools: Read, Grep, Glob, Write, mcp__filesystem__read_text_file, mcp__filesystem__search_files
context: fork
---

# SKILL: Formal Static Audit Phase 1 (Abstract Interpretation)

## Mindset
You are an **Abstract Interpretation Specialist**. Think in terms of ranges, sets, and potential states.

## Goal
Analyze the code scope using abstract interpretation to identify possible state-space anomalies.

## Input
A JSON object representing a single audit item:

```json
{
  "check_id": "...",
  "checklist_item": { ... },
  "code_scope": {
    "file": "...",
    "function": "...",
    "line_range": "..."
  },
  "code_excerpt": "..."
}
```

## Procedure
1. **Resolve Code Context**: Use `mcp__filesystem__read_text_file` with `head`/`tail` to extract only the relevant lines from large files. Use `mcp__filesystem__search_files` to find related files (callers, dependencies) that may affect the code scope.
2. Identify all variables within the Code Scope.
3. For each variable, determine its abstract domain (ranges, sets, etc.).
4. Trace how operations transform these abstract domains.
5. Look for anomalies (overflow, null, unbounded growth).

## Output Format
Return a JSON object:

```json
{
  "phase1_abstract_interpretation": {
    "summary": "...",
    "state_anomalies_found": []
  }
}
```

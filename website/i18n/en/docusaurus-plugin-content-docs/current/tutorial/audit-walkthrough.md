---
sidebar_position: 1
---

# Auditing a test repository

Hands-on walkthrough — already-installed `speca-cli` against a small public repo. The target is OpenZeppelin's `Ownable.sol`, a canonical access-control implementation. Because the code is short, it is well-suited as a first end-to-end run.

## 0. Confirm the environment

```bash
speca doctor
```

Expected:

```
[ok] Node.js 20.x
[ok] Python 3.11 (uv)
[ok] Claude Code CLI authenticated
[ok] MCP servers: fetch, tree_sitter
```

If any line is `[err]`, return to [Try it now](../guide/try-it.md) first.

## 1. Author the configuration files

You can do this interactively (`speca init`) or by hand. For this walkthrough, use the values below.

`outputs/TARGET_INFO.json`:

```json
{
  "project_name": "openzeppelin-ownable-walkthrough",
  "target_repo": "https://github.com/OpenZeppelin/openzeppelin-contracts",
  "target_commit": "v4.9.6",
  "target_language": "Solidity",
  "target_layer": "library",
  "description": "OpenZeppelin Contracts v4.9.6 — Ownable.sol"
}
```

`outputs/BUG_BOUNTY_SCOPE.json`:

```json
{
  "program_name": "openzeppelin-ownable-walkthrough",
  "scope_version": "1.0",
  "in_scope": ["contracts/access/Ownable.sol"],
  "out_of_scope": ["test/", "scripts/"],
  "severity_classification": {
    "HIGH":   { "description": "Unauthorized owner change",
                "cwe": ["CWE-862", "CWE-863"],
                "examples": ["Bypass of onlyOwner"] },
    "MEDIUM": { "description": "Two-step transfer divergence from spec",
                "cwe": ["CWE-841"],
                "examples": ["Pending owner not cleared"] },
    "LOW":    { "description": "Quality / informational",
                "cwe": ["CWE-710"],
                "examples": ["Misleading event"] }
  },
  "scope_notes": "Walkthrough — single contract."
}
```

Both schemas are documented in [Configuration files](../getting-started/config-files.md).

## 2. Run the audit

```bash
speca run --target 04 --workers 4
```

The TUI dashboard streams events. With a single contract this completes in 2–4 minutes:

```
{"phase":"01a","status":"running","found":3}
{"phase":"01b","status":"running","subgraph":"Ownable-ownership-transfer"}
{"phase":"01e","status":"running","property":"PROP-001",
 "description":"onlyOwner is applied to all administrative functions"}
{"phase":"02c","status":"running","resolved":5}
{"phase":"03","status":"running","property":"PROP-001","result":"gap_found"}
{"phase":"04","status":"running","verdict":"CONFIRMED_POTENTIAL"}
```

`result: gap_found` means *"a portion of the proof could not be closed"*; the final `verdict` is decided in Phase 04 after the 3 gates. To stream raw NDJSON instead of the TUI: `speca run --target 04 --json`.

## 3. Browse the findings

```bash
speca browse
```

Each row shows:

- `property_id` — the security property the finding pertains to
- `severity` — High / Medium / Low / Informational
- `verdict` — `CONFIRMED_VULNERABILITY` / `CONFIRMED_POTENTIAL` / `DISPUTED_FP` / …
- `location` — file and line range
- `proof_gap` / `description` — why it was flagged

Use `c` to peek at the code, `f` to refine the filter, and `q` to quit.

## 4. How to interpret the result

`Ownable.sol` is short and well-trodden, so a clean run is unlikely to surface high-severity vulnerabilities. What you may see is `CONFIRMED_POTENTIAL` against the two-step transfer flow (the spec's "pending owner clears on transfer" rule), or `DISPUTED_FP` filtered out by the Trust Boundary gate.

**Whether or not anything is found, success means the pipeline ran end-to-end.** "No findings" should be read as *"no proof gap survived in the specified scope and against the property set we generated,"* not *"no bugs."*

## 5. Move to your own repo

Replace `outputs/TARGET_INFO.json` and `outputs/BUG_BOUNTY_SCOPE.json` with your own project's values and re-run `speca run --target 04`. The more concretely you describe the scope (`in_scope` paths, severity rubric), the better the results.

For larger targets like the [Lighthouse Ethereum client](https://github.com/sigp/lighthouse), Phases 01a and 01b take longer because the spec corpus is bigger. Crank up parallelism:

```bash
speca run --target 04 --workers 8 --max-concurrent 16 --budget 80
```

`--budget 80` hard-stops the phase at $80 (exit code 64). For more on the trade-offs, see [model-benchmark takeaways](../design-notes/model-benchmark-takeaways.md).

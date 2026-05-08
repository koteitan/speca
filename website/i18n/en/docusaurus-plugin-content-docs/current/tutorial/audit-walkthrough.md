---
sidebar_position: 1
---

# Auditing a test repository

This is a hands-on walkthrough — for users who already have speca-cli installed — that takes you through the full audit flow on a public repository. The target is OpenZeppelin's `Ownable.sol` (a canonical access-control implementation). Because the code is short, it is well-suited as a first exercise for observing the entire pipeline end-to-end.

## Prerequisites and setup

Confirm that speca-cli works.

```bash
node cli/dist/cli.js doctor
```

Example output:

```
[ok] Node.js 20.x
[ok] Python 3.11 (uv)
[ok] Claude Code CLI authenticated
```

If any errors appear, return to [Try it now](../guide/try-it.md) and fix your environment first.

## 1. Prepare the configuration files

Running `speca init` creates two files interactively.

```bash
node cli/dist/cli.js init
```

For this walkthrough, prepare `outputs/TARGET_INFO.json` with the following contents.

```json
{
  "repo_url": "https://github.com/OpenZeppelin/openzeppelin-contracts",
  "commit": "v4.9.6",
  "language": "solidity",
  "description": "OpenZeppelin Contracts v4.9.6"
}
```

Write the scope information into `outputs/BUG_BOUNTY_SCOPE.json`.

```json
{
  "scope": "Access control invariants in contracts/access/Ownable.sol",
  "out_of_scope": "UI, deployment scripts",
  "severity_levels": ["High", "Medium", "Low"]
}
```

These two files are the inputs for the entire pipeline.

## 2. Run speca init

```bash
node cli/dist/cli.js init
```

`init` reads the JSON files above to finalize the internal configuration and completes the preparation for the Phase 01a specification crawl. On success, you will see a message such as:

```
[init] TARGET_INFO loaded: OpenZeppelin Contracts v4.9.6
[init] BUG_BOUNTY_SCOPE loaded: 1 scope entry
[init] Ready. Run: speca run --target 04
```

## 3. Run the audit

```bash
node cli/dist/cli.js run --target 04
```

`--target 04` means "execute every phase in sequence up through Phase 04." During execution, NDJSON-formatted logs stream to your terminal.

```
{"phase":"01a","status":"running","found":3}
{"phase":"01b","status":"running","subgraph":"Ownable-ownership-transfer"}
{"phase":"01e","status":"running","property":"PROP-001","description":"Whether the onlyOwner modifier is applied to all administrative functions"}
{"phase":"02c","status":"running","resolved":5}
{"phase":"03","status":"running","proof_attempt":"PROP-001","result":"gap_found"}
{"phase":"04","status":"running","verdict":"CONFIRMED_POTENTIAL"}
```

The `phase` field on each line tells you which stage is currently running. `result: gap_found` means "a portion that cannot be proven was found"; the final verdict is rendered in Phase 04.

## 4. Review the results

```bash
node cli/dist/cli.js browse outputs/04_PARTIAL_*.json
```

The detected candidates are listed. Each row contains the following information.

- `property_id`: which security property the finding pertains to
- `severity`: High / Medium / Low
- `verdict`: CONFIRMED_VULNERABILITY / CONFIRMED_POTENTIAL / DISPUTED_FP, etc.
- `location`: the offending code file and line number
- `description`: an explanation of why it was judged to be a problem

## 5. Interpreting the results

`Ownable.sol` is short and simple, so this exercise is unlikely to surface major vulnerabilities. Instead, conditions such as "is the two-step ownership-transfer confirmation flow implemented within the bounds of the specification?" may be reported as CONFIRMED_POTENTIAL.

**Whether or not anything is found**, success means that the pipeline ran and produced results. Read "no findings" not as "no bugs," but as "no problems were found within the specified scope and specification."

## 6. Now try your own repository

Once you have confirmed that everything works, replace `outputs/TARGET_INFO.json` and `outputs/BUG_BOUNTY_SCOPE.json` with the information for your own project and repeat the same steps. The more concretely you describe the scope, the higher the result quality.

For more complex targets (for example, the [Lighthouse Ethereum client](https://github.com/sigp/lighthouse)), Phases 01a and 01b take longer because there is more specification material. You can speed processing up by raising parallelism with the `--workers 4` option.

```bash
node cli/dist/cli.js run --target 04 --workers 4
```

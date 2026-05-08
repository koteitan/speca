---
sidebar_position: 4
---

# FAQ

## Setup and install

### Do I need a Claude subscription?

The Claude Code CLI itself is free, but running an audit calls the Claude API and incurs usage charges. A Claude Pro or Max subscription keeps cost predictable; a metered API key also works.

### How do I update the CLI?

```bash
npm update -g speca-cli
speca doctor
```

`speca doctor` confirms the new version is wired up correctly.

### Can I avoid a global npm install?

Yes — substitute `npx speca-cli@latest <subcommand>` everywhere this site shows `speca <subcommand>`. The trade-off is the per-invocation `npx` resolution time.

### Where do my outputs go?

Default: `./outputs/`. Override with `--output-dir <path>` on `speca run`, or set `SPECA_OUTPUT_DIR`. Audit outputs are kept locally — SPECA never uploads them.

## Running

### My audit ends with "Empty results"

`outputs/BUG_BOUNTY_SCOPE.json` is missing, empty, or its `in_scope` doesn't match anything. Re-run `speca init`, or edit the file directly using the [schema reference](../getting-started/config-files.md).

### Can I cancel and resume?

Yes. `Ctrl-C` is safe — partial files written so far are kept. Re-running the same command picks up where you stopped because the resume manager scans `*_PARTIAL_*.json` and skips items already processed. Pass `--force` to re-run from scratch.

### Can I cap the cost?

```bash
speca run --target 04 --budget 50
```

The orchestrator hard-stops the phase at $50 with exit code 64. Per-phase tracking is described in [harness internals](../agent-design/harness.md).

### Which Claude model is used?

Currently:

- **Phases 01a / 01b / 01e** — Claude Opus (knowledge structuring; quality of properties is the binding constraint on coverage)
- **Phases 02c / 03 / 04** — Claude Sonnet 4.5 (verification; faster + cheaper while matching precision)

The split, and the data behind it, is discussed in [model-benchmark takeaways](../design-notes/model-benchmark-takeaways.md).

### My target is not Solidity. Can SPECA still audit it?

Yes. SPECA is language-agnostic. Validated targets include Go, Rust, Nim, TypeScript, C, C++, and Solidity. As long as the target has a written specification (RFC, EIP, paper, design doc, or even a thorough README), SPECA can derive properties from it.

### My target has no public spec — just code

Then SPECA can't help much. The whole approach hinges on having a specification to derive properties from. With code alone there is no foothold for the property generator. Conventional code-pattern scanners are a better fit.

## Reading results

### I get a large number of findings — which are important?

Each finding has a `severity` (`Critical` / `High` / `Medium` / `Low` / `Informational`) and a `verdict`:

| Verdict | Meaning |
|---|---|
| `CONFIRMED_VULNERABILITY` | Highest confidence — passed all 3 gates |
| `CONFIRMED_POTENTIAL` | Genuine concern, possibly out-of-scope but worth a look |
| `DOWNGRADED` | Real but lower-impact than the property suggested |
| `NEEDS_MANUAL_REVIEW` | Inconclusive — human judgment required |
| `DISPUTED_FP` | Filtered out by Gate 1, 2, or 3 |
| `PASS_THROUGH` | None of the above |

Start with `speca browse --severity High --filter "verdict:CONFIRMED_*"`.

### Why was this judged a false positive?

Each `DISPUTED_FP` records which gate filtered it. See [3-gate review](../concepts/gate-review.md) for what each gate checks.

## Errors and limits

### "specs not found"

`TARGET_INFO.json` or `BUG_BOUNTY_SCOPE.json` is missing or empty. See [Configuration files](../getting-started/config-files.md). For details on Phase 01a's discovery behavior, [pipeline / 01a](../pipeline/01a-spec-discovery.md).

### Circuit breaker tripped (exit code 65)

Too many consecutive failures within a phase. Usually a transient API error or a misconfigured prompt. Inspect `outputs/logs/<phase>_*.jsonl` for the cause. See [harness internals](../agent-design/harness.md) for the trip thresholds.

### How long does an audit take?

5–15 min for a small repo, 1–3 hours for a production client. The dashboard streams progress and cost in real time. Phase 03 dominates wall-clock; Phase 02c savings (40–60% tokens) keep the bill in check.

## Other questions

[GitHub Issues](https://github.com/NyxFoundation/speca/issues).

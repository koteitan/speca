---
sidebar_position: 2
---

# Quickstart (5 minutes)

A walkthrough that gets you to your first audit in five minutes. This page assumes [Installation](./installation.md) is done and `speca doctor` is green.

## 1. Sign in to Claude (once)

```bash
speca auth login
```

Either pastes an API key into `~/.config/speca/auth.json` or delegates to `claude`'s session. `speca auth status` confirms.

## 2. Generate the two config files

```bash
speca init
```

Interactively asks for:

- the **target repository** URL and commit/tag,
- the **target language** and the **layer** (consensus, execution, application…),
- a **scope rubric** — pick `default` to start with the [ethereum.org rubric](./config-files.md), or `custom` to author your own.

It writes `outputs/TARGET_INFO.json` and `outputs/BUG_BOUNTY_SCOPE.json`. These are the two files that drive the entire pipeline; their schemas are documented in [Configuration files](./config-files.md).

Non-interactive form:

```bash
speca init \
  --target-repo https://github.com/sigp/lighthouse \
  --target-commit v5.1.3 \
  --target-language Rust \
  --target-layer consensus \
  --rubric default \
  --non-interactive
```

## 3. Run the audit

```bash
speca run --target 04 --workers 4
```

Phases 01a → 01b → 01e → 02c → 03 → 04 run in dependency order, with progress streamed to a TUI dashboard. Cost and budget are visible in the header. For the meaning of each phase ID see [Pipeline overview](../pipeline/overview.md).

Common flags:

| Flag | Effect |
|---|---|
| `--target 04` | Run all phases up through Phase 04 |
| `--phase 03 04` | Run only the listed phases |
| `--workers 4` | 4 parallel workers per phase |
| `--max-concurrent 8` | Cap on simultaneous Claude invocations |
| `--budget 50` | Hard-stop the phase if cost exceeds $50 |
| `--force` | Ignore resume state and re-run |
| `--json` | Emit raw NDJSON events instead of the TUI |

Full reference: [CLI reference](./cli-reference.md).

## 4. Browse the findings

```bash
speca browse                     # default: outputs/04_PARTIAL_*.json
speca browse --severity Critical
speca browse --filter "severity:High AND verdict:CONFIRMED_*"
```

The TUI shows each finding's property, code excerpt, proof gap, and gate trace. Pressing `c` opens the code peek; `f` edits the filter; `q` quits.

## 5. Drill in

```bash
speca ask                        # pick the first finding interactively
speca ask PROP-abc-001 --from outputs/04_PARTIAL_*.json
```

Resumes a Claude Code session pre-loaded with the finding context. Useful for asking *"what is the exact proof step that fails?"* or *"show me a minimal patch."*

## What you should see

A representative finding row in `speca browse`:

```
PROP-001  HIGH   CONFIRMED_VULNERABILITY   src/auth.rs:85
  proof_gap: "Missing auth check in error_handler() — unreachable path
              skips verify_auth() before sensitive_data()"
  gates: dead_code=PASS · trust_boundary=PASS · scope=PASS
```

For more on the verdict vocabulary, see [3-gate review](../concepts/gate-review.md).

## How long does it take? How much does it cost?

Rough envelopes from RQ1 / RQ2:

| Codebase | Wall-clock (Phase 03 dominates) | Cost (Sonnet 4.5) |
|---|---|---|
| Small contract (~1 K LoC) | 5–10 min | $1–5 |
| Mid-size repo (~50 K LoC) | 15–40 min | $20–50 |
| Production client (~500 K LoC) | 1–3 hours | $50–100 |

For tighter cost control, see [`design-notes/model-benchmark-takeaways`](../design-notes/model-benchmark-takeaways.md).

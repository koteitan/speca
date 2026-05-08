---
sidebar_position: 3
---

# Try it now

Five-minute walkthrough — first audit on a small public repo.

## Prerequisites

- Node.js 20 or later
- Python 3.11 + [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- git
- A Claude API key (paid via Claude Pro/Max subscription, or a metered API key)

## Step by step

### 1. Install the CLI

```bash
npm install -g speca-cli
speca doctor
```

`speca doctor` validates Node, Python, Claude Code, and the MCP servers. If anything is `[err]`, follow the printed remediation hint.

If you would rather avoid a global install, every command below works with `npx speca-cli@latest …` substituted for `speca`.

### 2. Sign in to Claude

```bash
speca auth login
```

Either pastes an API key into `~/.config/speca/auth.json` or piggybacks on the Claude Code session you already have.

### 3. Generate the two config files

```bash
speca init
```

Asks for the target repo URL, the language and layer, and the scope rubric. Writes `outputs/TARGET_INFO.json` and `outputs/BUG_BOUNTY_SCOPE.json`. For a hand-tuned setup, see [Configuration files](../getting-started/config-files.md).

### 4. Run the audit

```bash
speca run --target 04 --workers 4
```

Phases 01a → 01b → 01e → 02c → 03 → 04 run in order; the TUI dashboard streams progress and cost in real time. A small repo is typically 5–15 minutes; a production-size client is 1–3 hours. Add `--budget 50` to cap cost at $50.

The dashboard looks roughly like this — a header with running cost, then per-phase progress with the active worker count:

```
SPECA · openzeppelin-ownable-walkthrough          cost: $1.42 / $50 budget
─────────────────────────────────────────────────────────────────────────
01a Spec Discovery     ████████████████████  done   23 sections   $0.18
01b Subgraph Extract   ████████████████████  done   12 subgraphs  $0.24
01e Property Gen       ████████████████████  done   18 props      $0.31
02c Code Resolution    ████████░░░░░░░░░░░░  3 / 18 workers=4    $0.21
03 Audit Map           ░░░░░░░░░░░░░░░░░░░░  pending             —
04 Review              ░░░░░░░░░░░░░░░░░░░░  pending             —
```

### 5. Browse the findings

```bash
speca browse
speca browse --severity Critical
speca browse --filter "verdict:CONFIRMED_*"
```

Each row shows property, code excerpt, proof gap, and gate trace. `c` opens code peek, `f` edits the filter, `q` quits. See [CLI reference / browse](../getting-started/cli-reference.md#speca-browse) for the full filter DSL.

### 6. Drill in

```bash
speca ask                                # pick the first finding
speca ask PROP-abc-001 --from outputs/04_PARTIAL_*.json
```

Resumes a Claude Code session pre-loaded with the finding's context.

## Cost & runtime expectations

| Codebase | Wall-clock | Cost (Sonnet 4.5) |
|---|---|---|
| Small contract (~1 K LoC) | 5–10 min | $1–5 |
| Mid-size repo (~50 K LoC) | 15–40 min | $20–50 |
| Production client (~500 K LoC) | 1–3 hours | $50–100 |

For tighter cost control, see [model selection notes](../design-notes/model-benchmark-takeaways.md).

## Troubleshooting

### "Empty results" on Phase 01a

`outputs/BUG_BOUNTY_SCOPE.json` is missing or its `in_scope` is empty. Re-run `speca init` or hand-edit; see [Configuration files](../getting-started/config-files.md).

### Run aborted with exit code 64 / 65

- **64** — `--budget` was hit. Re-invoke with a higher cap or trim scope.
- **65** — circuit breaker tripped. Inspect `outputs/logs/<phase>_*.jsonl` for the underlying API error; usually transient (rate limit / 5xx). See [harness internals](../agent-design/harness.md).

### Other errors

[FAQ](faq.md) · [GitHub Issues](https://github.com/NyxFoundation/speca/issues).

## After your first audit

Once `speca browse` opens you have a list of findings. The next-step questions usually are:

- **"Which one is real?"** — start with `--severity High --filter "verdict:CONFIRMED_*"`. Verdict semantics: [3-gate review](../concepts/gate-review.md).
- **"Why was X dismissed?"** — every `DISPUTED_FP` records the gate that filtered it. Inspect with `Enter`-to-expand in `browse`.
- **"What's the exact proof step that fails?"** — `speca ask <property_id>` opens a session with the finding's full context.
- **"Does any of this trace back to a real spec sentence?"** — yes, every finding does. The chain is shown in the [worked example](../concepts/worked-example.md).

## Next steps

- [CLI reference](../getting-started/cli-reference.md) — every flag
- [Pipeline overview](../pipeline/overview.md) — what each phase does
- [Concepts](../concepts/spec-driven.md) — why the design works
- [Worked example](../concepts/worked-example.md) — one property end-to-end

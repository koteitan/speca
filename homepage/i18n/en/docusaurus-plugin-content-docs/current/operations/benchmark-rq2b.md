---
sidebar_position: 6
---

# Reproducing RQ2b — ProFuzzBench (exploratory)

SPECA application results against **ProFuzzBench**, derived from ChatAFL (NDSS 2024). Six text-based protocol implementations; ground truth is 9 zero-days. **An exploratory track not included in the paper.**

## Status

⚠️ Exploratory: the figure generation pipeline is in place, but SPECA-side raw traces are exploratory and incomplete. Strict reproduction scripts against the ground truth are still being developed.

## Dataset

- **Source**: [ProFuzzBench](https://github.com/profuzzbench/profuzzbench), ChatAFL paper
- **Targets**: 6 protocol implementations (SMTP / DNS / TLS / DTLS / SSH / RTSP families)
- **Ground truth**: 9 zero-days. Details → [`rq2b/ground_truth_bugs.yaml`](https://github.com/NyxFoundation/speca/blob/main/benchmarks/rq2b/ground_truth_bugs.yaml)

## How to reproduce

### Figures only (baseline)

```bash
uv run python3 benchmarks/rq2b/visualize.py
```

Artifacts: `benchmarks/results/rq2b/figures/rq2b_*.png` + `rq2b_table.tex`.

### Overlay SPECA results (if output data is available)

```bash
# Restore raw traces from the release tag (currently only figures are released)
bash benchmarks/scripts/restore-results.sh bench-rq2b-<date>-figures

uv run python3 benchmarks/rq2b/visualize.py \
  --speca-results benchmarks/results/rq2b/speca/speca_rq2b.json
```

`speca/speca_rq2b.json` itself is treated as exploratory; a separate release tag has not been issued at this time.

### CI workflows

- `rq2b-01-setup-dataset.yml` — shallow clone of the ProFuzzBench repository + metadata extraction
- `rq2b-02-visualize.yml` — automated figure generation

## Known issues

- Ground-truth coverage measurement is manual. We plan to add an automated matcher in `benchmarks/rq2b/evaluate.py`
- When integrating an LLM matcher, we want to reuse `matchers.py` from RQ1 (with protocol-specific vocabulary added)
- End-to-end SPECA runs against all 6 implementations have not yet been performed

---
sidebar_position: 4
---

# Reproducing RQ1 — Sherlock Ethereum Fusaka Audit Contest

A benchmark that runs SPECA against 10 Ethereum clients implementing EIP-7594 (PeerDAS) / EIP-7691 and measures how many of the 15 adjudicated H/M/L issues from Sherlock can be recovered. This is how to reproduce the numbers reported in RQ1 of the paper.

## Dataset

- **Contest**: [Sherlock Ethereum Fusaka Audit Contest #787](https://audits.sherlock.xyz/contests/787)
- **Targets**: 10 implementations across 5 languages (Go / Rust / Nim / TypeScript / C / C#)
  `alloy_evm_fusaka`, `c_kzg_4844_fusaka`, `grandine_fusaka`, `lighthouse_fusaka`, `lodestar_fusaka`, `nethermind_fusaka`, `nimbus_fusaka`, `prysm_fusaka`, `reth_fusaka`, `rust_eth_kzg_fusaka`
- **Ground truth**: out of 366 submissions, 15 valid H/M/L (High 5, Medium 2, Low 8)
- **Spec**: EIP-7594 / EIP-7691 + the consensus-spec PRs they reference (auto-discovered by Phase 01a)

## Reported numbers (paper, post-Phase 6)

| Metric | Value |
|---|---|
| Phase 5 findings (pre-review) | 102 |
| Phase 6 findings (post-review) | 72 |
| **H/M/L recover (expert-augmented)** | **15 / 15 (100%)** |
| H/M/L recover (automated-only) | 8 / 15 (53%) |
| Strict precision | 26.4% (19/72) |
| Confirmed-useful precision | 59.7% (43/72) |
| Broad precision | 66.7% (48/72) |
| **F1 (broad precision)** | **0.800** |
| Novel bugs confirmed by developer fix commits | 4 |

## How to reproduce

### A. Re-evaluate already-committed audit branches (no API cost required)

The audit outputs for each implementation are committed to dedicated branches.

```bash
# 1. Fetch branches
git fetch origin \
  alloy_evm_fusaka c_kzg_4844_fusaka grandine_fusaka lighthouse_fusaka \
  lodestar_fusaka nethermind_fusaka nimbus_fusaka prysm_fusaka \
  reth_fusaka rust_eth_kzg_fusaka

# 2. Run recall + precision evaluator
uv run python3 -m benchmarks.rq1 \
  --branches "alloy_evm_fusaka,c_kzg_4844_fusaka,grandine_fusaka,lighthouse_fusaka,lodestar_fusaka,nethermind_fusaka,nimbus_fusaka,prysm_fusaka,reth_fusaka,rust_eth_kzg_fusaka" \
  --use-llm

# 3. Generate report and charts
uv run python3 benchmarks/rq1/generate_report.py
```

### B. Run SPECA end-to-end (full reproduction)

```bash
git checkout alloy_evm_fusaka     # for each branch
uv run python3 scripts/run_phase.py --target 04 --workers 4 --max-concurrent 64
```

The paper's wall-time is 2.4–4.4 minutes per target in Phase 03 (Sonnet 4.5, $30–60 / target).

## Required files (restore)

The raw traces under `benchmarks/results/rq1/` need to be restored from the Release tag:

```bash
bash benchmarks/scripts/restore-results.sh bench-rq1-<date>-sherlock_ethereum_audit_contest
```

The restored content includes the matcher's LLM cache (`llm_cache.jsonl` + `llm_cache_fp.jsonl`), so re-evaluation requires zero API calls.

## Matching method

Issue matching uses LLM-assisted semantic matching + manual verification by two authors (initial agreement 93%; disagreements resolved by consensus). A finding is a TP only when both "root cause" and "security impact" match.

A three-stage matcher:

1. **Text similarity** — title + summary embedding cosine
2. **Token overlap** — Jaccard over normalized identifiers
3. **Keyword candidate selection + LLM judgment** — only for ambiguous cases

## Finding labels (7 categories, paper Table 3)

| Label | Counts as | Definition |
|---|---|---|
| `tp` | TP | Matches a valid H/M/L contest issue |
| `tp_info` | TP | True informational/low-severity detection |
| `fixed` | TP | Independently fixed in the target repo (developer fix commit) |
| `partially_fixed` | TP | Partially addressed |
| `potential-info` | TP* | Possible but unconfirmed |
| `fp_invalid` | FP | False positive due to inference error |
| `fp_review` | FP | False positive blocked by Phase 6 review gate |

Three precision tiers: **strict** (`tp` only), **confirmed-useful** (`tp` + `tp_info` + `fixed` + `partially_fixed`), **broad** (everything except `fp_*`).

## Applying to other audit contests

The harness is contest-agnostic. To apply it to another contest such as Code4rena or Cantina, prepare an `outputs/BUG_BOUNTY_SCOPE.json` and `outputs/TARGET_INFO.json` for each implementation, run `scripts/run_phase.py --target 04`, and run the recall/precision evaluator (`benchmarks/rq1/cli.py`) against the corresponding branch. The ground-truth CSV can be swapped by preparing `data/<contest>/<contest>.csv` in the same format.

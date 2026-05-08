# SPECA Benchmarks

Evaluation harnesses for the two benchmarks reported in the SPECA paper
([arXiv:2604.26495](https://arxiv.org/abs/2604.26495)) plus an exploratory
third track. Numbers below match the paper verbatim.

## Overview

| Benchmark | Dataset | Targets | Ground Truth | Status | Reproduction guide |
|---|---|---|---|---|---|
| **RQ1** | Sherlock Ethereum Fusaka Audit Contest | 10 production Ethereum clients (Go, Rust, Nim, TypeScript, C) | 15 H/M/L issues from 366 expert submissions | ✅ Reported in paper | [docs](https://nyx.foundation/speca/docs/operations/benchmark-rq1) |
| **RQ2** | RepoAudit (ICML 2025) | 15 OSS C/C++ projects (avg 251K LoC) | 35 non-disputed + 5 disputed bugs | ✅ Reported in paper | [docs](https://nyx.foundation/speca/docs/operations/benchmark-rq2a) |
| RQ2b | ProFuzzBench (ChatAFL, NDSS 2024) | 6 text-based protocol implementations | 9 zero-day bugs | ⚠️ Exploratory, not in paper | [docs](https://nyx.foundation/speca/docs/operations/benchmark-rq2b) |

Headline results from the paper:

- **RQ1**: 15 / 15 H/M/L recovered (100%); 4 novel bugs confirmed by fix commits; F1 = 0.80 post-Phase 6.
- **RQ2**: 88.9% precision (Sonnet 4.5) matching the best published RepoAudit baseline; 12 author-validated beyond-GT candidates (2 externally confirmed).

## Directory layout

```
benchmarks/
├── data/                  ← input datasets (Sherlock CSV, RepoAudit GT lists)
├── rq1/                   ← RQ1 evaluation code (matchers, recall/precision, FP analysis)
├── rq2a/                  ← RQ2 evaluation code + published baselines
├── rq2b/                  ← RQ2b ProFuzzBench (exploratory)
├── runners/               ← orchestration helpers (target-cloning, batch dispatch)
├── scripts/
│   ├── collect_branch_outputs.py
│   ├── publish-results.sh    ← pack results/<subdir>/ → tarball + manifest (Release flow)
│   └── restore-results.sh    ← download a release tarball back to results/
└── results/               ← raw outputs are on Releases; only figures (*.png/*.tex/*.md) are tracked
```

## Operator entry points

For runtime tasks (publishing / restoring artifacts, refreshing datasets,
re-running benchmarks), the **operator guide on the documentation site**
is the canonical reference:

- [Operator overview](https://nyx.foundation/speca/docs/operations/overview)
- [Refreshing the audit-finding dataset](https://nyx.foundation/speca/docs/operations/dataset-refresh)
- [Benchmark Release artifacts](https://nyx.foundation/speca/docs/operations/release-artifacts)
- [RQ1 reproduction](https://nyx.foundation/speca/docs/operations/benchmark-rq1) · [RQ2](https://nyx.foundation/speca/docs/operations/benchmark-rq2a) · [RQ2b](https://nyx.foundation/speca/docs/operations/benchmark-rq2b)

The Markdown sources live under [`homepage/docs/operations/`](../homepage/docs/operations/) — the documentation site is built from those.

## TL;DR — `benchmarks/results/` is on Releases, not in git

The bulky raw outputs (~350 MB of `*.json`/`*.jsonl` per RQ) live on
GitHub Releases under tags of the form `bench-<rq>-<utc-date>-<suffix>`.
Only the rendered figures (`*.png`), paper tables (`*.tex`), and human
review docs (`*.md`) stay in the working tree. To pull raw outputs back:

```bash
gh release list --repo NyxFoundation/speca | grep '^bench-'
bash benchmarks/scripts/restore-results.sh <tag>
```

See [Release artifacts](https://nyx.foundation/speca/docs/operations/release-artifacts) for the full publish/restore flow.

## Citation

```bibtex
@misc{kamba2026speca,
  title         = {Beyond Code Reasoning: A Specification-Anchored Audit Framework for Expert-Augmented Security Verification},
  author        = {Kamba, Masato and Murakami, Hirotake and Sannai, Akiyoshi},
  year          = {2026},
  eprint        = {2604.26495},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CR},
  url           = {https://arxiv.org/abs/2604.26495}
}
```

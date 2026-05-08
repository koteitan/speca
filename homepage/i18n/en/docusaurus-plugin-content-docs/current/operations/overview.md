---
sidebar_position: 1
---

# Operations guide overview

This category collects work procedures for the "operations side" of SPECA — refreshing the dataset, running benchmarks, distributing artifacts, and so on.

## Intended audience

- Researchers and implementers who want to reproduce SPECA's evaluation results
- Operators who want to update the HuggingFace audit-finding corpus ([NyxFoundation/vulnerability-reports](https://huggingface.co/datasets/NyxFoundation/vulnerability-reports))
- Contributors who want to share new benchmark execution results

## Common prerequisites

- Checkout of the speca repository + [installation](../getting-started/installation.md)
- A self-hosted GitHub Actions runner (`grandchildrice` / `hirorogo` allowlist)
- Additional secrets depending on the target task:
  - `HF_TOKEN` — write permission to HuggingFace org `NyxFoundation`
  - `GITHUB_TOKEN` — write to Releases (issued automatically by GitHub Actions)

## Pages in this category

| Page | Purpose |
|---|---|
| [Refresh the dataset](./dataset-refresh.md) | scrape → CSV → HF dataset loop |
| [Distribute benchmark artifacts](./release-artifacts.md) | bundle / restore `benchmarks/results/` to GitHub Release |
| [Reproduce RQ1](./benchmark-rq1.md) | Sherlock Ethereum Fusaka audit contest |
| [Reproduce RQ2](./benchmark-rq2a.md) | RepoAudit C/C++ benchmark |
| [Reproduce RQ2b](./benchmark-rq2b.md) | ProFuzzBench (exploratory) |

## Big picture

```
  scrape_*.py (run locally)
        ↓
  benchmarks/data/defi_audit_reports/*.csv
        ↓
  Publish dataset to HuggingFace (workflow_dispatch)
        ↓
  https://huggingface.co/datasets/NyxFoundation/vulnerability-reports
```

```
  benchmarks/results/<rq>/<run>/  (eval pipeline output)
        ↓
  Publish benchmark artifacts (workflow_dispatch)
        ↓
  GitHub Release `bench-<rq>-<date>-<suffix>`
        ↓
  restore via restore-results.sh
```

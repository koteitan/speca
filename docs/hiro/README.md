# docs/hiro — SPECA benchmark contract-work notes

> **Last updated:** 2026-03-04

Internal working notes for the SPECA benchmark contract track. The
sub-files retain their original Japanese content; only this index is in
English.

## Files

| File | Type | Content |
|------|------|---------|
| [ann.md](ann.md) | Ideation | 14 SPECA extension ideas (brainstorm) |
| ~~RQ2_BENCHMARK_GUIDE.md~~ | Archived | Old PrimeVul guide — the `benchmarks/archive/` directory has since been removed; see git history for content |
| [LOCAL_VERIFICATION_GUIDE.md](LOCAL_VERIFICATION_GUIDE.md) | Procedure | Pipeline verification on a local environment |
| [WEB_APP_DESIGN.md](WEB_APP_DESIGN.md) | Design | Result-visualization web-app design (not yet implemented) |
| [mobile-setup.md](mobile-setup.md) | Setup | SSH-from-mobile guide for Claude Code |
| [prbun.md](prbun.md) | Archived | Record of 66 bug-fix PRs |
| [arc/kijaku.md](arc/kijaku.md) | Bug tracking | Vulnerability + logic-bug tracker (57 items) |
| [引き継ぎ/hikitugi.md](引き継ぎ/hikitugi.md) | Handover | Project-state / handover document |

## Status

### Done

- RQ1 Sherlock Ethereum evaluation: recall 100% (15/15), precision 66.3%.
- ~~RQ2 PrimeVul baseline~~ — archived (was at `benchmarks/archive/rq2_primevul/`, since removed).
- **RQ2a RepoAudit baseline visualization** — 5 figures under `benchmarks/results/rq2a/figures/`.
- **RQ2b ChatAFL baseline visualization** — 5 figures under `benchmarks/results/rq2b/figures/`.
- GitHub Actions workflows: `rq2a-01`/`02`, `rq2b-01`/`02`.
- Benchmark issue analysis and discussion.
- 14 SPECA extension ideas (`ann.md`).

### In progress / pending

- **RQ2a: run SPECA against the 15 RepoAudit projects** (highest priority).
- RQ2a: fill in `ground_truth_bugs.yaml` bug detail.
- **RQ2b: contact ChatAFL authors** to obtain file / function / line info.
- RQ2b: run SPECA against the 6 protocol implementations.
- Manual review of the human-label set (22 items).

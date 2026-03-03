# Benchmark Report

Generated: 2026-02-28T14:26:05.425017+00:00

## Dataset

- Path: /Users/hiro/Documents/security-agent/.claude/worktrees/zealous-cohen/benchmarks/data/primevul/primevul_test_paired.jsonl
- Ground-truth samples: 868
- Total samples: 868
- Pair groups: 412 (eligible: 386, skipped: 26)

## Tool Metrics

| Tool | Precision | Recall | F1 | TP | FP | TN | FN |
| ---- | --------- | ------ | -- | -- | -- | -- | -- |
| Semgrep | 0.000 | 0.000 | 0.000 | 0 | 0 | 433 | 435 |
| Cppcheck | 0.499 | 0.867 | 0.633 | 377 | 379 | 54 | 58 |
| Flawfinder | 0.508 | 0.290 | 0.369 | 126 | 122 | 311 | 309 |
| Security Agent | — | — | — | — | — | — | — |

## Tool Metadata

| Tool | Version | Timeout | Limit |
| ---- | ------- | ------- | ----- |
| semgrep | 1.152.0 | 300 | 0 |
| cppcheck | Cppcheck 2.17.1 from cppcheck-wheel 1.5.1 | 30 | 0 |
| flawfinder | 2.0.19 | 30 | 0 |
| llm_baseline | n/a | 120 | 20 |

## Pairwise Correct

## Pairwise Statistics (Security Agent vs Baselines)

- n/a

| Tool | Accuracy | Correct | Scored | Total |
| ---- | -------- | ------- | ------ | ----- |
| Semgrep | 0.000 | 0 | 386 | 386 |
| Cppcheck | 0.003 | 1 | 386 | 386 |
| Flawfinder | 0.010 | 4 | 386 | 386 |
| Security Agent | — | — | — | — |

## Unique Detections (Security Agent)

- Count: 0

## CWE Coverage (Top 10 by vulnerable count)

| CWE | Total | Semgrep Recall | Cppcheck Recall | Flawfinder Recall |
| --- | --- | --- | --- | --- |
| CWE-787 | 72 | 0.000 | 0.972 | 0.292 |
| CWE-125 | 47 | 0.000 | 0.872 | 0.234 |
| CWE-703 | 47 | 0.000 | 0.745 | 0.213 |
| CWE-476 | 39 | 0.000 | 0.846 | 0.256 |
| CWE-416 | 29 | 0.000 | 0.931 | 0.207 |
| CWE-200 | 16 | 0.000 | 0.938 | 0.312 |
| CWE-369 | 14 | 0.000 | 0.643 | 0.071 |
| CWE-20 | 14 | 0.000 | 1.000 | 0.429 |
| CWE-119 | 14 | 0.000 | 1.000 | 0.357 |
| CWE-617 | 12 | 0.000 | 0.583 | 0.333 |

## Tool Weaknesses (Top Missed CWEs)

- Semgrep: CWE-787 (72), CWE-125 (47), CWE-703 (47), CWE-476 (39), CWE-416 (29)
- Cppcheck: CWE-703 (12), CWE-476 (6), CWE-125 (6), CWE-617 (5), CWE-369 (5)
- Flawfinder: CWE-787 (51), CWE-703 (37), CWE-125 (36), CWE-476 (29), CWE-416 (23)

## Example Cases (Security Agent Only)

- n/a

## Notes

- Security Agent: results pending.

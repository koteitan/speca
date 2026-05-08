---
sidebar_position: 2
title: Generalization of Specification-Anchored Auditing
---

# Beyond Code Reasoning — Specification-Anchored Auditing of Multi-Implementation Distributed Protocols

## Overview

This is a follow-up paper that extends the mechanism obtained from the SPECA Fusaka case study ([previous paper](./paper-fusaka)) to multi-implementation distributed protocols at large, including those beyond Ethereum.

Conventional audit tools that "only look inside the codebase" are strong on cases where bugs surface as code-level anomalies, but they miss cases where "the correctness required by the specification" and "how the code is written" do not align. This paper aims to bridge that gap by reusing security properties derived from the specification across multiple implementations.

In the evaluation, we recovered all 15 known H/M/L vulnerabilities from Sherlock contests while also reporting 4 independently discovered bugs, including one cryptographic-algorithm invariant violation that 366 auditors had missed.

## Key Contributions

1. **A property vocabulary reusable across implementations** — properties extracted once from the specification are commonly used across 10 Ethereum targets (6 languages)
2. **A specification-anchored audit framework** — detects spec-originated invariant violations that are unreachable by code alone. In addition to fully recovering known contest vulnerabilities, 4 additional bugs were independently discovered
3. **Pipeline-traceable false-positive analysis** — false positives map to three root causes, each tied to a specific phase
4. **Audit principles that minimize misses** — characterizes the property kinds that work effectively and the filters that preserve severity. Approximately $30 cost per H/M/L bug

## Key Experimental Results

### Sherlock Benchmark (10 targets / 15 known cases)

- Recovery rate with expert assistance (expert-augmented): **15/15 (100%)**
- Recovery rate fully automated (automated-only): **8/15 (53%)**
- Novel bugs independently discovered with confirmed fixes: **4 cases**
  - One of them is a cryptographic-algorithm invariant violation that 366 contest auditors had missed
- Post-review broad precision: 66.7%
- Cluster-level strict precision: 48.7%

### RepoAudit Benchmark (15 C/C++ projects)

| Metric | Value |
|------|-----|
| Precision (Sonnet 4.5) | 88.9% |
| Recall (35 known bugs) | 100% |
| F1 score | 0.94 |
| Author-verified candidates outside the known set | 12 cases |
| Passing external verification (Level A fix / Level B authorization) | 2 cases |
| Cost per bug | approx. $1.69 |

## Citation

```bibtex
@article{Kamba2026Beyond,
  title={Beyond Code Reasoning: Specification-Anchored Auditing of Multi-Implementation Distributed Protocols},
  author={Kamba, Masato and Murakami, Hirotake and Sannai, Akiyoshi},
  journal={arXiv preprint arXiv:2604.26495},
  year={2026},
  month={May}
}
```

## Links

- arXiv HTML: https://arxiv.org/html/2604.26495v2
- arXiv Abstract: https://arxiv.org/abs/2604.26495
- arXiv PDF: https://arxiv.org/pdf/2604.26495v2

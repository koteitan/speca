---
sidebar_position: 1
title: SPECA Fusaka Case Study
---

# SPECA: Specification-Checklist-Driven Auditing for Multi-Implementation Systems — An Ethereum Fusaka Case Study

## Overview

This is the first SPECA paper. It proposes a framework that converts a specification into an "audit checklist" and establishes a 1:1 correspondence between requirements and implementation code.

We applied this mechanism to 11 production clients participating in the Ethereum Fusaka upgrade and analyzed the results of agent-driven submissions to a real bug-reporting contest. By reusing checklist items found in one implementation against other implementations, we reduced the average human verification time per submission to 40 minutes.

## Key Contributions

1. **A framework for converting specifications into checklists** — keeps the requirement → implementation code-location mapping in a form that can be automatically traced
2. **Checklist 1→N reuse strategy** — a method that applies inspection items found in a single implementation directly to other implementations as well. Ultimately, **76.5%** of valid findings originate from this mechanism
3. **Real-world case study** — submitted 54 entries for Ethereum Fusaka, with **31.5% accepted as valid findings** (above the contest average of 27.6%)
4. **Cause classification of false positives** — identifies that **56.8%** of false positives stem from "threat-model assumption mismatches," with the remaining causes also broken down
5. **Quantification of human effort** — agent-led work reduced manual verification per submission to an average of **40 minutes**

## Key Experimental Results

### Ethereum Fusaka Audit Deployment

- **Valid findings**: 17/54 (31.5%), exceeding the contest average of 27.6%
- **Breakdown of detection strategies** (out of 17 valid findings):
  - Cross-implementation check origin: 13 cases (76.5%)
  - Static audit origin: 17.6%
  - Dynamic testing origin: 5.9%
- **Client coverage**: 9/11 (81.8%)
- **V2 reassessment recall** (Consensus Layer H/M/L issues): 27.3% (3/11), with High-severity at 2/3 detected

### Root Causes of False Positives (out of 37 cases)

| Cause | Count | Share |
|------|-----|-----|
| Threat-model assumption mismatch | 21 | 56.8% |
| Duplicate detection | 8 | 21.6% |
| Analysis error | 5 | 13.5% |
| Out of scope | 3 | 8.1% |

### Human Effort

Under the agent-led approach, the average manual verification time per submission was **40 minutes**, a significant reduction compared to traditional audit workflows.

## Citation

```bibtex
@article{kamba2026speca,
  title={SPECA: Specification-to-Checklist Agentic Auditing for Multi-Implementation Systems --- A Case Study on Ethereum Clients},
  author={Kamba, Masato and Sannai, Akiyoshi},
  journal={arXiv preprint arXiv:2602.07513},
  year={2026},
  month={February}
}
```

## Links

- arXiv HTML: https://arxiv.org/html/2602.07513v2
- arXiv Abstract: https://arxiv.org/abs/2602.07513
- arXiv PDF: https://arxiv.org/pdf/2602.07513v2

## SPECA Paper Series

This paper (Feb 2026) is the **foundational case study** of SPECA, an empirical investigation focused on a single Ethereum Fusaka case. The follow-up paper (May 2026) generalizes the mechanisms used here to multi-implementation distributed protocols at large.

- [Generalization of Specification-Anchored Auditing (Beyond Code Reasoning)](./paper-multi-impl)

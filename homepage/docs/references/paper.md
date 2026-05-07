---
sidebar_position: 1
title: 論文
---

# コード推論を超えて — マルチ実装分散プロトコルの仕様アンカー監査

**Beyond Code Reasoning: Specification-Anchored Auditing of Multi-Implementation Distributed Protocols**

## 概要

本論文は、分散プロトコルの監査における仕様駆動の脆弱性検出手法を提案する。マルチ実装環境では、コード解析単独では仕様に基づく不変式違反を捕捉することが困難である。本研究では、仕様から一度抽出した property vocabulary を複数実装で再利用し、specification-anchored framework を通じて、コード推論の限界を超えた invariant 検出を実現した。

## 主要な貢献

1. **Cross-implementation property vocabulary** — 仕様から抽出した property を複数の実装間で一度の定義で再利用可能にする体系
2. **Specification-anchored framework** — コード単独では到達困難な仕様駆動の invariant を検出するパイプライン
3. **Pipeline-traceable FP analysis** — 偽陽性が phase 単位の root cause にマップされる可視化および除去手法
4. **Recall-first auditing principles** — productive property types と severity-preserving filters により cost-effective monitoring を実現 (~$30 per H/M/L bug)

## 主要な実験結果

### Sherlock Benchmark (10 ターゲット / 15 issues)

- Expert-augmented recovery: 15/15 (100%)
- Automated-only: 8/15 (53%)
- 独立発見した fix-confirmed novel bugs: 4 件
  - うち 1 件は 366 名のコンテスト監査者が見落とした暗号不変式違反
- Broad post-review precision: 66.7%
- Cluster-level strict precision: 48.7%

### RepoAudit Benchmark (15 C/C++ projects)

| 指標 | 値 |
|------|-----|
| Precision (Sonnet 4.5) | 88.9% |
| Recall (35 ground-truth bugs) | 100% |
| F1 Score | 0.94 |
| Beyond-GT author-validated candidates | 12 |
| External validation (Level A+B) | 2 |
| Cost per bug | ~$1.69 |

## 引用

```bibtex
@article{Kamba2026Beyond,
  title={Beyond Code Reasoning: Specification-Anchored Auditing of Multi-Implementation Distributed Protocols},
  author={Kamba, Masato and Murakami, Hirotake and Sannai, Akiyoshi},
  journal={arXiv preprint arXiv:2604.26495},
  year={2026},
  month={May}
}
```

## リンク

- **arXiv HTML**: https://arxiv.org/html/2604.26495v2
- **arXiv PDF**: https://arxiv.org/pdf/2604.26495v2
- **arXiv Abstract**: https://arxiv.org/abs/2604.26495

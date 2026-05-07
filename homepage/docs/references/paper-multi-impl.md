---
sidebar_position: 2
title: 仕様アンカー監査の一般化
---

# コード推論を超えて — マルチ実装分散プロトコルの仕様アンカー監査

## 概要

SPECA の Fusaka ケーススタディ ([前論文](./paper-fusaka)) で得られた仕組みを、Ethereum 以外を含むマルチ実装分散プロトコル全般に拡張した発展論文です。

「コードベースの中だけ眺める」従来の監査ツールは、バグがコードレベルの異常として表面化しているケースには強い反面、「仕様が要求している正しさ」と「コードがどう書かれているか」がかみ合っていないケースを取りこぼします。本論文は、仕様から導いたセキュリティプロパティを複数実装に対して使い回すことで、このギャップを埋めることを目指しています。

評価では、Sherlock コンテストの既知 H/M/L 脆弱性 15 件をすべて回復しつつ、366 名の監査者が見落とした暗号不変式違反 1 件を含む 4 件の独立発見バグも報告しました。

## 主要な貢献

1. **実装間で使い回せるプロパティ語彙** — 仕様から 1 度抽出したプロパティを、Ethereum 10 ターゲット (6 言語) で共通利用
2. **仕様アンカー方式の監査枠組み** — コード単独では到達できない、仕様起点の不変式違反を検出。コンテスト既知脆弱性を全回復した上で 4 件の追加バグも独立発見
3. **パイプラインで追跡できる偽陽性分析** — false positive が 3 つの根本原因にマップでき、それぞれ特定のフェーズに紐づく
4. **取りこぼしを最小化する監査原則** — 効きやすいプロパティ種別と severity を保つフィルタを特性化。H/M/L バグ 1 件あたり約 $30 のコスト

## 主要な実験結果

### Sherlock ベンチマーク (10 ターゲット / 既知 15 件)

- 専門家補助あり (expert-augmented) での回復率: **15/15 (100%)**
- 完全自動 (automated-only) での回復率: **8/15 (53%)**
- 独立発見し fix が確認された novel bug: **4 件**
  - うち 1 件は 366 名のコンテスト監査者が見落とした暗号不変式違反
- レビュー後の broad precision: 66.7%
- クラスタレベルの strict precision: 48.7%

### RepoAudit ベンチマーク (C/C++ 15 プロジェクト)

| 指標 | 値 |
|------|-----|
| Precision (Sonnet 4.5) | 88.9% |
| Recall (既知 35 件のバグ) | 100% |
| F1 スコア | 0.94 |
| 既知集合外で著者検証済の候補 | 12 件 |
| 外部検証通過 (Level A 修正 / Level B 認可) | 2 件 |
| 1 バグあたりのコスト | 約 $1.69 |

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

- arXiv HTML: https://arxiv.org/html/2604.26495v2
- arXiv Abstract: https://arxiv.org/abs/2604.26495
- arXiv PDF: https://arxiv.org/pdf/2604.26495v2

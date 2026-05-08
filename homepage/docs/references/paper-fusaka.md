---
sidebar_position: 1
title: SPECA Fusaka ケーススタディ
---

# SPECA: マルチ実装システム向け仕様書チェックリスト駆動型監査 — Ethereum Fusaka ケーススタディ

## 概要

SPECA の最初の論文です。仕様書を「監査チェックリスト」に変換し、要件と実装コードを 1:1 で対応付ける枠組みを提案しています。

Ethereum Fusaka アップグレードに参加している 11 個の本番クライアントに対してこの仕組みを適用し、実際のバグ報告コンテストにエージェント主導で submission を出した結果を分析しました。1 つの実装で見つけたチェック項目を他の実装に使い回すことで、人手の検証時間を 1 件あたり平均 40 分まで短縮しています。

## 主要な貢献

1. **仕様書をチェックリストに変換する枠組み** — 要件 → 実装コード位置のマッピングを自動でたどれる形に保つ
2. **チェックリスト 1→N 再利用戦略** — 単一実装で見つけた検査項目を他の実装にもそのまま当てる方式。最終的に有効 finding の **76.5%** がこの仕組みに由来
3. **実戦ケーススタディ** — Ethereum Fusaka で 54 件の submission を提出し、**31.5% が valid finding として採択** (コンテスト平均 27.6% 超え)
4. **偽陽性の原因分類** — false positive の **56.8%** が「脅威モデルの想定ずれ」だと特定し、その他の原因も内訳化
5. **人手工数の定量化** — エージェント主導により、submission 1 件あたりの手動検証を平均 **40 分** に削減

## 主要な実験結果

### Ethereum Fusaka 監査デプロイ

- **valid findings**: 17/54 (31.5%)、コンテスト平均 27.6% を上回る
- **検出戦略の内訳** (有効 findings 17 件中):
  - クロス実装チェック由来: 13 件 (76.5%)
  - 静的監査由来: 17.6%
  - 動的テスト由来: 5.9%
- **クライアント網羅率**: 9/11 (81.8%)
- **V2 再評価 recall** (Consensus Layer の H/M/L issues): 27.3% (3/11)、High-severity は 2/3 を検出

### 偽陽性の根本原因 (37 件中)

| 原因 | 件数 | 割合 |
|------|-----|-----|
| 脅威モデルの想定ずれ | 21 | 56.8% |
| 重複検出 | 8 | 21.6% |
| 分析エラー | 5 | 13.5% |
| スコープ外 | 3 | 8.1% |

### 人手工数

エージェント主導により submission 1 件あたりの手動検証時間は平均 **40 分**。従来の audit ワークフローとの比較で大幅短縮。

## 引用

```bibtex
@article{kamba2026speca,
  title={SPECA: Specification-to-Checklist Agentic Auditing for Multi-Implementation Systems --- A Case Study on Ethereum Clients},
  author={Kamba, Masato and Sannai, Akiyoshi},
  journal={arXiv preprint arXiv:2602.07513},
  year={2026},
  month={February}
}
```

## リンク

- arXiv HTML: https://arxiv.org/html/2602.07513v2
- arXiv Abstract: https://arxiv.org/abs/2602.07513
- arXiv PDF: https://arxiv.org/pdf/2602.07513v2

## SPECA 論文シリーズ

本論文 (Feb 2026) は SPECA の **基礎ケーススタディ** で、Ethereum Fusaka 1 ケースに焦点を当てた実証研究です。その後の発展論文 (May 2026) では、ここで使われた仕組みをマルチ実装分散プロトコル全般へ一般化しています。

- [仕様アンカー監査の一般化 (Beyond Code Reasoning)](./paper-multi-impl)

# RQ2a: リポジトリレベルバグ検出ベンチマーク

**ベンチマーク:** RepoAudit 15 C/C++ プロジェクト (ICML 2025)
**Issue:** https://github.com/NyxFoundation/security-agent/issues/96

## 概要

RepoAudit 論文で使用された 15 個の C/C++ OSS プロジェクトに対して、
SPECA の検出性能を既存ツール (Meta Infer, Amazon CodeGuru, 各種 LLM) と比較する。

**比較対象ツールの結果は論文記載の数値を引用し、SPECA の結果のみ新規実験で追加する。**

## ファイル構成

```
benchmarks/rq2a/
  published_baselines.yaml   # 論文データ (集約数値 + per-project, 手動転記)
  ground_truth_bugs.yaml     # 具体的バグリスト (照合用, TODO: 詳細を埋める)
  visualize.py               # 可視化スクリプト
  README.md                  # このファイル

benchmarks/results/rq2a/
  figures/                   # 生成グラフ
  speca/                     # SPECA 結果 (後で追加)
```

## 実行方法

```bash
# 可視化 (baselines-only)
uv run python3 benchmarks/rq2a/visualize.py

# SPECA 結果を含む場合
uv run python3 benchmarks/rq2a/visualize.py --speca-results benchmarks/results/rq2a/speca/speca_summary.json
```

## データソース

| ツール | TP | FP | Precision | 出典 |
|--------|----|----|-----------|------|
| RepoAudit (Claude 3.5 Sonnet) | 40 | 11 | 78.43% | Table 2, v3 |
| RepoAudit (DeepSeek R1) | — | — | 88.46% | Appendix, v3 |
| RepoAudit (Claude 3.7 Sonnet) | — | — | 86.79% | Appendix, v3 |
| RepoAudit (o3-mini) | — | — | 82.35% | Appendix, v3 |
| Meta Infer | 7 | 2 | 77.78% | Section 4.4, v3 |
| Amazon CodeGuru | 0 | 18 | 0.00% | Section 4.4, v3 |
| Single-function LLM | 1 | — | — | Section 4.3, v3 |
| **SPECA** | **TBD** | **TBD** | **TBD** | This study |

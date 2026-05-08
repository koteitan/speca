---
sidebar_position: 5
---

# RQ2 を再現する — RepoAudit C/C++ Benchmark

ICML 2025 の RepoAudit benchmark(15 個の OSS C/C++ プロジェクト、平均 251K LoC、Ground truth 35 + 5 件)に SPECA を適用したベンチマーク。論文の RQ2。

## 結果(paper)

| 指標 | 値 |
|---|---|
| Precision(Sonnet 4.5) | **88.9%** — 公開ベースラインの最高値と並ぶ |
| Beyond-GT 候補 | **12 件**(著者 validate)、うち上流メンテナで **2 件確認済み** |
| 平均 wall-time(Phase 03) | プロジェクトあたり 4.4 分 |

## ファイル構成

```
benchmarks/rq2a/
├── visualize.py                  # ベースライン + SPECA 比較図の生成
├── evaluate.py                   # SPECA 出力の評価
├── analyze_deep.py               # FP の深掘り分析
├── ground_truth_bugs.yaml        # 35 + 5 件の判定済みバグ
├── published_baselines.yaml      # RepoAudit 論文のベースライン
└── README.md
```

生成成果物の格納先(全て Release tag からの restore 必要):

```
benchmarks/results/rq2a/
├── speca/                  ← Sonnet 4.5(主結果)
├── speca_sonnet4/          ← Sonnet 4(モデル比較対照)
├── speca_deepseek_r1/      ← DeepSeek R1(matched-backbone control)
└── figures/                ← rq2a_*.png(visualize.py が再生成)
```

restore コマンド:

```bash
bash benchmarks/scripts/restore-results.sh bench-rq2a-<date>-speca
bash benchmarks/scripts/restore-results.sh bench-rq2a-<date>-sonnet4
bash benchmarks/scripts/restore-results.sh bench-rq2a-<date>-deepseek_r1
bash benchmarks/scripts/restore-results.sh bench-rq2a-<date>-figures
```

最新の `<date>` は `gh release list --repo NyxFoundation/speca | grep '^bench-rq2a-'` で確認。

## 再現方法

### A. 既存 SPECA 出力から図だけ再生成(API コスト不要)

```bash
# ベースラインのみ
uv run python3 benchmarks/rq2a/visualize.py

# Sonnet 4.5 を重ねる(speca/ を restore 済み前提)
uv run python3 benchmarks/rq2a/visualize.py \
  --speca-results benchmarks/results/rq2a/speca/speca_summary.json

# モデル間比較(symmetric-comparison + adherence 図用)
uv run python3 benchmarks/rq2a/visualize.py \
  --speca-multi \
    "Sonnet 4.5=benchmarks/results/rq2a/speca/speca_summary.json" \
    "Sonnet 4=benchmarks/results/rq2a/speca_sonnet4/speca_summary.json" \
    "DeepSeek R1=benchmarks/results/rq2a/speca_deepseek_r1/speca_summary.json"
```

生成: 8 PNG + 1 LaTeX 表 → `benchmarks/results/rq2a/figures/`。

### B. 15 プロジェクトに SPECA を end-to-end で回す

```bash
# 1. RepoAudit dataset を target_workspace/ にクローン
gh workflow run rq2a-01-setup-dataset.yml

# 2. SPECA を実行(モデル別の workflow が分かれている)
gh workflow run rq2a-03-audit-map-sonnet4.yml -f projects=all
gh workflow run rq2a-03-audit-map-deepseek-r1.yml -f projects=all

# 3. 評価 + 可視化
gh workflow run rq2a-04-evaluate-sonnet4.yml -f projects=all
```

### C. Beyond-GT 候補レビュー

Sonnet 4 run で得られた **18 件の著者 validate 済み beyond-GT 候補**は [`benchmarks/results/rq2a/REVIEW_GUIDE.md`](https://github.com/NyxFoundation/speca/blob/main/benchmarks/results/rq2a/REVIEW_GUIDE.md) に provenance + cross-model 確認情報付きで列挙されています。

## 別のコードベースに応用する

ハーネスは benchmark 非依存です。新しい C/C++(または他言語)プロジェクトを評価するには:

1. 対象コードベース毎に `outputs/TARGET_INFO.json` を作成(`target_repo` + `target_commit`)
2. `outputs/BUG_BOUNTY_SCOPE.json` でスコープを定義(対象モジュール / 除外パス)
3. `scripts/run_phase.py --target 04` で SPECA を回す
4. `benchmarks/rq2a/published_baselines.yaml` 形式で比較先を用意すれば既存可視化スクリプトにそのまま乗る

詳細は[プロジェクト構成](../project-structure.md)も参照。

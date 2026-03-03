# Archive: 旧 RQ2 (PrimeVul 関数レベルベンチマーク)

**アーカイブ日:** 2026-03-04
**理由:** RQ 構成変更により、関数レベルデータセット (PrimeVul) は廃止。
リポジトリ/プロジェクトレベルのベンチマークに移行。

詳細: https://github.com/NyxFoundation/security-agent/issues/96

## 新しい RQ 構成

| RQ | 内容 | ベンチマーク |
|----|------|-------------|
| RQ2a | リポジトリレベルバグ検出 | RepoAudit 15 プロジェクト |
| RQ2b | 動的テストとの比較 | ProFuzzBench (ChatAFL) |

## アーカイブ内容

- `rq2_primevul/` — PrimeVul 評価・可視化スクリプト (evaluate.py, visualize.py)
- `results_rq2/` — PrimeVul ベースライン結果 (Semgrep, Cppcheck, Flawfinder)
- `run_cvefixes_baseline.sh` — CVEFixes 自動化スクリプト (未使用)

## 再利用可能性

- `evaluate.py` のメトリクス計算ロジック (Precision/Recall/F1, Pairwise Accuracy) は流用可能
- `visualize.py` のグラフ生成パターンも参考にできる
- PrimeVul ベースライン結果 (Cppcheck F1=0.633, Flawfinder F1=0.369) は論文の背景説明に引用可能

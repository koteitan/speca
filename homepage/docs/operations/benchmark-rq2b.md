---
sidebar_position: 6
---

# RQ2b を再現する — ProFuzzBench(探索的)

ChatAFL(NDSS 2024)由来の **ProFuzzBench** に対する SPECA 適用結果。テキストベースの 6 プロトコル実装、Ground truth は 9 件の zero-day。**論文には含まれていない探索的 track** です。

## ステータス

⚠️ Exploratory: 図の生成パイプラインは整っていますが、SPECA 側の生 trace は探索的かつ不完全。Ground truth に対する厳密な再現スクリプトは整備中。

## データセット

- **Source**: [ProFuzzBench](https://github.com/profuzzbench/profuzzbench), ChatAFL paper
- **対象**: 6 プロトコル実装(SMTP / DNS / TLS / DTLS / SSH / RTSP 系列)
- **Ground truth**: 9 件の zero-day。詳細 → [`rq2b/ground_truth_bugs.yaml`](https://github.com/NyxFoundation/speca/blob/main/benchmarks/rq2b/ground_truth_bugs.yaml)

## 再現方法

### 図のみ(ベースライン)

```bash
uv run python3 benchmarks/rq2b/visualize.py
```

成果物: `benchmarks/results/rq2b/figures/rq2b_*.png` + `rq2b_table.tex`。

### SPECA 結果を重ねる(出力データがあれば)

```bash
# 生 trace を release tag から復元(現状は figures のみ release されている)
bash benchmarks/scripts/restore-results.sh bench-rq2b-<date>-figures

uv run python3 benchmarks/rq2b/visualize.py \
  --speca-results benchmarks/results/rq2b/speca/speca_rq2b.json
```

`speca/speca_rq2b.json` 自体は探索的扱いで、別 release tag は現時点では未発行。

### CI workflow

- `rq2b-01-setup-dataset.yml` — ProFuzzBench リポジトリの shallow clone + メタデータ抽出
- `rq2b-02-visualize.yml` — 図の自動生成

## 既知の課題

- Ground truth の coverage 計測が手動。`benchmarks/rq2b/evaluate.py` に automated matcher を入れる予定
- LLM matcher を組み込む場合、RQ1 の `matchers.py` を流用したい(プロトコル特有の語彙を追加)
- 6 実装すべてに対する end-to-end SPECA run は未実施

---
sidebar_position: 4
---

# RQ1 を再現する — Sherlock Ethereum Fusaka Audit Contest

EIP-7594 (PeerDAS) / EIP-7691 を実装した 10 個の Ethereum クライアントに対して SPECA を回し、Sherlock の判定済み 15 件の H/M/L issue をどれだけ recover できるかを計測したベンチマークです。論文の RQ1 で報告した数値の再現方法。

## データセット

- **コンテスト**: [Sherlock Ethereum Fusaka Audit Contest #787](https://audits.sherlock.xyz/contests/787)
- **対象**: 5 言語(Go / Rust / Nim / TypeScript / C / C#)10 実装
  `alloy_evm_fusaka`, `c_kzg_4844_fusaka`, `grandine_fusaka`, `lighthouse_fusaka`, `lodestar_fusaka`, `nethermind_fusaka`, `nimbus_fusaka`, `prysm_fusaka`, `reth_fusaka`, `rust_eth_kzg_fusaka`
- **Ground truth**: 366 件の応募中、有効 H/M/L 15 件(High 5・Medium 2・Low 8)
- **Spec**: EIP-7594 / EIP-7691 + 参照する consensus-spec PR(Phase 01a が自動発見)

## 報告された数値(paper, post-Phase 6)

| 指標 | 値 |
|---|---|
| Phase 5 findings(レビュー前) | 102 |
| Phase 6 findings(レビュー後) | 72 |
| **H/M/L recover(expert-augmented)** | **15 / 15(100%)** |
| H/M/L recover(automated-only) | 8 / 15(53%) |
| Strict precision | 26.4%(19/72) |
| Confirmed-useful precision | 59.7%(43/72) |
| Broad precision | 66.7%(48/72) |
| **F1(broad precision)** | **0.800** |
| 開発者の fix commit で確認された novel bug | 4 |

## 再現方法

### A. コミット済み audit branch を再評価する(API コスト不要)

各実装の audit 出力は専用ブランチに commit されています。

```bash
# 1. ブランチを fetch
git fetch origin \
  alloy_evm_fusaka c_kzg_4844_fusaka grandine_fusaka lighthouse_fusaka \
  lodestar_fusaka nethermind_fusaka nimbus_fusaka prysm_fusaka \
  reth_fusaka rust_eth_kzg_fusaka

# 2. recall + precision evaluator を実行
uv run python3 -m benchmarks.rq1 \
  --branches "alloy_evm_fusaka,c_kzg_4844_fusaka,grandine_fusaka,lighthouse_fusaka,lodestar_fusaka,nethermind_fusaka,nimbus_fusaka,prysm_fusaka,reth_fusaka,rust_eth_kzg_fusaka" \
  --use-llm

# 3. レポートとチャート生成
uv run python3 benchmarks/rq1/generate_report.py
```

### B. SPECA を end-to-end で回す(完全再現)

```bash
git checkout alloy_evm_fusaka     # 各ブランチ毎
uv run python3 scripts/run_phase.py --target 04 --workers 4 --max-concurrent 64
```

paper の wall-time は 1 ターゲットあたり Phase 03 で 2.4–4.4 分(Sonnet 4.5、$30–60 / 件)。

## 必要なファイル(restore)

`benchmarks/results/rq1/` 配下の生 trace は Release tag からの restore が必要です:

```bash
bash benchmarks/scripts/restore-results.sh bench-rq1-<date>-sherlock_ethereum_audit_contest
```

restore 対象には matcher の LLM キャッシュ(`llm_cache.jsonl` + `llm_cache_fp.jsonl`)が含まれているので、再評価時は API call 0 で済みます。

## マッチング手法

issue マッチは LLM-assisted semantic matching + 2 著者による手動検証(初期一致 93%、不一致は consensus で解決)。「root cause」と「security impact」が両方一致した場合のみ TP。

3 段階のマッチャー:

1. **テキスト類似度** — タイトル + 要約の embedding cosine
2. **トークン重複** — 正規化 identifier の Jaccard
3. **キーワード候補選定 + LLM 判定** — 曖昧なケースのみ

## Finding ラベル(7 カテゴリ、paper Table 3)

| ラベル | 計上 | 定義 |
|---|---|---|
| `tp` | TP | 有効 H/M/L コンテスト issue にマッチ |
| `tp_info` | TP | 真の informational/low-severity 検出 |
| `fixed` | TP | 対象リポで独立に修正されている(developer fix commit) |
| `partially_fixed` | TP | 一部対応済み |
| `potential-info` | TP* | 可能性ありだが未確認 |
| `fp_invalid` | FP | 推論誤りの偽陽性 |
| `fp_review` | FP | Phase 6 のレビューゲートで弾かれた偽陽性 |

3 段階の precision: **strict**(`tp` のみ)、**confirmed-useful**(`tp` + `tp_info` + `fixed` + `partially_fixed`)、**broad**(`fp_*` 以外)。

## 別の audit contest に応用する

ハーネスはコンテスト非依存です。Code4rena / Cantina など別のコンテストに適用するには、各実装に対応する `outputs/BUG_BOUNTY_SCOPE.json` と `outputs/TARGET_INFO.json` を用意して `scripts/run_phase.py --target 04` を回し、recall/precision evaluator(`benchmarks/rq1/cli.py`)を該当ブランチに走らせます。Ground truth CSV は同形式の `data/<contest>/<contest>.csv` を準備すれば差し替え可能。

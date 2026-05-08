---
sidebar_position: 1
---

# パイプライン概要

SPECA は 6 つの順序付きフェーズで構成されます。前 2 つのフェーズは仕様分析 (一度のみ実行)、後 4 つは実装監査 (対象ごとに実行)。

## フェーズ依存チェーン

```
01a (Spec Discovery)
  ↓
01b (Subgraph Extraction)
  ↓
01e (Property Generation) ← BUG_BOUNTY_SCOPE.json 必須
  ↓
02c (Code Pre-resolution) ← TARGET_INFO.json 必須
  ↓
03 (Audit Map)
  ↓
04 (Review)
```

## 各フェーズ

| ID | 名前 | 入力 | 出力 |
|---|---|---|---|
| **01a** | [仕様発見](./01a-spec-discovery.md) | SPEC_URLS env | STATE.json |
| **01b** | [サブグラフ抽出](./01b-subgraph-extraction.md) | STATE.json | Mermaid + PARTIAL_*.json |
| **01e** | [プロパティ生成](./01e-property-generation.md) | Subgraph + STRIDE/CWE | PARTIAL_*.json |
| **02c** | [コード解析](./02c-code-resolution.md) | Properties + ソース | PARTIAL_*.json |
| **03** | [監査マップ](./audit-map.md) | Properties + コード | PARTIAL_*.json |
| **04** | [レビュー](./review.md) | Findings | PARTIAL_*.json (6 verdicts) |

## データフロー

- **パーシャルファイル**: `outputs/<phase_id>_PARTIAL_W{worker}B{batch}_{timestamp}.json`
- **キューファイル**: `outputs/<phase_id>_QUEUE_{worker}.json`
- **ログ**: `outputs/logs/{phase_id}_*.jsonl`

各フェーズは上流のパーシャルファイルをグロブパターンで消費し、処理済みアイテムをスキップして (resume)、結果を即座に保存します。

## サーキットブレーカー・予算・リジューム

- **Circuit Breaker**: 全ワーカーで共有。連続エラーまたは API 異常で自動停止
- **予算**: フェーズごとに BudgetExceeded で硬停止。トークン浪費を防止
- **Resume**: 既処理アイテムは自動スキップ。中断・再実行時にトークン節約

詳細は各フェーズドキュメントを参照してください。

---
sidebar_position: 7
---

# Phase 04: レビュー (3-Gate FP Filter)

構造的な 3 ゲート review で false positive を削減。Recall-safe 設計。

## 入力

Phase 03 の出力 (`outputs/03_PARTIAL_*.json`)

## 3 つのゲート (順序実行)

### Gate 1: Dead Code

- コード位置が到達不可能か判定
- unreachable / stub / placeholder を検出
- Verdict: `DISPUTED_FP` (early exit)

### Gate 2: Trust Boundary

- proof gap が trust boundary を越えているか確認
- 攻撃者制御可能な入力か、内部呼び出しか
- Verdict: `DISPUTED_FP` または次ゲートへ

### Gate 3: Scope Check

- バグ報奨対象スコープ内か
- BUG_BOUNTY_SCOPE.json に従う
- out_of_scope なら `DISPUTED_FP`

## Early Exit

各ゲートで `DISPUTED_FP` が返ると処理終了。後続ゲートは実行されません。

## 出力

`outputs/04_PARTIAL_*.json` — 6 つの verdicts:

```json
{
  "property_id": "PROP-001",
  "finding_id": "FINDING-001",
  "verdict": "CONFIRMED_VULNERABILITY",
  "gate_results": [
    {"gate": "dead_code", "passed": true},
    {"gate": "trust_boundary", "passed": true},
    {"gate": "scope_check", "passed": true}
  ],
  "severity": "HIGH"
}
```

| Verdict | 意味 |
|---|---|
| `CONFIRMED_VULNERABILITY` | 高信頼度の脆弱性 (全ゲート通過) |
| `CONFIRMED_POTENTIAL` | 潜在的問題 (スコープ外だが重要) |
| `DISPUTED_FP` | FP (ゲートで棄却) |
| `DOWNGRADED` | 重要度削減 (情報レベル) |
| `NEEDS_MANUAL_REVIEW` | 判定困難 (要審査) |
| `PASS_THROUGH` | その他 |

詳細は [3-Gate Review](../concepts/gate-review.md) を参照。

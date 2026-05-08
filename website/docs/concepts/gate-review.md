---
sidebar_position: 3
---

# 3-Gate Review (Recall-Safe FP Filter)

Phase 03 の proof-based audit から出た FINDING 候補を、3 つの機械的ゲートで検証します。

## 設計原則: Recall-Safe

- **Recall**: H/M/L 脆弱性の検出率を保つ (目標 >90%)
- **Precision**: False Positive を系統的に削減

この tension は、ゲート設計を「狭く」(棄却条件を厳格に) することで解く:

- ゲートは DISPUTED_FP のみを返す (他の削減は早期段階で実行)
- 3 ゲート以外での FP 削減は許さない (precision を確保しつつ recall を守る)

## Gate 1: Dead Code

**質問**: Proof gap のコード位置は、実際に到達可能か？

- 削減対象:
  - `unreachable` / `panic!` 直後 / `return` 後のコード
  - Stub / placeholder / TODO コメント
  - テストコード / 非稼働ブランチ

- Verdict: **DISPUTED_FP** (early exit)

## Gate 2: Trust Boundary

**質問**: Proof gap が trust boundary を越えているか？

攻撃者制御可能な入力か、内部ロジックか:

- ✓ in_scope (信頼できない入力): continue to Gate 3
- ✗ out_of_scope (内部生成): **DISPUTED_FP** (early exit)

## Gate 3: Scope Check

**質問**: BUG_BOUNTY_SCOPE.json で対象スコープ内か？

```json
{
  "in_scope": ["src/auth.rs", "src/crypto/*"],
  "out_of_scope": ["tests/", "docs/"],
  "severity_classification": {
    "HIGH": [...],
    "MEDIUM": [...]
  }
}
```

- Verdict: **DISPUTED_FP** または **CONFIRMED_VULNERABILITY**

## Early Exit 動作

各ゲートで DISPUTED_FP が返ると、後続ゲートは実行されません:

```
Gate 1 → DISPUTED_FP ⇒ STOP (no Gate 2, 3)
Gate 1 → PASS ⇒ Gate 2
Gate 2 → DISPUTED_FP ⇒ STOP (no Gate 3)
Gate 2 → PASS ⇒ Gate 3
Gate 3 → DISPUTED_FP or CONFIRMED ⇒ STOP
```

## 6 つの最終 Verdict

| Verdict | 条件 |
|---|---|
| `CONFIRMED_VULNERABILITY` | 全ゲート通過、高信頼 |
| `CONFIRMED_POTENTIAL` | 潜在的だが重要 |
| `DISPUTED_FP` | Gate 1/2/3 で棄却 |
| `DOWNGRADED` | 情報レベルに格下げ |
| `NEEDS_MANUAL_REVIEW` | 判定困難 |
| `PASS_THROUGH` | その他 |

実装詳細は [パイプライン - Phase 04](../pipeline/review.md) を参照。

---
sidebar_position: 6
---

# Phase 03: 監査マップ (Proof-Based)

形式的な証明試行ベースの監査。各プロパティについて Map → Prove → Stress-Test を実行します。

![Phase 03 の制御フロー](/img/diagrams/proof-attempt.png)

## 入力

- Phase 02c の出力 (`outputs/02c_PARTIAL_*.json`)
- ターゲットコードベース (TARGET_INFO.json で指定された commit)

## 処理

3 つの監査フェーズを順序実行:

### 1. Map (マッピング)

- プロパティを code_scope に従いコードをスキャン
- 関連する関数・変数を特定

### 2. Prove (証明試行)

- 「このプロパティは成立するか」を問う
- 証明を試みる
- **Proof gap** (証明の隙間) = 候補 finding
- ハルシネーション抑制: 具体的な proof claim を要求

### 3. Stress-Test

- 証明の反例 (counterexample) を探索
- Edge case での成立確認
- 境界条件チェック

## 出力

`outputs/03_PARTIAL_*.json`

```json
{
  "property_id": "PROP-001",
  "verdict": "FINDING",
  "proof_attempt": {
    "claim": "verify_auth() is always called before resource access",
    "evidence": "Code path exists where resource access occurs at line 85 without prior verify_auth() call",
    "confidence": "HIGH",
    "proof_gap": "Missing auth check in error handler at line 85"
  }
}
```

- `verdict`: FINDING / NO_FINDING / UNCERTAIN
- `proof_gap`: 証明の具体的な隙間 (Phase 04 でフィルタリング対象)

詳細は [証明試行ベースの監査](../concepts/proof-attempt.md) を参照。

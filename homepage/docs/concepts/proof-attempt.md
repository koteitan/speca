---
sidebar_position: 2
---

# 証明試行ベースの監査

## 「バグを探す」から「証明を試みる」へ

従来の LLM ベースツールは曖昧な指示で動きます:

```
"このコードにバグがないか調べてください"
```

結果は投機的で根拠が薄い。**FP 率 88%**。

SPECA は構造化された主張を要求します:

```
"このプロパティが成立するか証明してください:
 『authenticate() は常に sensitive_data() の前に呼ばれる』"
```

## Proof Gap = Finding 候補

証明試行は 3 つの結論に至ります:

1. **Proof Success**: プロパティは成立する → NO_FINDING
2. **Proof Gap**: 証明できない部分がある → FINDING 候補
3. **Proof Failure**: プロパティは成立しない → CONFIRMED_VULNERABILITY

**Proof gap** が検出の核です。具体的なギャップ (コード位置・条件) を特定:

```
Claim: "authenticate() は sensitive_data() の前に呼ばれる"

Gap at line 85 in error_handler():
  if (!cache_hit) {
    sensitive_data();  // <-- authenticate() 呼ばれていない
  }
```

## ハルシネーション抑制

構造化された claim は以下により投機性を抑制:

- **Commitment**: モデルが「このコードは property X を満たす / 満たさない」を明確に判定
- **Gap articulation**: FP なら具体的 gap を説明する必要がある
- **3-gate filter**: Proof gap のうち trust boundary / scope を外れたものは FP と判定

## Phase 03 での実装

```
Map:  property をコード上にマップ
  ↓
Prove: 「property は成立するか」を問う
  ↓
Stress-Test: edge case を試す
```

詳細は [パイプライン - Phase 03](../pipeline/audit-map.md) を参照。

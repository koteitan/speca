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

監査は固定の Map → Prove → Stress-Test フローに従います。各分岐は `03_PARTIAL_*.json` の verdict と直接対応します。

![証明試行の制御フロー](/img/diagrams/proof-attempt.png)

- **Map** — プロパティを実装で担保しているコードを特定 (Phase 02c の事前解決があればそれを使用)。
- **Prove** — プロパティが全実行パスで成立する証明を試みる。サブクレームを明示的に書き出す。
- **証明が成立** → `Pass` (finding なし)。
- **gap が残る** → **Stress-Test** で具体的な反例を探す。
  - **攻撃可能** → `Vulnerability` (証明が能動的に破れる)。
  - **反例未構築** → `Potential` (proof gap は残るがエクスプロイトは未構築)。

Phase 03 の verdict はそのまま Phase 04 の [3 ゲートレビュー](../concepts/gate-review.md) に渡されます。JSON 形式とプロンプトレベルの詳細は [パイプライン — Phase 03](../pipeline/audit-map.md) を参照してください。

---
sidebar_position: 4
---

# Phase 01e: プロパティ生成

サブグラフから型付きセキュリティプロパティを生成します。STRIDE + CWE Top 25 脅威モデルを適用。

## 前提条件

`outputs/BUG_BOUNTY_SCOPE.json` が必須です。ファイルがない場合はオーケストレータが `sys.exit(1)` で停止します。

## 入力

- Phase 01b の出力 (`outputs/01b_PARTIAL_*.json`)
- `outputs/BUG_BOUNTY_SCOPE.json`

## 処理

1. **STRIDE 脅威モデル**: Spoofing / Tampering / Repudiation / Information Disclosure / Denial of Service / Elevation of Privilege
2. **CWE Top 25**: CWE-22 (Path Traversal) / CWE-78 (OS Command Injection) / CWE-89 (SQL Injection) など
3. **信頼モデル分析**: サブグラフから攻撃者制御可能な入力点を特定
4. **プロパティ型**: 4 つのクラス
   - `Invariant` — 常に成立すべき条件
   - `Precondition` — 関数実行前の要件
   - `Postcondition` — 実行後の保証
   - `Assumption` — 外部システムの前提

## 出力

`outputs/01e_PARTIAL_*.json`

```json
{
  "property_id": "PROP-001",
  "type": "Invariant",
  "description": "Authentication state must be verified before accessing protected resources",
  "covers": "FN-001",
  "classification": "STRIDE_ElevationOfPrivilege",
  "cwe_related": ["CWE-862"],
  "reachability": {
    "classification": "PUBLIC_API",
    "entry_points": ["authenticate()", "verify_token()"],
    "attacker_controlled": ["user_input", "token"],
    "bug_bounty_scope": "in_scope"
  }
}
```

- `covers`: 原拠となるサブグラフ要素 ID
- `reachability`: BUG_BOUNTY_SCOPE.json ベースの到達可能性情報

このファイルは Phase 02c (コード解析) と Phase 03 (監査) の入力として使用されます。

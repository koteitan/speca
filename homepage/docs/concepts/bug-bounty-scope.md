---
sidebar_position: 4
---

# BUG_BOUNTY_SCOPE.json

Phase 01e (プロパティ生成) から Phase 04 (review) まで、scope 判定に用いるメタデータファイル。

## 必須性

Phase 01e 実行時に `outputs/BUG_BOUNTY_SCOPE.json` が必須。ファイルがない場合、オーケストレータは `sys.exit(1)` で停止します。

## スキーマ

```json
{
  "program_name": "ethereum-fusaka",
  "scope_version": "1.0",
  
  "in_scope": [
    "src/consensus/",
    "src/crypto/kzg.rs",
    "src/state_machine.rs"
  ],
  
  "out_of_scope": [
    "tests/",
    "docs/",
    "vendor/",
    "build/"
  ],
  
  "severity_classification": {
    "CRITICAL": {
      "description": "Protocol halt, cryptographic break",
      "cwe": ["CWE-327", "CWE-338"],
      "examples": ["Invalid signature verification", "Entropy exhaustion"]
    },
    "HIGH": {
      "description": "State divergence, consensus failure",
      "cwe": ["CWE-862", "CWE-863"],
      "examples": ["Unauthorized state transition", "Access control bypass"]
    },
    "MEDIUM": {
      "description": "Information disclosure, partial bypass",
      "cwe": ["CWE-200", "CWE-203"],
      "examples": ["Timing leak", "Nonce reuse"]
    },
    "LOW": {
      "description": "Quality, usability",
      "cwe": ["CWE-400"],
      "examples": ["Resource leak", "Performance degradation"]
    }
  },
  
  "scope_notes": "Only in-scope high-value code paths will be audited. Test utilities and vendor code excluded per standard rubric."
}
```

## 使用箇所

- **Phase 01e**: Properties に `reachability.bug_bounty_scope` (in_scope/out_of_scope) を付与
- **Phase 02c**: Severity 分類にマップ (Informational を削減)
- **Phase 04 Gate 3**: Proof gap が in_scope に含まれるか確認

## カスタム Rubric の書き方

複数実装の cross-comparison では、共通の rubric を用いる:

```json
{
  "program_name": "kzg-batch-verify-v2",
  "common_rubric": {
    "in_scope": [
      "KZG parameter generation (setup)",
      "Commitment creation",
      "Batch verification (main algorithm)",
      "Polynomial operations"
    ],
    "out_of_scope": [
      "Serialization / deserialization",
      "Performance optimizations",
      "Logging / debugging"
    ]
  }
}
```

このファイルを複数実装間で共有することで、**同じ property 語彙での比較**が可能になります。

詳細は [仕様駆動監査](./spec-driven.md) を参照。

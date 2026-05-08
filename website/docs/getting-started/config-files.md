---
sidebar_position: 4
---

# 設定ファイル

`speca init` は `outputs/` 配下に 2 つの JSON ファイルを生成します。これらがパイプラインに必要な唯一の入力です。本ページはその正規スキーマリファレンスです。

## `outputs/TARGET_INFO.json`

監査対象のコードベースを識別します。Phase 02c (正しいコミットをクローン) と Phase 03 (相対パス解決) が読み込みます。

```json
{
  "project_name": "lighthouse-audit-2026-05",
  "target_repo": "https://github.com/sigp/lighthouse",
  "target_commit": "v5.1.3",
  "target_language": "Rust",
  "target_layer": "consensus",
  "description": "Lighthouse Ethereum consensus client, v5.1.3"
}
```

| フィールド | 必須 | 備考 |
|---|---|---|
| `project_name` | ○ | 出力パスとレポートタイトルに使用 |
| `target_repo` | ○ | 公開 Git URL。SSH 鍵が通れば SSH URL も可 |
| `target_commit` | ○ | コミットハッシュ・ブランチ・タグ。再現性のためタグかハッシュへの固定を強く推奨 |
| `target_language` | ○ | 自由記述。`tree_sitter` MCP は実際にはファイル拡張子で言語判定するため、ここは目印 |
| `target_layer` | × | Phase 01e がどの CWE テンプレートを優先するかのヒント |
| `description` | × | レポート向けのフリーノート |

リポジトリは実行時に `target_workspace/` 配下にクローンされます。コミットする必要はありません。

## `outputs/BUG_BOUNTY_SCOPE.json`

監査スコープと重大度の定義です。**Phase 01e の必須入力** — 不在ならオーケストレータは `sys.exit(1)` で停止します。

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

  "scope_notes": "Only in-scope high-value code paths will be audited."
}
```

### トップレベルフィールド

| フィールド | 必須 | 備考 |
|---|---|---|
| `program_name` | ○ | 識別子。レポート見出しに使用 |
| `scope_version` | × | スコープ版数 (絞り込み再実行時など) |
| `in_scope` | ○ | グロブ・パスエントリ。Phase 04 Gate 3 はここに少なくとも 1 件マッチする finding を残す |
| `out_of_scope` | × | 明示的な除外。ここに当たる finding は Gate 3 で `DISPUTED_FP` に |
| `severity_classification` | ○ | 各重大度 (`CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `Informational`) を CWE と例にマップ |
| `scope_notes` | × | レポートに転記される自由記述 |

### なぜ重大度は **コード側ではなく** ここに置くのか

重大度は **プログラム固有の判断** です ("validators の 100% が止まる" 事象は consensus client では `CRITICAL`、それ以外では `HIGH`)。Phase 02c は `severity_classification` を使って `Informational` プロパティを監査前にドロップし、Phase 03 はコンテキストとして読み、Phase 04 で最終的な重大度を較正します。これをこのファイルに集約していることが、パイプライン本体をコンテスト非依存に保っているポイントです — ルブリックの差し替え例は [運用ガイド / RQ1 再現](../operations/benchmark-rq1.md) を参照してください。

### 複数実装間でルブリックを共有する

複数実装監査 (例: 同じ EIP を実装する 10 種の Ethereum クライアント) では `common_rubric` ブロックでスコープ記述を共通化します:

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

各実装が同じプロパティ語彙を継承するため、[実装間比較](../concepts/spec-driven.md#利点) が成立します。

## 健全性チェック

`speca doctor` は両ファイルがロード可能で、`severity_classification` がパースできることを検証します。手書きする場合は

```bash
speca doctor
```

を `speca run` の前に走らせてください。最初のパースエラーを行・列番号付きで報告します。

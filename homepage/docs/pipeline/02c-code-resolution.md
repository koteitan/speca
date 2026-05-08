---
sidebar_position: 5
---

# Phase 02c: コード解析 (Tree-sitter)

プロパティ定義をソースコード上の具体的位置に事前解析します。Tree-sitter MCP を使用。

## 前提条件

- `outputs/TARGET_INFO.json` が必須。対象リポジトリと commit hash を含む
- `outputs/BUG_BOUNTY_SCOPE.json` (Phase 01e から継承)

## 入力

- Phase 01e の出力 (`outputs/01e_PARTIAL_*.json`)
- Phase 01b の出力から構築した `outputs/01b_SUBGRAPH_INDEX.json`
- ターゲットコードベース

## 処理

1. **サブグラフインデックス構築**: 01b パーシャルから spec 関数名・状態遷移を索引化
2. **Tree-sitter シンボル解析**: `mcp__tree_sitter__get_symbols` で関数・構造体を取得
3. **コード位置解決**: プロパティの entry point をファイル・行番号にマップ
4. **重要度フィルタ**: Informational レベルを削減

## 出力

`outputs/02c_PARTIAL_*.json`

```json
{
  "property_id": "PROP-001",
  "type": "Invariant",
  "description": "Authentication state must be verified before accessing protected resources",
  "code_scope": {
    "file": "src/auth.rs",
    "line_range": [42, 68],
    "symbol": "verify_auth",
    "language": "rust"
  },
  "severity": "HIGH"
}
```

- `code_scope`: Tree-sitter で解析した具体的コード位置
- `severity`: BUG_BOUNTY_SCOPE.json の重要度分類

このプリ解析により Phase 03 の token 消費を 40-60% 削減。

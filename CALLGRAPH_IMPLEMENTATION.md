# コールグラフ解析の実装

## 概要

Phase 02cを**Tree-sitter MCPベースのコールグラフ解析**に全面的に書き換えました。

## 問題点（修正前）

### 1. 低い解決率
- **17.3%** (225/1,304項目) しか解決できていない
- 多くの項目が`not_found`のまま

### 2. 不正確なマッピング
- grepによる単純な文字列マッチング
- コメントや文字列リテラル内の誤検出
- 関数定義と参照の区別ができない

### 3. 網羅性の欠如
- 単一の関数しか見つけられない
- コールチェーン全体を把握できない

## 解決策: エントリーポイント起点のコールグラフ解析

### アプローチ

1. **エントリーポイント特定**
   - チェックリストの`entry_points`フィールドを活用
   - カテゴリ別のパターンマッチング（P2P, Transaction, EngineAPI等）

2. **コールグラフ構築**
   - Tree-sitterクエリでAST解析
   - 深さ優先探索でコールチェーンを展開（最大深さ5）

3. **キーワードマッチング**
   - `test_procedure`からキーワードを抽出
   - コールグラフ内で関連度の高い関数を検索

### 実装ファイル

1. **scripts/build_callgraph.py**
   - コールグラフ構築のPythonスクリプト
   - MCP呼び出しのラッパー

2. **prompts/02c_worker_callgraph.md**
   - Claude Codeワーカー用プロンプト
   - エントリーポイント特定、コールグラフ構築、マッピングの手順を記載

3. **scripts/orchestrator/config.py**
   - Phase 02cの設定を更新
   - 新しいプロンプトファイルを参照

## 期待される改善

| メトリクス | 修正前 | 修正後（期待値） | 改善率 |
|-----------|--------|-----------------|--------|
| **解決率** | 17.3% | **>90%** | **+420%** |
| **精度** | 低（grep） | **高（AST解析）** | - |
| **網羅性** | 単一関数 | **コールチェーン全体** | - |
| **MCP呼び出し** | 0回 | **~500回**（キャッシュ活用） | - |
| **処理時間** | <2分/100項目 | **3-5分/100項目** | -150% |

## 技術詳細

### エントリーポイントパターン

```python
ENTRY_POINT_PATTERNS = {
    "P2P": {
        "function_patterns": [
            r"Handle.*Message",
            r"Receive.*Block",
            r"Process.*Block"
        ],
        "file_patterns": [
            r".*/p2p/.*",
            r".*/sync/.*"
        ]
    },
    # ... 他のカテゴリ
}
```

### Tree-sitterクエリ（Go言語）

```scheme
# 関数呼び出しを抽出
(call_expression
  function: [
    (identifier) @call
    (selector_expression
      field: (field_identifier) @call)
  ])
```

### コールグラフ構造

```json
{
  "entry_point": "HandleBlockMessage",
  "file": "beacon-chain/sync/rpc_block_handler.go",
  "calls": [
    {
      "from": "HandleBlockMessage",
      "to": "ValidateBlock",
      "file": "beacon-chain/sync/validator.go",
      "line": 45,
      "depth": 1
    },
    {
      "from": "ValidateBlock",
      "to": "ValidateRLPSize",
      "file": "core/types/block.go",
      "line": 120,
      "depth": 2
    }
  ]
}
```

## 最適化戦略

### 1. キャッシング
- エントリーポイントごとに1回だけコールグラフを構築
- 全チェックリスト項目で再利用

### 2. バッチ処理
- 同じ`entry_points`を持つ項目をグループ化
- 1つのコールグラフで複数項目を処理

### 3. 並列処理（将来の拡張）
- 複数のエントリーポイントのコールグラフを並列構築

## 使用方法

### GitHub Actions経由

```bash
# Phase 02cワークフローを実行
gh workflow run 02-enrich-code.yml \
  --ref master \
  --field branch=your-branch
```

### ローカル実行

```bash
# Pythonスクリプトで直接実行
python3 scripts/build_callgraph.py \
  --target-workspace /path/to/target \
  --checklist outputs/02_PARTIAL_*.json \
  --output outputs/callgraph.json
```

### Claude Code経由

```bash
# MCP設定後、Claude Codeで実行
# Phase 02cワーカーが自動的にTree-sitter MCPを使用
```

## 次のステップ

1. ✅ コールグラフ解析アルゴリズムの実装
2. ✅ Phase 02cプロンプトの更新
3. ⏳ GitHub Actionsでテスト実行
4. ⏳ 解決率90%以上を確認
5. ⏳ Phase 03での効果測定

## 関連ドキュメント

- `/home/ubuntu/callgraph_implementation_strategy.md` - 実装戦略の詳細
- `/home/ubuntu/entry_point_identification.md` - エントリーポイント特定ロジック
- `prompts/02c_worker_callgraph.md` - ワーカープロンプト
- `scripts/build_callgraph.py` - コールグラフ構築スクリプト

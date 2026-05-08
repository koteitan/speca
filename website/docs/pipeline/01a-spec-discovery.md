---
sidebar_position: 2
---

# Phase 01a: 仕様発見

シード URL から仕様書を再帰的に発見・クローリングします。

## 入力

`SPEC_URLS` 環境変数に仕様書の開始 URL を指定します。

```bash
SPEC_URLS="https://github.com/ethereum/EIPs/blob/master/EIPS/eip-7594.md" \
  uv run python3 scripts/run_phase.py --phase 01a
```

複数 URL の場合はスペース区切り:

```bash
SPEC_URLS="https://example.com/spec1.md https://example.com/spec2.md" \
  uv run python3 scripts/run_phase.py --phase 01a
```

## 処理

- `mcp__fetch__fetch` MCP ツールで URL をフェッチ
- HTML → Markdown に変換
- リンク構造を解析して関連ドキュメントを発見
- 訪問済み URL は重複を避ける

## 出力

`outputs/01a_STATE.json` — 発見された全ドキュメントのインデックス

```json
{
  "urls": [
    {
      "url": "https://...",
      "title": "EIP-7594: ...",
      "content": "...",
      "links": ["https://...", ...]
    }
  ],
  "crawl_timestamp": "2026-05-07T12:00:00Z"
}
```

このファイルは Phase 01b の入力として使用されます。

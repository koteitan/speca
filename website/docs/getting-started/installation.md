---
sidebar_position: 1
---

# インストール

SPECA のインストール方法は 2 通りあります。エンドユーザー向けの **CLI グローバルインストール** と、コントリビュータ・ベンチマーク再現向けの **ソースインストール** です。

## 前提

- **Node.js 20 以上** — CLI フロントエンドの実行に必要です。
- **Python 3.11 以上** + [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — オーケストレータの実行に必要です。
- **git** — 監査時に対象リポジトリをクローンします。
- **Claude Code CLI** (`@anthropic-ai/claude-code`) — `speca-cli` の peer として自動インストールされます。`claude` でサインインするか、`ANTHROPIC_API_KEY` を設定してください。

## オプション A — グローバル CLI (推奨)

```bash
# 1 回だけの環境チェック (インストール不要)
npx speca-cli@latest doctor

# 永続インストール
npm install -g speca-cli
speca doctor
```

これで `speca` コマンドが PATH 上に乗ります。論文ベンチマークの再現や本体への貢献をするとき以外は、ソースコードを取得する必要はありません。

## オプション B — ソースから

```bash
git clone https://github.com/NyxFoundation/speca.git
cd speca

# オーケストレータの Python 依存をインストール
uv sync

# CLI フロントエンドをビルド
cd cli && npm install && npm run build && cd ..

# ビルド済みバイナリを PATH に置くか …
npm link --prefix cli

# … ローカルビルドを直接呼ぶ
node cli/dist/cli.js doctor
```

このサイトの残りは `speca <subcommand>` で書かれています。`npm link` を使わない場合は `node cli/dist/cli.js <subcommand>` に読み替えてください。

## MCP サーバーの登録

Phase 01a (Spec Discovery) と Phase 02c (Code Pre-resolution) は MCP サーバーを呼びます。1 度だけ登録します:

```bash
bash scripts/setup_mcp.sh           # ソース版 — fetch + tree_sitter を登録
bash scripts/setup_mcp.sh --verify  # 各サーバーが応答するか確認
```

CLI 版は同等の登録ロジックを内蔵しています。サーバーが見つからない場合は `speca doctor` が指摘してくれます。

## 環境チェック

```bash
speca doctor
```

期待される出力:

```
[ok] Node.js 20.x
[ok] Python 3.11 (uv)
[ok] Claude Code CLI authenticated
[ok] MCP servers: fetch, tree_sitter
```

`[err]` が出たら表示されるメッセージに従ってください。`speca doctor` は失敗ごとに具体的な対処コマンドを表示します。

## 次のステップ

→ [クイックスタート](./quickstart.md) — 5 分で初回監査。

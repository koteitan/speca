---
sidebar_position: 1
---

# インストール

SPECA を実行するための環境構築手順です。

## 前提条件

- Node.js 20 以上
- Python 3.11 以上 + `uv` パッケージマネージャ
- git
- Claude Code CLI (`@anthropic-ai/claude-code`)
- Anthropic API キー (`ANTHROPIC_API_KEY` として環境変数に設定、または Claude Code でログイン)

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/NyxFoundation/speca.git
cd speca
```

### 2. Claude Code CLI をインストール

```bash
npm install -g @anthropic-ai/claude-code
```

### 3. Python 依存をセットアップ

```bash
uv sync
```

### 4. MCP サーバーを登録

```bash
bash scripts/setup_mcp.sh
bash scripts/setup_mcp.sh --verify
```

`--verify` コマンドで各 MCP サーバー (tree_sitter / filesystem / fetch) が正常に登録されていることを確認します。

## 環境検証

```bash
speca doctor
```

システムの準備が整っていることを確認します。

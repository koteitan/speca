---
sidebar_position: 3
---

# とりあえず動かしてみる

5 分で SPECA を試すための手順です。

## 必要なもの

- Node.js 20 以上
- Python 環境管理ツール `uv` ([インストール](https://docs.astral.sh/uv/getting-started/installation/))
- Git
- Claude Code CLI ([インストール](https://claude.ai/download)、無料版あり。監査実行には Claude Pro または Max サブスクリプションを推奨)

## ステップバイステップ

### 1. リポジトリを clone する

```bash
git clone https://github.com/NyxFoundation/speca.git
cd speca
```

### 2. Python 環境をセットアップする

```bash
uv sync
```

プロジェクトに必要な Python パッケージをインストールします。

### 3. CLI ツールをビルドする

```bash
cd cli
npm install
npm run build
cd ..
```

Node.js 版のコマンドラインツール (speca-cli) をビルドします。

### 4. 環境を確認する

```bash
node cli/dist/cli.js doctor
```

Node.js・Python・Claude API の各依存関係が正しく設定されているか確認します。エラーが出た場合は、表示されたメッセージに従って修正してください。

### 5. プロジェクト設定を初期化する

```bash
node cli/dist/cli.js init
```

対象リポジトリの URL やセキュリティスコープなどを対話形式で入力します。`outputs/TARGET_INFO.json` と `outputs/BUG_BOUNTY_SCOPE.json` が生成されます。これら 2 つのファイルがパイプライン全体の入力になります。

### 6. 監査を実行する

```bash
node cli/dist/cli.js run --target 04
```

Phase 01a から Phase 04 まで順に実行します。完了まで数分〜数十分かかります。進捗はターミナルにリアルタイムで表示されます。

### 7. 結果を確認する

```bash
node cli/dist/cli.js browse
```

検出された脆弱性の候補を一覧表示します。各項目にはコード位置・セキュリティプロパティ・重要度 (severity) と判定 (verdict) が付いています。

## トラブルシューティング

### 「Empty results」で終わる

`outputs/BUG_BOUNTY_SCOPE.json` が見つからない、または中身が空の可能性があります。以下を確認してください。

- `speca init` を実行して設定ファイルを生成したか
- 対象リポジトリの GitHub Issues や Wiki に仕様情報があるか

詳しくは [FAQ](faq.md) の「specs が見つからない」の項目を参照してください。

### その他のエラー

[FAQ](faq.md) を確認するか、[GitHub Issues](https://github.com/NyxFoundation/speca/issues) へ報告してください。

## 次のステップ

- 結果の読み方を詳しく知りたい: [概念](../concepts/spec-driven.md)
- コマンドの詳細: [クイックスタート](../getting-started/quickstart.md)
- よくある質問: [FAQ](faq.md)

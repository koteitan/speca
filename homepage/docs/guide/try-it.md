---
sidebar_position: 3
---

# とりあえず動かしてみる

5 分で SPECA を試すための手順です。

## 必要なもの

- Node.js 20 以上
- Python 環境管理ツール `uv`（[インストール](https://docs.astral.sh/uv/getting-started/installation/)）
- Git
- Claude Code CLI（[インストール](https://claude.ai/download)、無料版あり。セキュリティ監査には Claude Pro または Max サブスクの利用を推奨）

## ステップバイステップ

### 1. リポジトリを clone する

```bash
git clone https://github.com/NyxFoundation/speca.git
cd speca
```

このコマンドで、SPECA のコード一式がローカルに コピーされます。

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

Node.js 版のコマンドラインツールをビルドします。

### 4. 環境をチェックする

```bash
node cli/dist/cli.js doctor
```

必要な環境（Node、Python、Claude API）が正しくセットアップされているか確認します。エラーが出た場合は、表示されたメッセージに従って修正してください。

### 5. プロジェクト設定を初期化する

```bash
node cli/dist/cli.js init
```

対象となるコードベースの情報（GitHub リポジトリ URL やセキュリティスコープなど）を入力します。設定ファイルが生成されます。

### 6. 実際に監査を実行する

```bash
node cli/dist/cli.js run --target 04
```

SPECA が 6 つの段階（Phase）を順に実行します。処理が完了するまで数分かかります。

### 7. 結果を確認する

```bash
node cli/dist/cli.js browse
```

検出された脆弱性の候補を表示します。各項目にはコード位置、セキュリティプロパティ、重要度（severity）が記載されています。

## トラブルシューティング

### 「Empty results」で終わる

仕様書（BUG_BOUNTY_SCOPE.json など）が見つからなかった可能性があります。以下を確認してください：

- リポジトリに BUG_BOUNTY_SCOPE.json または TARGET_INFO.json が存在するか
- GitHub Issues や Wiki に仕様情報があるか

詳しくは [FAQ](faq.md) の「specs が見つからないって出た」を参照。

### エラーが出た

設定が不足している場合があります。[FAQ](faq.md) を確認するか、GitHub Issues へ報告してください。

## 次のステップ

- 結果をもっと深く理解したい：[概念](../concepts/spec-driven.md)
- コマンドの詳細オプション：[クイックスタート](../getting-started/quickstart.md)
- よくある質問：[FAQ](faq.md)

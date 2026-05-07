---
sidebar_position: 4
---

# よくある質問

## 監査が「Empty results」で終わります

`outputs/BUG_BOUNTY_SCOPE.json` が見つからないか、中身が空の可能性があります。`speca init` を実行して設定ファイルを生成したか確認してください。対象リポジトリに仕様情報 (GitHub の Bug Bounty ページ・Issues・Wiki など) があるかも確認し、必要であれば JSON ファイルを手動で作成してください。

## Claude のサブスクリプションなしで使えますか？

Claude Code CLI は無料でインストールできますが、監査の実行中は Claude API を呼び出すため利用料が発生します。Claude Pro または Max サブスクリプションを契約すると月額料金が固定されます。詳細は [Claude.ai](https://claude.ai) でご確認ください。

## 対象が Solidity ではありませんが使えますか？

使えます。SPECA は Go・Rust・Nim・TypeScript・C など複数の言語に対応しています。仕様書で規定されたシステムであれば、言語を問わず監査できます。

## 結果が大量に出て、どれが重要か分かりません

各検出には `severity` (重要度) と `verdict` (判定) が付いています。`CONFIRMED_VULNERABILITY` が最も信頼度が高く、`CONFIRMED_POTENTIAL` は潜在的なリスク、`DISPUTED_FP` は誤検出の可能性があります。`browse` コマンドのフィルタオプション (`--severity high` など) で絞り込んでください。

## 「specs が見つからない」というエラーが出ました

`outputs/TARGET_INFO.json` または `outputs/BUG_BOUNTY_SCOPE.json` が存在しないか空になっています。以下を確認してください。

- `speca init` を実行して設定ファイルを作成したか
- 対象リポジトリの Bug Bounty スコープページ・Issues・Wiki に仕様が記載されているか
- 必要に応じて JSON ファイルを手動で作成する

詳しくは [クイックスタート](../getting-started/quickstart.md) を参照してください。

## 監査にどのくらい時間がかかりますか？

コードベースの規模や複雑さによりますが、小さなリポジトリで 5〜15 分、大規模なプロジェクトだと 1 時間以上かかることがあります。`run` コマンドは進捗をリアルタイムで表示するため、並行して他の作業もできます。

## その他の質問は？

[GitHub Issues](https://github.com/NyxFoundation/speca/issues) で質問してください。

---
sidebar_position: 4
---

# よくある質問

## 監査が「Empty results」で終わります

仕様ファイル（BUG_BOUNTY_SCOPE.json）が見つからないか、空の可能性があります。対象リポジトリに仕様情報（GitHub の Bug Bounty ページ、Issues、Wiki など）があるか確認し、BUG_BOUNTY_SCOPE.json を作成してください。

## Claude のサブスク無くても使えますか？

Claude Code CLI は無料でインストールできますが、実際に監査を実行する際は Claude API にアクセスしているため API 利用料が発生します。Claude Pro または Max サブスクを契約することで、月々の額が安定します。詳細は Claude.ai でご確認ください。

## 自分のリポジトリは Solidity ではありませんが対応していますか？

SPECA は Go、Rust、Nim、TypeScript、C など複数の言語に対応しています。仕様書で規定されたシステムであれば、言語を問わず監査可能です。

## 結果がたくさん出すぎて、どれが重要か分かりません

各検出には severity（重要度）と verdict（判定）が付いています。CONFIRMED_VULNERABILITY が最も信頼度が高く、CONFIRMED_POTENTIAL は潜在的なリスク、DISPUTED_FP は誤検出の可能性があります。severity で絞り込むか、`browse` コマンドのフィルタオプションを使ってください。

## 「specs が見つからない」というエラーが出ました

対象リポジトリに TARGET_INFO.json や BUG_BOUNTY_SCOPE.json が無い、または空である可能性があります。以下を確認してください：

- GitHub のバグバウンティスコープページを確認
- Issues または Wiki にシステムの仕様が記載されているか
- 必要に応じて JSON ファイルを手動で作成

詳しくは [クイックスタート](../getting-started/quickstart.md) を参照。

## 監査にどのくらい時間がかかりますか？

コードベースの規模や複雑さによりますが、通常 5 分から数十分です。大規模プロジェクトの場合は 1 時間以上かかることもあります。`run` コマンドは進捗を表示するため、その間に他の作業をできます。

## その他の質問は？

[GitHub Issues](https://github.com/NyxFoundation/speca/issues) で質問してください。コミュニティが答えています。

---
sidebar_position: 2
---

# クイックスタート (5分)

初回監査を 5 分で体験する手順です。

## セットアップ (1分)

対象コードベースのメタデータを生成します。

```bash
cd speca
speca init
```

このコマンドで `outputs/TARGET_INFO.json` と `outputs/BUG_BOUNTY_SCOPE.json` が生成されます。

## 監査パイプライン実行 (3分)

Phase 01a から Phase 04 までを一括実行します。

```bash
uv run python3 scripts/run_phase.py --target 04 --workers 4
```

パイプラインの進行状況を確認できます。各フェーズの詳細は[パイプライン](../pipeline/overview.md)を参照してください。

## 結果確認 (1分)

ブラウザで結果を閲覧します。

```bash
speca browse outputs/04_PARTIAL_*.json
```

各検出項目 (finding) について、対応するプロパティ、証明試行 (proof attempt) の詳細、3ゲートレビューの結果が表示されます。

## 詳細分析

Claude Code CLI で自由に質問できます。

```bash
speca ask "なぜこの脆弱性が検出されたのか"
```

証明試行の根拠 (proof gap) や仕様レベルの制約がどの部分で破られているかを確認できます。

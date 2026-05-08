---
sidebar_position: 3
---

# とりあえず動かしてみる

5 分で完了するウォークスルー。小さな公開リポジトリに対して初回監査を走らせます。

## 前提

- Node.js 20 以上
- Python 3.11 + [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- git
- Claude API キー (Claude Pro/Max 契約による課金、または従量制 API キー)

## 手順

### 1. CLI をインストール

```bash
npm install -g speca-cli
speca doctor
```

`speca doctor` が Node / Python / Claude Code / MCP サーバーを検証します。`[err]` 行があれば、表示される対処メッセージに従ってください。

グローバルインストールを避けたい場合は、本サイトの `speca` を `npx speca-cli@latest` に置換すれば全コマンドが動きます。

### 2. Claude にサインイン

```bash
speca auth login
```

API キーを `~/.config/speca/auth.json` に保存するか、既存の Claude Code セッションに乗ります。

### 3. 設定ファイルを生成

```bash
speca init
```

対象リポジトリ URL、言語とレイヤー、スコープルブリックを尋ねられます。`outputs/TARGET_INFO.json` と `outputs/BUG_BOUNTY_SCOPE.json` を書き出します。手動で書く場合は [設定ファイル](../getting-started/config-files.md) を参照してください。

### 4. 監査を実行

```bash
speca run --target 04 --workers 4
```

Phase 01a → 01b → 01e → 02c → 03 → 04 が順に実行され、TUI ダッシュボードに進捗とコストがリアルタイム表示されます。小型リポジトリは典型的に 5〜15 分、本番サイズのクライアントは 1〜3 時間。`--budget 50` で $50 を上限に固定できます。

ダッシュボードは大体こんな見た目になります — ヘッダに累積コスト、各フェーズに進捗とアクティブワーカー数:

```
SPECA · openzeppelin-ownable-walkthrough          cost: $1.42 / $50 budget
─────────────────────────────────────────────────────────────────────────
01a Spec Discovery     ████████████████████  done   23 sections   $0.18
01b Subgraph Extract   ████████████████████  done   12 subgraphs  $0.24
01e Property Gen       ████████████████████  done   18 props      $0.31
02c Code Resolution    ████████░░░░░░░░░░░░  3 / 18 workers=4    $0.21
03 Audit Map           ░░░░░░░░░░░░░░░░░░░░  pending             —
04 Review              ░░░░░░░░░░░░░░░░░░░░  pending             —
```

### 5. 結果を閲覧

```bash
speca browse
speca browse --severity Critical
speca browse --filter "verdict:CONFIRMED_*"
```

各行はプロパティ・コード抜粋・proof gap・ゲートトレースを表示します。`c` でコード覗き、`f` でフィルタ編集、`q` で終了。完全なフィルタ DSL は [CLI リファレンス / browse](../getting-started/cli-reference.md#speca-browse) にあります。

### 6. 個別調査

```bash
speca ask                                # 最初の finding を選択
speca ask PROP-abc-001 --from outputs/04_PARTIAL_*.json
```

その finding のコンテキストをロードした Claude Code セッションを開きます。

## コストと所要時間の目安

| コードベース | 実時間 | コスト (Sonnet 4.5) |
|---|---|---|
| 小型コントラクト (~1K LoC) | 5〜10 分 | $1〜5 |
| 中規模リポジトリ (~50K LoC) | 15〜40 分 | $20〜50 |
| 本番クライアント (~500K LoC) | 1〜3 時間 | $50〜100 |

コスト管理の詳細は [モデル選定の設計ノート](../design-notes/model-benchmark-takeaways.md) を参照してください。

## トラブルシューティング

### Phase 01a で「Empty results」

`outputs/BUG_BOUNTY_SCOPE.json` が無いか、`in_scope` が空です。`speca init` を再実行するか手で編集します。詳細は [設定ファイル](../getting-started/config-files.md)。

### 終了コード 64 / 65 で停止した

- **64** — `--budget` に到達。上限を引き上げるかスコープを絞ります。
- **65** — サーキットブレーカー作動。`outputs/logs/<phase>_*.jsonl` で原因を確認 (大半は一時的な API エラー)。詳細は [ハーネスの内部](../agent-design/harness.md)。

### その他のエラー

[FAQ](faq.md) · [GitHub Issues](https://github.com/NyxFoundation/speca/issues)。

## 初回監査が終わったあと

`speca browse` が開いたら finding のリストが手元に来ています。次の質問はだいたいこうなります:

- **「どれが本物?」** — まず `--severity High --filter "verdict:CONFIRMED_*"`。verdict の意味は [3 ゲートレビュー](../concepts/gate-review.md)。
- **「なぜ X は dismiss された?」** — `DISPUTED_FP` は弾いたゲートを記録しています。`browse` の `Enter` で展開できます。
- **「証明のどのステップが失敗したのか?」** — `speca ask <property_id>` で finding のフルコンテキスト付きセッションを開きます。
- **「どこかで本物の仕様の文に遡れる?」** — はい、すべての finding が遡れます。連鎖は [ワークドエグザンプル](../concepts/worked-example.md) に図示されています。

## 次のステップ

- [CLI リファレンス](../getting-started/cli-reference.md) — 全フラグ
- [パイプライン概要](../pipeline/overview.md) — 各フェーズの役割
- [概念](../concepts/spec-driven.md) — なぜこの設計が成立するか
- [ワークドエグザンプル](../concepts/worked-example.md) — 1 つのプロパティを最後まで追う

---
sidebar_position: 4
---

# よくある質問

## セットアップとインストール

### Claude のサブスクリプションは必要?

Claude Code CLI 自体は無料ですが、監査実行時に Claude API を呼ぶため使用料が発生します。Claude Pro / Max 契約だとコストが見通しやすく、従量制 API キーでも動きます。

### CLI を更新するには?

```bash
npm update -g speca-cli
speca doctor
```

`speca doctor` で新バージョンが正しく動作するか確認できます。

### グローバル npm install を避けたい

サイト内の `speca <subcommand>` を `npx speca-cli@latest <subcommand>` に置き換えれば動きます。トレードオフは `npx` の起動ごとの解決時間です。

### 出力はどこに保存される?

デフォルト: `./outputs/`。`speca run --output-dir <path>` か環境変数 `SPECA_OUTPUT_DIR` で上書きできます。監査出力はローカルにのみ保存され、SPECA がアップロードすることはありません。

## 実行

### 「Empty results」で終わる

`outputs/BUG_BOUNTY_SCOPE.json` が無いか、空か、`in_scope` がどれにもマッチしていません。`speca init` を再実行するか、[スキーマ](../getting-started/config-files.md) を参考に手編集します。

### 中断・再開できる?

はい。`Ctrl-C` は安全です。それまでに書かれた partial ファイルは残ります。同じコマンドを再実行すれば、resume manager が `*_PARTIAL_*.json` を走査して処理済み項目をスキップします。最初からやり直すには `--force` を付けます。

### コストに上限を設けるには?

```bash
speca run --target 04 --budget 50
```

オーケストレータは $50 を超えた瞬間にフェーズを停止し、終了コード 64 を返します。フェーズ単位でのトラッキングについては [ハーネスの内部](../agent-design/harness.md) を参照。

### どの Claude モデルが使われる?

現在の構成:

- **Phase 01a / 01b / 01e** — Claude Opus (knowledge structuring。プロパティ品質がカバレッジを縛る)
- **Phase 02c / 03 / 04** — Claude Sonnet 4.5 (verification。同等精度をより安価かつ高速に)

その理由とデータは [モデル選定の設計ノート](../design-notes/model-benchmark-takeaways.md) を参照してください。

### 対象が Solidity でない場合も使える?

はい。SPECA は言語非依存です。動作確認済みは Go / Rust / Nim / TypeScript / C / C++ / Solidity。仕様 (RFC・EIP・論文・設計ドキュメント・しっかり書かれた README など) が存在するシステムなら、プロパティを導出できます。

### 公開仕様がなくコードのみ

それだと SPECA は十分に機能しません。仕様からプロパティを導出する設計のため、コードしかないとプロパティ生成器に手がかりがありません。従来のコードパターン型スキャナの方が向いています。

## 結果の読み方

### 大量の finding が出る — どれが重要?

各 finding は `severity` (`Critical` / `High` / `Medium` / `Low` / `Informational`) と `verdict` を持ちます:

| Verdict | 意味 |
|---|---|
| `CONFIRMED_VULNERABILITY` | 最高信頼度 — 3 ゲートを全通過 |
| `CONFIRMED_POTENTIAL` | 真の懸念。スコープ外でも見る価値あり |
| `DOWNGRADED` | 真だがプロパティが示唆したより影響が小さい |
| `NEEDS_MANUAL_REVIEW` | 結論不能 — 人間判断が必要 |
| `DISPUTED_FP` | Gate 1/2/3 で除外 |
| `PASS_THROUGH` | 上記以外 |

まずは `speca browse --severity High --filter "verdict:CONFIRMED_*"` から見るのがおすすめです。

### なぜ FP と判定されたのか?

`DISPUTED_FP` はどのゲートで弾かれたか記録されます。各ゲートの判定基準は [3 ゲートレビュー](../concepts/gate-review.md) を参照してください。

## エラーと制限

### "specs not found"

`TARGET_INFO.json` か `BUG_BOUNTY_SCOPE.json` が無いか空です。[設定ファイル](../getting-started/config-files.md) を参照。Phase 01a の探索挙動については [パイプライン / 01a](../pipeline/01a-spec-discovery.md)。

### サーキットブレーカー (終了コード 65)

フェーズ内で連続失敗が閾値を超えました。多くは API の一時エラーかプロンプト不具合です。`outputs/logs/<phase>_*.jsonl` を確認してください。閾値の詳細は [ハーネスの内部](../agent-design/harness.md)。

### 監査時間は?

小型リポジトリで 5〜15 分、本番クライアントで 1〜3 時間。Phase 03 が実時間を支配します。Phase 02c のトークン削減 (40〜60%) で課金は抑えられます。

## その他

[GitHub Issues](https://github.com/NyxFoundation/speca/issues) へどうぞ。

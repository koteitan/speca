---
sidebar_position: 2
---

# クイックスタート (5 分)

初回監査までを 5 分で済ませる手順です。[インストール](./installation.md) が完了していて `speca doctor` がグリーンであることを前提にします。

## 1. Claude にサインイン (1 度だけ)

```bash
speca auth login
```

API キーを `~/.config/speca/auth.json` に保存するか、`claude` のセッションを利用するかを選びます。`speca auth status` で現在の認証状態を確認できます。

## 2. 設定ファイルを生成

```bash
speca init
```

対話で以下を尋ねられます:

- **対象リポジトリ** の URL とコミット/タグ
- **対象言語** と **レイヤー** (consensus / execution / application / …)
- **スコープルブリック** — まずは `default` ([ethereum.org rubric](./config-files.md)) を選択。独自ルールにする場合は `custom`。

`outputs/TARGET_INFO.json` と `outputs/BUG_BOUNTY_SCOPE.json` が生成されます。これらがパイプライン全体の入力になります。スキーマの詳細は [設定ファイル](./config-files.md) にあります。

非対話形式:

```bash
speca init \
  --target-repo https://github.com/sigp/lighthouse \
  --target-commit v5.1.3 \
  --target-language Rust \
  --target-layer consensus \
  --rubric default \
  --non-interactive
```

## 3. 監査を実行

```bash
speca run --target 04 --workers 4
```

Phase 01a → 01b → 01e → 02c → 03 → 04 が依存関係順に実行され、TUI ダッシュボードに進捗とコストがリアルタイムで表示されます。フェーズ ID の意味は [パイプライン概要](../pipeline/overview.md) を参照してください。

主要なフラグ:

| フラグ | 効果 |
|---|---|
| `--target 04` | Phase 04 まで全フェーズを実行 |
| `--phase 03 04` | 指定したフェーズのみ |
| `--workers 4` | 各フェーズのワーカー数 |
| `--max-concurrent 8` | Claude 同時起動数の上限 |
| `--budget 50` | $50 を超えたらフェーズを停止 |
| `--force` | resume 状態を無視して再実行 |
| `--json` | TUI の代わりに NDJSON を流す |

すべてのフラグは [CLI リファレンス](./cli-reference.md) にあります。

## 4. 結果を閲覧

```bash
speca browse                     # デフォルト: outputs/04_PARTIAL_*.json
speca browse --severity Critical
speca browse --filter "severity:High AND verdict:CONFIRMED_*"
```

TUI が各 finding のプロパティ、コード抜粋、proof gap、ゲートトレースを表示します。`c` でコード覗き、`f` でフィルタ編集、`q` で終了。

## 5. 個別調査

```bash
speca ask                        # 最初の finding を対話的に選択
speca ask PROP-abc-001 --from outputs/04_PARTIAL_*.json
```

その finding のコンテキストを事前にロードした Claude Code セッションを開きます。「証明のどのステップが失敗しているか」「最小修正パッチ」を尋ねるのに便利です。

## 期待される出力

`speca browse` の典型的な行:

```
PROP-001  HIGH   CONFIRMED_VULNERABILITY   src/auth.rs:85
  proof_gap: "Missing auth check in error_handler() — unreachable path
              skips verify_auth() before sensitive_data()"
  gates: dead_code=PASS · trust_boundary=PASS · scope=PASS
```

verdict の意味は [3 ゲートレビュー](../concepts/gate-review.md) を参照してください。

## どれくらいの時間とコストがかかるか

RQ1 / RQ2 から見積もれる目安:

| コードベース | 実時間 (Phase 03 が支配的) | コスト (Sonnet 4.5) |
|---|---|---|
| 小型コントラクト (~1K LoC) | 5〜10 分 | $1〜5 |
| 中規模リポジトリ (~50K LoC) | 15〜40 分 | $20〜50 |
| 本番クライアント (~500K LoC) | 1〜3 時間 | $50〜100 |

コスト管理のさらなる手段は [モデル選定の設計ノート](../design-notes/model-benchmark-takeaways.md) にあります。

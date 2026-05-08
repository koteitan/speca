---
sidebar_position: 2
---

# ハーネス

`scripts/orchestrator/` 配下の非同期 Python オーケストレータがハーネスです。ユーザー起動 (`speca run --target 04`) と各バッチの Claude 呼び出しの間に挟まる層で、どのフェーズが走っているかに関わらず必要な機能 — 並列化、リトライ、コスト管理、resume、構造化ログ — をすべて担います。

## モジュール一覧

| モジュール | 担当 |
|---|---|
| `config.py` | `PhaseConfig` Pydantic モデル — プロンプトパス、IO glob、バッチ戦略、サーキットブレーカー閾値、コスト上限、MCP サーバー、ツール許可を宣言 |
| `base.py` | `BaseOrchestrator` — 入力ロード、Pydantic 検証、resume フィルタ、バッチ化、`asyncio.gather` で実行 |
| `runner.py` | `ClaudeRunner` — バッチごとに `claude` を `--prompt-path` + `--stream-json` で起動。`CircuitBreaker` と指数バックオフリトライを持つ |
| `watchdog.py` | `LogWatcher` (stream-json リアルタイム追従) + `CostTracker` (USD 上限。`BudgetExceeded` を投げる) |
| `resume.py` | `ResumeManager` — `*_PARTIAL_*.json` をスキャンして処理済み ID 集合を作る |
| `collector.py` | `ResultCollector` — partial を即座に保存。検証は寛容 (warn は出すが書き込みはブロックしない) |
| `schemas.py` | フェーズ間の全契約を表現する Pydantic モデル |

## エンドツーエンドの実行フロー

```
speca run --target 04
        │
        ▼
┌───────────────────────┐
│  PhaseConfig          │  ← config.py がフェーズ定義を選択
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│  ResumeManager        │  ← outputs/<phase>_PARTIAL_*.json をスキャン
│  → 処理済み ID         │     既に partial を出した項目をスキップ
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│  バッチビルダー        │  ← 残作業を N 個のキューファイルに分割
└───────────┬───────────┘     (ワーカー 1 つにつき 1 ファイル)
            ▼
┌─────────────────────── parallel × workers ──────────────────────────┐
│  ClaudeRunner          ClaudeRunner          ClaudeRunner           │
│   • claude を spawn    • claude を spawn    • claude を spawn       │
│   • LogWatcher          • LogWatcher          • LogWatcher          │
│   • トークン集計        • トークン集計        • トークン集計        │
│   • 一時障害ならリトライ • 一時障害ならリトライ • 一時障害ならリトライ│
└─────────────────────────────────┬────────────────────────────────────┘
                                  ▼
┌───────────────────────┐    ┌───────────────────────┐
│  ResultCollector      │    │  CostTracker          │
│  → PARTIAL_*.json     │    │  → BudgetExceeded     │
└───────────┬───────────┘    └───────────┬───────────┘
            ▼                            ▼
            └────────► 次フェーズ    ─►  終了コード 64 (即停止)
```

## サーキットブレーカー

フェーズあたり 1 つの共有インスタンス。以下のいずれかで作動:

| カウンタ | デフォルト閾値 | 理由 |
|---|---|---|
| `consecutive_failures` | 5 | 系統的問題 (壊れたプロンプト、モデル障害)。続けるのは予算の浪費 |
| `total_retries` | 20 | 散発的一時エラーであれ、ここまで来たら構造的問題 |
| `consecutive_empty_results` | 3 | 空出力は通常 `MaxTurnsExhausted` の症状かプロンプト退行 |

作動すると `CircuitBreakerTripped` を投げ、オーケストレータは実行中タスクをキャンセルし終了コード **65** で抜けます。それまでの状態は partial として保存済みです。

## リトライ方針

リトライは **すべての失敗に適用されるわけではありません**。

| 失敗 | リトライ? | 補足 |
|---|---|---|
| 一時 API エラー (rate limit, 5xx) | する — 指数バックオフ、最大 3 回 | 最も多いケース |
| `MaxTurnsExhausted` | **しない** | 決定論的。再実行しても同じ出力 |
| 出力スキーマ検証失敗 | しない | collector はログを残し partial を書き込む (寛容) |
| `BudgetExceeded` | しない | 即終了 |
| `CircuitBreakerTripped` | しない | 全ワーカーをキャンセル |

`MaxTurnsExhausted` の区別は重要です。決定論的失敗をリトライするのは無駄ですし、そっと続行すれば予算上限を実質的に押し上げてしまいます。

## コスト管理と予算

`CostTracker` は各バッチの stream-json 出力からトークン消費を抽出し、フェーズごとに USD を積み上げます。価格モデルはそのフェーズが使うモデルでキー付けされます。`--budget <usd>` が指定されていれば、合計が上限を超えた瞬間に `BudgetExceeded` を投げ、ランナー側で **終了コード 64** に変換します。

運用上の含意は 2 つ:

- **コストはフェーズ単位で上限を設ける、CLI ラン全体ではない。** 6 フェーズランで `--budget 50` の場合、どれか 1 フェーズで $50 まで使い切れます。本気で抑えたければフェーズ単独で実行してください。
- **ダッシュボードは実時間でコストを表示する。** これが LogWatcher の役目です — stream-json を追従し TUI にコストイベントを送ります。

## Resume

ハーネスにおける最も安価なトークン節約機能です。フェーズ実行前:

1. `ResumeManager` が `outputs/<phase>_PARTIAL_*.json` を全部読みます。
2. 結果を出した `item_id` の集合を作ります。
3. バッチビルダーがその ID をキューから除外します。

これで `Ctrl-C` が安全になり (次のランで続きから)、部分失敗フェーズの再実行は無料になります。`--force` で resume フィルタをクリアして全件再実行。

## Partial ファイルは設計判断

`ResultCollector` はバッチ完了直後に partial を書きます。意味するところ:

- **クラッシュしたランの損失は実行中バッチ分だけ。**
- **検証はあえて寛容。** 1 件のスキーマ不一致は warn で、partial は書かれます。次のフェーズが消費可能な状態を保ちます。
- **Resume はディレクトリスキャンだけ。** ステート DB なし、ラン UUID なし、孤児クリーンアップなし。

トレードオフは「ファイル数が増える」こと。代替案 (SQLite など) は不透明で grep しづらく、ベンチマーク成果物として publish できないため、ディスク使用量は受け入れています。

## ワーカー / バッチサイズ

`PhaseConfig.batch_strategy` がアイテムをどう Claude 呼び出しにまとめるかを宣言します。多くのフェーズはバッチサイズ 1 — 1 プロパティ単位でプロンプトをサイズしているため、並列度はワーカー数で稼ぎます。`--workers` がワーカー数、`--max-concurrent` が同時 Claude プロセス数の上限。

経験的 (RQ2 再現) に `--workers 4 --max-concurrent 8` で 1 API キーをレートリミットなしで使い切れます。さらに大きい構成にはまだ実装されていない共有レート管理が必要です。

## コードを読み始める順番

ハーネスを拡張するなら次の順で読むのがおすすめです: `config.py` (宣言形)、`base.py` (オーケストレーション)、`runner.py` (プロセス管理)、`watchdog.py` (コスト + ログストリーム)。依存関係は意図的に浅く、各モジュールは 600 LOC 以下です。

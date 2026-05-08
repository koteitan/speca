---
sidebar_position: 1
---

# パイプライン概要

SPECA は 6 ステージから成るパイプラインです。前半 3 ステージは仕様を型付きプロパティに変換 (Knowledge Structuring)、後半 3 ステージはそのプロパティを実装に対して監査します (Systematic Auditing)。

![SPECA パイプライン](/img/diagrams/pipeline.png)

## フェーズ番号 — 論文 vs 内部 ID

2 本の SPECA 論文ではステージを **Phase 1〜6** と呼びます。一方、コードベースは開発時の順序を反映した内部 ID (`01a` / `01b` / `01e` / `02c` / `03` / `04`) を使います。指しているステージは同じです。

| 論文 | 内部 ID | プレーン名 | ページ |
|---|---|---|---|
| Phase 1 | `01a` | Spec Discovery (仕様収集) | [01a](./01a-spec-discovery.md) |
| Phase 2 | `01b` | Subgraph Extraction (サブグラフ抽出) | [01b](./01b-subgraph-extraction.md) |
| Phase 3 | `01e` | Property Generation (プロパティ生成) | [01e](./01e-property-generation.md) |
| Phase 4 | `02c` | Code Pre-resolution (コード位置事前解決) | [02c](./02c-code-resolution.md) |
| Phase 5 | `03` | Property Audit (Map / Prove / Stress-Test) | [03](./audit-map.md) |
| Phase 6 | `04` | Severity Review (3 ゲート FP フィルタ) | [04](./review.md) |

CLI とオーケストレータは常に内部 ID を使います (例: `speca run --target 04`)。

## 依存関係

```
01a (Spec Discovery)
  ↓
01b (Subgraph Extraction)
  ↓
01e (Property Generation)        ← BUG_BOUNTY_SCOPE.json 必須
  ↓
02c (Code Pre-resolution)        ← TARGET_INFO.json 必須
  ↓
03 (Audit Map: Map → Prove → Stress-Test)
  ↓
04 (Review: Dead Code → Trust Boundary → Scope)
```

前半 3 フェーズ (01a / 01b / 01e) は仕様とスコープルブリックのみに依存するため、複数の実装間でキャッシュ・再利用できます。後半 3 フェーズ (02c / 03 / 04) は対象コードベースに依存し、実装ごとに走らせます。

## 入出力一覧

| ID | 名前 | 入力 | 出力 |
|---|---|---|---|
| **01a** | [Spec Discovery](./01a-spec-discovery.md) | `SPEC_URLS` 環境変数 | `01a_STATE.json` |
| **01b** | [Subgraph Extraction](./01b-subgraph-extraction.md) | `01a_STATE.json` | Mermaid `.mmd` + `01b_PARTIAL_*.json` |
| **01e** | [Property Generation](./01e-property-generation.md) | サブグラフ + STRIDE/CWE Top 25 | `01e_PARTIAL_*.json` |
| **02c** | [Code Resolution](./02c-code-resolution.md) | プロパティ + ソース | `02c_PARTIAL_*.json` |
| **03** | [Audit Map](./audit-map.md) | プロパティ + コード | `03_PARTIAL_*.json` |
| **04** | [Review](./review.md) | Phase 03 findings | `04_PARTIAL_*.json` (6 種類の verdict) |

## データフローの規約

- **Partial ファイル**: `outputs/<phase_id>_PARTIAL_W{worker}B{batch}_{timestamp}.json`
- **キューファイル**: `outputs/<phase_id>_QUEUE_{worker}.json`
- **ログ**: `outputs/logs/{phase_id}_*.jsonl`

各フェーズは上流の partial ファイルを glob で消費し、resume により処理済み項目をスキップ、各バッチ完了直後に結果を即書き込みます。検証エラーで partial の保存をブロックすることはありません。

## ハーネス共通機能

オーケストレータは全フェーズで共通の 4 つの機能を提供します。詳細は [エージェント設計 — ハーネス](../agent-design/harness.md) にあります。

- **Circuit Breaker** — フェーズ内のすべてのワーカーで共有。連続失敗・総リトライ・空結果連発のいずれかで停止。
- **Cost Tracker** — フェーズごとの USD 予算上限。超過すると `BudgetExceeded` を投げてフェーズを即停止。
- **Resume Manager** — `*_PARTIAL_*.json` を走査し処理済み項目を判定、再実行はデフォルトでスキップ。
- **Log Watcher** — stream-json ログをリアルタイムに追従し、TUI ダッシュボードへイベント転送。

各フェーズへのモデル割り当てとプロンプト/スキルの選び分けは [プロンプトとスキル](../agent-design/prompts-and-skills.md) を参照してください。

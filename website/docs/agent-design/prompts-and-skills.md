---
sidebar_position: 3
---

# プロンプトとスキル

各フェーズの実装の中身: どのプロンプトが動かしているか、Claude Code skill をフォークするか、どのモデルが走るか、どのツールと MCP サーバーにアクセスできるか。

## 一覧

| フェーズ | プロンプトファイル | Skill フォーク? | モデル | ツール | MCP |
|---|---|---|---|---|---|
| **01a** Spec Discovery | `prompts/01a_crawl.md` + `.claude/skills/spec-discovery/` | **あり** | Opus | full | `fetch` |
| **01b** Subgraph Extraction | `prompts/01b_extract_worker.md` + `.claude/skills/subgraph-extractor/` | **あり** | Opus | full | — |
| **01e** Property Generation | `prompts/01e_prop_worker.md` | なし (inline) | Opus | full | — |
| **02c** Code Pre-resolution | `prompts/02c_codelocation_worker.md` | なし (inline) | Sonnet 4.5 | Read / Write / Grep / Glob | `tree_sitter` |
| **03** Audit Map | `prompts/03_auditmap_worker_inline.md` | なし (inline) | Sonnet 4.5 | Read / Write / Grep / Glob | — |
| **04** Review | `prompts/04_review_worker.md` | なし (inline) | Sonnet 4.5 | Read / Write / Grep / Glob | — |

手動フェーズ (オーケストレータ管理外) も同じディレクトリにあります: `05_poc.md` / `06_report.md` / `06b_audit_report.md`。

## Skill フォーク vs インラインプロンプト

`01a` と `01b` の 2 つは Claude Code **skill** (`.claude/skills/<name>/SKILL.md` に `context: fork`) として実装されています。残りの 4 つは **インラインプロンプト** — オーケストレータが `claude --prompt-path` に渡すワーカープロンプトファイルに分析手順をすべて埋め込んでいます。

この使い分けは意図的です:

- **Skill が向くのは、エージェントの仕事が探索的かつ横断的なとき** — Phase 01a は仕様リンクを大量のドキュメント横断で発見する。Phase 01b は仕様セクションを状態機械に分解する。Skill コンテキストをフォークすることで、長い探索作業をオーケストレータのメインスレッドから切り離します。
- **インラインが向くのは、エージェントの仕事が項目単位で閉じているとき** — Phase 01e は 1 つのサブグラフから型付きプロパティを生成。Phase 03 は 1 つのプロパティに対して Map → Prove → Stress-Test を走らせる。別コンテキストをフォークしても得るものは無く、間接層を 1 つ減らせます (コンテキストロードの往復が 1 回省ける)。

インライン化により項目あたり処理時間が約 15〜25% 短縮し、品質劣化はないことを計測しました。[RQ2 のモデル比較数値](../operations/benchmark-rq2a.md) はインライン構成で取得しています。

## フェーズ別ツール許可リスト

オーケストレータは `claude` 起動時に毎回ツール許可リストを渡します。これが効くのは 2 つの理由から: エージェントの行動範囲を制限する (混乱したエージェントが `git push` を呼ばないようにする) ことと、モデルが推論する行動空間を絞ることです。

**Phase 03 と 04** は `Read / Write / Grep / Glob` のみ — **MCP も Bash も WebFetch も無し**。プロパティが Phase 03 に到達した時点で関連ファイルは 02c で解決済みなので、エージェントの仕事はそれらを推論することだけです。シェルや外部 fetch を許すと「とりあえず周辺を覗いてみる」失敗モードが復活します — それを避けるための proof-attempt 設計が崩れます。

**Phase 02c** は唯一 MCP を多用するフェーズです — シンボル解決のための `tree_sitter`。Phase 01a も同じ理由 (探索) で `fetch` を使います。

## MCP サーバー — 役割と適用フェーズ

| サーバー | フェーズ | 役割 |
|---|---|---|
| `fetch` | 01a | HTTP GET + HTML→Markdown 変換。訪問済み URL キャッシュを尊重 |
| `tree_sitter` | 02c | `mcp__tree_sitter__get_symbols`, `run_query` など — 言語別に正確なシンボル解決を行う |

登録: `bash scripts/setup_mcp.sh` で両方セットアップ。`--verify` で疎通確認。

なぜこの仕事に MCP か? どちらも **エージェントが再発明すべきでないインフラ** だからです。仕様クロールには堅牢な URL 処理と HTML 変換が、シンボル解決には言語ごとの本物のパーサが必要です。MCP の境界が、エージェントプロンプトを「推論」に集中させ「配管」から外します。

## なぜモデルを分割 (前段 Opus、後段 Sonnet) するのか

前半 3 フェーズ (`01a` → `01b` → `01e`) は **knowledge structure** を構築します: 仕様コーパス、プログラムグラフ、型付きプロパティ集合。ここでのエラーは recall を直接縛ります — 監査ランのカバレッジはプロパティ品質で頭打ちになります。RQ2 の ablation で、後段モデルの強さではなくプロパティ生成がカバレッジの bottleneck だと示せたので、ここに **Opus** を割り当てています。

後半 3 フェーズ (`02c` → `03` → `04`) は実装に対してプロパティを **検証** します。RQ2 の精度 88.9% は **Sonnet 4.5** で達成しました — Claude 3.7 Sonnet と同等精度を Sonnet 4 より低コストで。経験的なスイートスポットで、その詳細は [モデル選定の設計ノート](../design-notes/model-benchmark-takeaways.md) で議論しています。

## プロンプトの読み方

プロンプトは短い (大半が 100〜300 行)。フェーズの挙動を端から端まで理解したいなら、プロンプトファイルが唯一の真実 (single source of truth) です — オーケストレータは入力を渡し出力を保存するだけ。プロンプト群が共有する不変条件:

- すべてのプロンプトは先頭の `<task>` ブロックで IO 契約を宣言します (キューファイル、コンテキストファイル、出力ファイル)。
- すべてのプロンプトは `<critical_requirements>` ブロックで譲れない条件を列挙します (例: "項目をスキップする場合でも出力ファイルは必ず書く")。
- Phase 03 と 04 は早期 exit やショートカット推論を明示的に禁止しています — 経験的にこの変更が幻覚 finding 抑制に最も効きました。

## システム拡張

新しいフェーズを足すには 3 つの artifact を書きます:

1. `scripts/orchestrator/config.py` への `PhaseConfig` エントリ。
2. ワーカープロンプト (インライン) または skill (`.claude/skills/<name>/SKILL.md`)。
3. 新出力型のための `scripts/orchestrator/schemas.py` の Pydantic スキーマ。

オーケストレータは新しい config を自動で拾います。CLI のフェーズ許可リスト (`KNOWN_PHASE_IDS`) は未知 ID に warning を出しつつ転送するため、フォークが `cli/` を変更せずに新フェーズを実験できます。

---
sidebar_position: 6
---

# プロジェクト構造

SPECA リポジトリのフォルダ構成と、各ディレクトリの役割を説明します。

## ディレクトリツリー

```
speca/
├── scripts/
│   ├── orchestrator/       # 非同期 Python オーケストレータ (メインロジック)
│   ├── run_phase.py        # パイプライン実行のエントリポイント
│   └── setup_mcp.sh        # MCP サーバ登録スクリプト
├── prompts/                # 各 Phase のワーカープロンプト
│   ├── 01a_spec_discovery/
│   ├── 01b_subgraph_extractor/
│   ├── 01e_property_generation/
│   └── ...
├── cli/                    # speca-cli (Node.js + Ink の TUI フロントエンド)
│   ├── src/
│   │   └── cli.tsx         # CLI エントリポイント
│   └── README.md
├── tests/                  # pytest テストスイート
├── outputs/                # パイプラインの入出力ファイル置き場 (gitignore 済み)
│   ├── TARGET_INFO.json    # 監査対象の情報
│   ├── BUG_BOUNTY_SCOPE.json
│   └── {phase}_PARTIAL_*.json
├── automation/             # GitHub Actions ワークフロー定義
├── website/               # Docusaurus ドキュメントサイト (このサイト)
├── .claude/
│   └── skills/             # Claude Code スキル定義 (01a / 01b)
├── CLAUDE.md               # アーキテクチャ・設計判断・コマンドリファレンス
└── README.md               # プロジェクト概要と arXiv 論文リンク
```

## 主要ディレクトリの役割

**`scripts/orchestrator/`**  
パイプラインの中核です。`config.py` で各 Phase の設定を定義し、`base.py` がバッチ生成・並列実行・再開 (resume) を管理します。`runner.py` が Claude Code CLI を呼び出し、`watchdog.py` がコストを監視します。

**`prompts/`**  
各 Phase の Claude へのプロンプトが入っています。Phase 01a と 01b はスキル (`SKILL.md`) として定義されており、残りの Phase はワーカープロンプトとして直接インライン化されています。プロンプトを読むと、各 Phase が何をどう分析しているかが分かります。

**`cli/`**  
`speca init` / `speca run` / `speca browse` などのコマンドを提供する TUI フロントエンドです。エントリポイントは `cli/src/cli.tsx`。Node.js + Ink で実装されています。

**`tests/`**  
pytest で動く自動テストです。CI の pre-flight チェックとして全 Phase の実行前に走ります。`uv run python3 -m pytest tests/ -v --tb=short` で実行できます。

**`outputs/`**  
パイプラインの入力ファイル (`TARGET_INFO.json`, `BUG_BOUNTY_SCOPE.json`) と、各 Phase の出力 (`{phase}_PARTIAL_*.json`) が置かれます。`.gitignore` に含まれているため、監査結果がリポジトリに混入しません。

**`automation/`**  
GitHub Actions のワークフロー定義です。Phase ごとに CI ジョブが分かれており、各 Phase を独立して再実行できます。

## コードを読み始めるなら

パイプライン全体の流れを把握したい場合は `scripts/run_phase.py` から読むのがよいです。引数解析 → `PhaseConfig` の選択 → `BaseOrchestrator.run()` という流れで動いています。

CLI の動作を調べたい場合は `cli/src/cli.tsx` がエントリポイントです。

各 Phase の具体的な分析ロジックは対応する `prompts/` 以下のプロンプトに書かれています。Phase 01e・02c・03・04 はプロンプトにすべてのロジックがインライン化されています。

設計判断の **背景** — ハーネスの不変条件、プロンプト vs スキル選別、自明でないコンテキスト流通の判断 — は [エージェント設計](./agent-design/overview.md) のセクションを参照してください。設計の背景や判断の理由は [CLAUDE.md](https://github.com/NyxFoundation/speca/blob/main/CLAUDE.md) にもまとめてあります。

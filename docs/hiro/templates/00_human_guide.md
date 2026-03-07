# Sherlock Bug Bounty 量産監査ガイド (人間用)

## この文書は何か

Sherlock Bug Bounty コンテストに対して、AI エージェントを大量並列起動して脆弱性を発見するワークフローの人間向け説明。各ステップで「何をするか」「なぜやるか」「どのテンプレートを使うか」を説明する。

---

## ブランチ戦略

```
main (master)
  SPECA のソースコードのみ。レポートは置かない。
      |
      +-- hiro/<CONTEST_BRANCH> (作業ベースブランチ)
            レポートを溜める場所。各 agent ブランチの PR マージ先。
            |
            +-- <CONTEST_BRANCH>-agent-1  → PR → マージ
            +-- <CONTEST_BRANCH>-agent-2  → PR → マージ
            +-- <CONTEST_BRANCH>-agent-N  → PR → マージ
            |
            (マージ後)
            +-- テンプレート 09 で重複チェック → 統合 or 削除
```

- **main**: コードだけ。監査の成果物は入れない
- **作業ブランチ**: コンテストごとに 1 本。全レポートが集約される場所
- **agent ブランチ**: エージェントが作業して PR → 作業ブランチにマージ → 自動削除
- **重複チェック**: 全 agent マージ後にテンプレート 09 を実行し、重複レポートを統合/削除

---

## テンプレート変数

各テンプレート (.template.md / .template.sh) で使用する変数:

| 変数 | 説明 | 例 |
|------|------|-----|
| `{{PROTOCOL_NAME}}` | プロトコル名 | Current Finance |
| `{{CONTEST_NUMBER}}` | Sherlock コンテスト番号 | 1256 |
| `{{TARGET_PATH}}` | ターゲットコードのパス | /Users/hiro/Documents/xxx/sui-move-contract |
| `{{LANGUAGE}}` | プログラミング言語 | Sui Move |
| `{{CHAIN}}` | ブロックチェーン名 | Sui |
| `{{CONTRACT_DIR}}` | メインコントラクトディレクトリ | contracts/protocol/sources |
| `{{MODULE_LIST}}` | 主要モジュール一覧 | market, obligation, reserve... |
| `{{BASE_BRANCH}}` | 作業ベースブランチ名 | elegant-wiles |
| `{{BRANCH_PREFIX}}` | agent ブランチの prefix | elegant-wiles |
| `{{LANGUAGE_SPECIFIC_CONCERNS}}` | 言語固有の注意点 | Move: phantom type, hot-potato... |

---

## 全体フロー

```
Phase 0: 準備 (人間)
  ターゲット情報収集、コードクローン、作業ブランチ作成
      |
Phase 1: 初回並列監査 (AI x N)
  テンプレート 01 を N 個のセッションに投入
  各 agent → PR → 作業ブランチにマージ
      |
Phase 1.5: 重複チェック (AI x 1)
  テンプレート 09 で重複レポート統合/削除
      |
Phase 2: オーケストレーター監査 (AI x 1)
  テンプレート 02 → 内部で 12 並列エージェント → PR → マージ
      |
Phase 3: Codex クロスバリデーション (スクリプト)
  テンプレート 08 のスクリプト直接実行
      |
Phase 4: 深堀り・最終洗い出し (AI x 1)
  追加テンプレートで深堀り → PR → マージ
      |
Phase 4.5: 最終重複チェック (AI x 1)
  テンプレート 09 で最終整理
```

---

## Phase 0: 準備 (人間が手動で行う)

### 0-1. コンテスト情報を集める

Sherlock のコンテストページから:
- コンテスト番号 (例: #1256)
- プロトコル名 (例: Current Finance)
- ターゲットリポジトリ URL
- コンテスト期間、賞金プール
- スコープ (対象ファイル/コントラクト)
- 言語 (Solidity / Move / Rust / etc.)

### 0-2. ターゲットコードをクローン

```bash
cd /Users/hiro/Documents
git clone <TARGET_REPO_URL>
```

### 0-3. ベースブランチを作成

```bash
cd /Users/hiro/Documents/security-agent
git checkout -b hiro/<CONTEST_BRANCH> main
git push origin hiro/<CONTEST_BRANCH>
```

### 0-4. テンプレートをカスタマイズ

`.template.md` / `.template.sh` ファイルの変数を置換して、コンテスト固有の `.md` / `.sh` を作成:

```bash
# 例: テンプレートから固有ファイルを生成
sed -e 's|{{PROTOCOL_NAME}}|Current Finance|g' \
    -e 's|{{CONTEST_NUMBER}}|1256|g' \
    -e 's|{{TARGET_PATH}}|/Users/hiro/Documents/xxx/sui-move-contract|g' \
    -e 's|{{LANGUAGE}}|Sui Move|g' \
    -e 's|{{BASE_BRANCH}}|elegant-wiles|g' \
    -e 's|{{BRANCH_PREFIX}}|elegant-wiles|g' \
    docs/hiro/templates/01_single_agent_audit.template.md \
    > docs/hiro/templates/01_single_agent_audit.md
```

---

## Phase 1: 量産セッション起動

### 方法 A: happy コマンド (推奨、最も手軽)

ターミナルを N 個開いて、全部同じコマンドを貼るだけ:

```bash
cd /Users/hiro/Documents/security-agent
happy --yolo -p "docs/hiro/templates/01_single_agent_audit.md を読み込み、リモートブランチを確認して空いている最も若い番号を自身のエージェント番号として監査を実行して。既存レポートとの重複は避けること。"
```

### 方法 B: claude コマンド

```bash
cd /Users/hiro/Documents/security-agent
claude -p "docs/hiro/templates/01_single_agent_audit.md を読み込み実行してください。"
```

### 方法 C: スクリプト一括起動

```bash
bash docs/hiro/templates/07_mass_launch.sh 10
```

### 何が起きるか

1. 各セッションが `git branch -r` を確認して空き番号を取得
2. `hiro/<BRANCH_PREFIX>-agent-N` ブランチを作成
3. ターゲットコードを読んで脆弱性を発見
4. `outputs/reports/report_NNN_*.md` にレポートを作成
5. PR を作成して即座にマージ
6. ブランチ削除

---

## Phase 2: オーケストレーター (1 セッションで 12 並列)

テンプレート 02 を使う。1 つの Claude Code セッション内で 12 個の Agent ツール呼び出しを行い、攻撃面ごとに並列分析する。

```bash
claude -p "docs/hiro/templates/02_orchestrator_12_agents.md を読み込み実行してください。"
```

Phase 1 とは別のアプローチ:
- Phase 1: 各セッションが独立に全コードを見る → 同じバグの独立確認が得られる
- Phase 2: 1 セッションが攻撃面を分割して効率的に探索 → 網羅性が高い

---

## Phase 3: Codex クロスバリデーション

Claude とは異なる AI (OpenAI Codex) で同じ分析を行い、発見を比較する。

```bash
# スクリプト直接実行
bash docs/hiro/templates/08_codex_launch.sh
```

---

## ディレクトリ構成

```
docs/hiro/templates/
  00_human_guide.md                       ← この文書 (人間用ガイド)
  01_single_agent_audit.template.md       ← AI用: 単体監査プロンプト (テンプレート)
  02_orchestrator_12_agents.template.md   ← AI用: 12 並列オーケストレーター (テンプレート)
  07_mass_launch.sh                       ← スクリプト: N 個のセッション一括起動
  08_codex_launch.template.sh             ← スクリプト: 12 Codex エージェント起動 (テンプレート)
  09_dedup_reports.template.md            ← AI用: マージ後の重複チェック・統合 (テンプレート)
```

---

## 注意事項

- happy / claude は security-agent ディレクトリで起動すること
- Codex は `--skip-git-repo-check` が必要
- レポートは必ず `outputs/reports/` に配置
- エージェント間の番号衝突は PR マージ時に自然解消 (squash merge)
- `.template.md` の `{{変数}}` は使用前に sed 等で置換すること

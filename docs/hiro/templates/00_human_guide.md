# SPECA 量産監査ガイド (人間用)

## この文書は何か

Sherlock Bug Bounty コンテストに対して、SPECA パイプライン (spec-to-property agentic auditing) を N 並列で実行し、脆弱性を効率的に発見するワークフローの人間向け説明。

SPECA の正式パイプライン (01a→01b→01e→02c→03→04) を使い、定義済みスキーマで体系的に監査する。アドホックな「コード読んでバグ探せ」方式ではない。

---

## アーキテクチャ

```
01a (Spec Discovery) → 01b (Subgraph) → 01e (Property Gen)
                                              |
                    +-------------------------+
                    |         共有 (1回実行)
                    |
          +---------+---------+---------+
          |         |         |         |
        inst_01   inst_02   inst_03   inst_04    ← N 並列
          |         |         |         |
        02c       02c       02c       02c        ← Code Pre-resolution
          |         |         |         |
        03        03        03        03         ← Audit Map
          |         |         |         |
        04        04        04        04         ← Review (FP Filter)
          |         |         |         |
          +----+----+----+----+
               |
         結果統合 + 重複チェック
```

- **01a-01e**: 仕様発見→サブグラフ→プロパティ生成。1回だけ実行して全インスタンスで共有
- **02c-04**: コード解析→監査→レビュー。N 並列で独立実行 (各インスタンスが固有の output-dir)
- **統合**: 全インスタンスの PARTIAL 結果を統合し、重複を排除

---

## ブランチ戦略

```
main (master)
  SPECA のソースコードのみ。監査成果物は入れない。
      |
      +-- hiro/<CONTEST_BRANCH> (作業ベースブランチ)
            監査結果を溜める場所。
            |
            +-- <CONTEST_BRANCH>-speca-shared    → 01a-01e 共有結果
            +-- <CONTEST_BRANCH>-speca-inst-01   → inst_01 の 02c-04 結果
            +-- <CONTEST_BRANCH>-speca-inst-02   → inst_02 の 02c-04 結果
            +-- <CONTEST_BRANCH>-speca-inst-N    → inst_N の 02c-04 結果
            |
            (マージ後)
            +-- テンプレート 09 で重複チェック → 統合
```

---

## テンプレート変数

各テンプレート (.template.md / .template.sh) で使用する変数:

| 変数 | 説明 | 例 |
|------|------|-----|
| `{{PROTOCOL_NAME}}` | プロトコル名 | Current Finance |
| `{{CONTEST_NUMBER}}` | コンテスト番号 | 1256 |
| `{{TARGET_REPO}}` | ターゲットリポジトリ URL | https://github.com/xxx/yyy |
| `{{TARGET_PATH}}` | ローカルのターゲットコードパス | /Users/hiro/Documents/xxx |
| `{{LANGUAGE}}` | プログラミング言語 | Sui Move |
| `{{CHAIN}}` | ブロックチェーン名 | Sui |
| `{{SPEC_URLS}}` | 仕様書 URL (カンマ区切り) | https://docs.example.com/... |
| `{{BASE_BRANCH}}` | 作業ベースブランチ名 | elegant-wiles |
| `{{NUM_INSTANCES}}` | 並列インスタンス数 | 4 |

---

## 全体フロー

```
Phase 0: 準備 (人間)
  ターゲット情報収集、コードクローン、作業ブランチ作成
      |
Phase 1: 共有フェーズ実行 (1回)
  run_phase.py --phase 01a 01b 01e
  → outputs/ に共有データ生成
      |
Phase 2: BUG_BOUNTY_SCOPE + TARGET_INFO 作成 (人間/AI)
  対象スコープ定義、ターゲット情報ファイル作成
      |
Phase 3: 並列インスタンス準備
  テンプレート 07 でインスタンスディレクトリ作成 + シンボリックリンク
      |
Phase 4: N 並列 SPECA 実行
  テンプレート 01 or 07 で 02c→03→04 を N 並列起動
      |
Phase 5: 結果統合 + 重複チェック (AI x 1)
  テンプレート 09 で全インスタンスの結果を統合・整理
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
- 仕様書 URL

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

```bash
sed -e 's|{{PROTOCOL_NAME}}|Current Finance|g' \
    -e 's|{{CONTEST_NUMBER}}|1256|g' \
    -e 's|{{TARGET_REPO}}|https://github.com/xxx/yyy|g' \
    -e 's|{{TARGET_PATH}}|/Users/hiro/Documents/xxx|g' \
    -e 's|{{LANGUAGE}}|Sui Move|g' \
    -e 's|{{CHAIN}}|Sui|g' \
    -e 's|{{SPEC_URLS}}|https://docs.example.com/|g' \
    -e 's|{{BASE_BRANCH}}|elegant-wiles|g' \
    -e 's|{{NUM_INSTANCES}}|4|g' \
    docs/hiro/templates/01_speca_pipeline.template.md \
    > docs/hiro/templates/01_speca_pipeline.md
```

---

## Phase 1: 共有フェーズ実行 (01a→01b→01e)

仕様発見からプロパティ生成まで。1回だけ実行して全インスタンスで共有する。

```bash
cd /Users/hiro/Documents/security-agent

# 環境変数を設定
export SPEC_URLS="<仕様書URL>"
export KEYWORDS="<キーワード>"

# 共有フェーズ実行
uv run python3 scripts/run_phase.py --phase 01a 01b 01e --workers 4
```

### 出力

- `outputs/01a_STATE.json` — 発見した仕様一覧
- `outputs/01b_PARTIAL_*.json` — サブグラフ
- `outputs/graphs/*.mmd` — Mermaid ダイアグラム
- `outputs/01e_PARTIAL_*.json` — セキュリティプロパティ

---

## Phase 2: スコープ定義

### BUG_BOUNTY_SCOPE.json

Phase 01e が必要とするスコープ定義ファイル。共有フェーズ実行前に作成する。

```bash
cat > outputs/BUG_BOUNTY_SCOPE.json << 'EOF'
{
  "protocol": "<PROTOCOL_NAME>",
  "scope": ["<対象ファイルパターン>"],
  "out_of_scope": ["<対象外ファイルパターン>"]
}
EOF
```

### TARGET_INFO.json

Phase 02c が必要とするターゲット情報。

```bash
cat > outputs/TARGET_INFO.json << 'EOF'
{
  "repository": "<TARGET_REPO_URL>",
  "commit": "<COMMIT_HASH>",
  "local_path": "<TARGET_PATH>",
  "language": "<LANGUAGE>"
}
EOF
```

---

## Phase 3: 並列インスタンス準備

```bash
NUM_INSTANCES=4

# インスタンスディレクトリ作成 + 共有データのシンボリックリンク
for i in $(seq -w 1 $NUM_INSTANCES); do
  dir="outputs/inst_$i"
  mkdir -p "$dir"

  # 共有フェーズ出力をリンク
  ln -sf ../01a_STATE.json "$dir/"
  for f in ../01b_PARTIAL_*.json; do ln -sf "$f" "$dir/" 2>/dev/null; done
  for f in ../01e_PARTIAL_*.json; do ln -sf "$f" "$dir/" 2>/dev/null; done
  ln -sf ../graphs "$dir/"
  ln -sf ../BUG_BOUNTY_SCOPE.json "$dir/"
  ln -sf ../01b_SUBGRAPH_INDEX.json "$dir/" 2>/dev/null

  # TARGET_INFO はコピー (インスタンス固有の可能性)
  cp outputs/TARGET_INFO.json "$dir/"
done
```

---

## Phase 4: N 並列 SPECA 実行 (02c→03→04)

### 方法 A: 直接コマンド (最も手軽)

```bash
cd /Users/hiro/Documents/security-agent

# 各インスタンスを並列起動
SPECA_OUTPUT_DIR=outputs/inst_01 uv run python3 scripts/run_phase.py --phase 02c 03 04 --workers 2 &
SPECA_OUTPUT_DIR=outputs/inst_02 uv run python3 scripts/run_phase.py --phase 02c 03 04 --workers 2 &
SPECA_OUTPUT_DIR=outputs/inst_03 uv run python3 scripts/run_phase.py --phase 02c 03 04 --workers 2 &
SPECA_OUTPUT_DIR=outputs/inst_04 uv run python3 scripts/run_phase.py --phase 02c 03 04 --workers 2 &
wait
```

### 方法 B: スクリプト一括起動

```bash
bash docs/hiro/templates/07_mass_launch.sh 4
```

### 方法 C: AI に実行させる

```bash
# AI が docs/hiro/templates/01_speca_pipeline.md を読んで自動実行
claude -p "docs/hiro/templates/01_speca_pipeline.md を読み込み実行してください。"
```

---

## Phase 5: 結果統合 + 重複チェック

全インスタンスの結果をマージし、重複を排除する。

```bash
claude -p "docs/hiro/templates/09_dedup_results.md を読み込み実行してください。"
```

---

## ディレクトリ構成

```
docs/hiro/templates/
  00_human_guide.md                      -- この文書 (人間用ガイド)
  01_speca_pipeline.template.md          -- AI用: SPECA パイプライン実行プロンプト
  02_orchestrator_n_instances.template.md -- AI用: N 並列 SPECA オーケストレーター
  07_mass_launch.sh                      -- スクリプト: N インスタンス一括起動
  08_codex_launch.template.sh            -- スクリプト: Codex クロスバリデーション
  09_dedup_results.template.md           -- AI用: 結果統合 + 重複チェック
```

---

## 注意事項

- `--output-dir` と `SPECA_OUTPUT_DIR` は同じ効果。CLI 引数が環境変数より優先
- 共有フェーズ (01a-01e) は必ず先に完了させてからインスタンスを起動
- シンボリックリンクにより共有データの重複コピーを回避
- 各インスタンスの出力は完全に分離 (02c/03/04 の PARTIAL ファイルが独立)
- SPECA のスキーマ (Pydantic) により出力フォーマットは一貫
- 既存の GitHub Actions ワークフロー (grandchildrice 作成) は一切変更なし

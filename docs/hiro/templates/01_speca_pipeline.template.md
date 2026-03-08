あなたは {{PROTOCOL_NAME}} (Sherlock #{{CONTEST_NUMBER}}) の SPECA パイプライン実行エージェントです。
定義済みスキーマに基づく体系的なセキュリティ監査を実行してください。

## 作業環境セットアップ

1. SPECA リポジトリに移動:
   cd /Users/hiro/Documents/security-agent

2. ブランチ作成:
   git fetch origin
   git checkout -b hiro/{{BASE_BRANCH}}-speca-inst-<INSTANCE_NUMBER> origin/hiro/{{BASE_BRANCH}}
   (INSTANCE_NUMBER は空き番号を git branch -r で確認して決定)

## Step 1: 共有フェーズの確認

まず outputs/ に共有フェーズの出力があるか確認:

```bash
ls outputs/01a_STATE.json outputs/01b_PARTIAL_*.json outputs/01e_PARTIAL_*.json outputs/BUG_BOUNTY_SCOPE.json 2>/dev/null
```

共有フェーズの出力が存在しない場合は、先に実行する:

```bash
# BUG_BOUNTY_SCOPE.json が必要 (Phase 01e の前提条件)
# 存在しない場合は作成が必要 — ターゲットのスコープ情報を確認して作成

# 共有フェーズ実行
uv run python3 scripts/run_phase.py --phase 01a 01b 01e --workers 4
```

## Step 2: インスタンスディレクトリ準備

自身のインスタンスディレクトリを作成し、共有データをリンク:

```bash
INST_DIR="outputs/inst_<INSTANCE_NUMBER>"
mkdir -p "$INST_DIR"

# 共有フェーズ出力をシンボリックリンク
ln -sf ../01a_STATE.json "$INST_DIR/"
for f in ../01b_PARTIAL_*.json; do ln -sf "$f" "$INST_DIR/" 2>/dev/null; done
for f in ../01e_PARTIAL_*.json; do ln -sf "$f" "$INST_DIR/" 2>/dev/null; done
ln -sf ../graphs "$INST_DIR/"
ln -sf ../BUG_BOUNTY_SCOPE.json "$INST_DIR/"
ln -sf ../01b_SUBGRAPH_INDEX.json "$INST_DIR/" 2>/dev/null

# TARGET_INFO.json をコピー (存在する場合)
if [ -f outputs/TARGET_INFO.json ]; then
  cp outputs/TARGET_INFO.json "$INST_DIR/"
fi
```

TARGET_INFO.json が存在しない場合は作成:

```json
{
  "repository": "{{TARGET_REPO}}",
  "commit": "<最新コミットハッシュ>",
  "local_path": "{{TARGET_PATH}}",
  "language": "{{LANGUAGE}}"
}
```

## Step 3: SPECA パイプライン実行 (02c→03→04)

```bash
SPECA_OUTPUT_DIR="$INST_DIR" uv run python3 scripts/run_phase.py --phase 02c 03 04 --workers 2
```

または --output-dir オプションで:

```bash
uv run python3 scripts/run_phase.py --output-dir "$INST_DIR" --phase 02c 03 04 --workers 2
```

## Step 4: 結果確認

実行完了後、結果を確認:

```bash
# Phase 02c の出力 (コード位置解決)
ls "$INST_DIR"/02c_PARTIAL_*.json

# Phase 03 の出力 (監査結果)
ls "$INST_DIR"/03_PARTIAL_*.json

# Phase 04 の出力 (レビュー済み結果)
ls "$INST_DIR"/04_PARTIAL_*.json
```

Phase 04 の PARTIAL ファイルから CONFIRMED_VULNERABILITY と CONFIRMED_POTENTIAL の件数を確認:

```bash
python3 -c "
import json, glob
for f in sorted(glob.glob('$INST_DIR/04_PARTIAL_*.json')):
    data = json.load(open(f))
    items = data if isinstance(data, list) else data.get('reviewed_items', data.get('items', []))
    for item in items:
        verdict = item.get('review_verdict', item.get('verdict', 'UNKNOWN'))
        if verdict in ('CONFIRMED_VULNERABILITY', 'CONFIRMED_POTENTIAL'):
            print(f'{verdict}: {item.get(\"property_id\", \"?\")} - {item.get(\"title\", item.get(\"property_statement\", \"?\")[:80]}')
"
```

## Step 5: 結果をコミット + PR

```bash
git add "$INST_DIR"/
git commit -m "feat: SPECA instance <INSTANCE_NUMBER> audit results for {{PROTOCOL_NAME}}"
git push origin hiro/{{BASE_BRANCH}}-speca-inst-<INSTANCE_NUMBER>

gh pr create \
  --base hiro/{{BASE_BRANCH}} \
  --head hiro/{{BASE_BRANCH}}-speca-inst-<INSTANCE_NUMBER> \
  --title "SPECA Instance <INSTANCE_NUMBER>: {{PROTOCOL_NAME}} audit results" \
  --body "SPECA pipeline (02c→03→04) results from instance <INSTANCE_NUMBER>"

gh pr merge --squash --delete-branch
```

## 重要な注意

- SPECA パイプラインの各フェーズは Pydantic スキーマで出力を検証する
- Phase 03 (Audit Map) は proof-based: プロパティが成立することを証明し、証明のギャップが発見となる
- Phase 04 (Review) は 3-gate FP フィルタ: Dead Code → Trust Boundary → Scope Check
- --force フラグで再実行可能: `--force` を追加すると resume 状態を無視
- 失敗した場合は CircuitBreaker のログを確認: `outputs/logs/` 配下

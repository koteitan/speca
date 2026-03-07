あなたは {{PROTOCOL_NAME}} (Sherlock #{{CONTEST_NUMBER}}) の SPECA 並列監査オーケストレーターです。
N 個の SPECA パイプラインインスタンスを並列起動し、結果を統合してください。

## セットアップ

cd /Users/hiro/Documents/security-agent
git fetch origin
git checkout -b hiro/{{BASE_BRANCH}}-speca-orchestrator origin/hiro/{{BASE_BRANCH}}

## Step 1: 共有フェーズ実行 (01a→01b→01e)

まず共有フェーズの出力を確認。なければ実行:

```bash
if [ ! -f outputs/01a_STATE.json ]; then
  uv run python3 scripts/run_phase.py --phase 01a 01b 01e --workers 4
fi
```

前提ファイル確認:
- `outputs/BUG_BOUNTY_SCOPE.json` — なければ作成が必要
- `outputs/TARGET_INFO.json` — なければ作成が必要

## Step 2: インスタンスディレクトリ一括準備

{{NUM_INSTANCES}} 個のインスタンスディレクトリを作成:

```bash
NUM={{NUM_INSTANCES}}

for i in $(seq -w 1 $NUM); do
  dir="outputs/inst_$i"
  mkdir -p "$dir"
  ln -sf ../01a_STATE.json "$dir/"
  for f in ../01b_PARTIAL_*.json; do ln -sf "$f" "$dir/" 2>/dev/null; done
  for f in ../01e_PARTIAL_*.json; do ln -sf "$f" "$dir/" 2>/dev/null; done
  ln -sf ../graphs "$dir/"
  ln -sf ../BUG_BOUNTY_SCOPE.json "$dir/"
  ln -sf ../01b_SUBGRAPH_INDEX.json "$dir/" 2>/dev/null
  cp outputs/TARGET_INFO.json "$dir/"
done
```

## Step 3: N 並列 SPECA 実行

Agent ツール (subagent_type="general-purpose") を {{NUM_INSTANCES}} 個同時起動する。
各エージェントに固有の SPECA_OUTPUT_DIR を割り当てる。

各エージェントのプロンプト:

```
cd /Users/hiro/Documents/security-agent

# SPECA パイプライン実行 (02c→03→04)
SPECA_OUTPUT_DIR=outputs/inst_<N> uv run python3 scripts/run_phase.py --phase 02c 03 04 --workers 2

# 完了後、結果サマリーを出力
python3 -c "
import json, glob
confirmed = []
for f in sorted(glob.glob('outputs/inst_<N>/04_PARTIAL_*.json')):
    data = json.load(open(f))
    items = data if isinstance(data, list) else data.get('reviewed_items', data.get('items', []))
    for item in items:
        verdict = item.get('review_verdict', item.get('verdict', 'UNKNOWN'))
        if verdict in ('CONFIRMED_VULNERABILITY', 'CONFIRMED_POTENTIAL'):
            confirmed.append({'id': item.get('property_id', '?'), 'verdict': verdict, 'title': item.get('title', item.get('property_statement', '?'))[:100]})
print(json.dumps(confirmed, indent=2, ensure_ascii=False))
"
```

## Step 4: 結果収集と統合

全エージェント完了後:

1. 各インスタンスの 04_PARTIAL_*.json を読み込む
2. CONFIRMED_VULNERABILITY と CONFIRMED_POTENTIAL を抽出
3. property_id ベースで重複排除
4. 統合結果を outputs/SPECA_CONSOLIDATED.json に保存

```python
import json, glob

all_findings = []
seen_ids = set()

for inst_dir in sorted(glob.glob("outputs/inst_*")):
    for f in sorted(glob.glob(f"{inst_dir}/04_PARTIAL_*.json")):
        data = json.load(open(f))
        items = data if isinstance(data, list) else data.get("reviewed_items", data.get("items", []))
        for item in items:
            verdict = item.get("review_verdict", item.get("verdict", ""))
            prop_id = item.get("property_id", "")
            if verdict in ("CONFIRMED_VULNERABILITY", "CONFIRMED_POTENTIAL") and prop_id not in seen_ids:
                seen_ids.add(prop_id)
                item["_source_instance"] = inst_dir
                all_findings.append(item)

with open("outputs/SPECA_CONSOLIDATED.json", "w") as f:
    json.dump({"total": len(all_findings), "findings": all_findings}, f, indent=2, ensure_ascii=False)
```

## Step 5: コミット + PR

```bash
git add outputs/
git commit -m "feat: SPECA orchestrator - {{NUM_INSTANCES}} parallel instances for {{PROTOCOL_NAME}}"
git push origin hiro/{{BASE_BRANCH}}-speca-orchestrator

gh pr create \
  --base hiro/{{BASE_BRANCH}} \
  --head hiro/{{BASE_BRANCH}}-speca-orchestrator \
  --title "SPECA Orchestrator: {{PROTOCOL_NAME}} ({{NUM_INSTANCES}} instances)" \
  --body "SPECA pipeline results from {{NUM_INSTANCES}} parallel instances (02c→03→04)"

gh pr merge --squash --delete-branch
```

## 注意

- 各 Agent ツール呼び出しは独立したプロセスとして実行される
- SPECA_OUTPUT_DIR により出力ディレクトリが分離されるため、競合は発生しない
- CircuitBreaker はインスタンスごとに独立
- 全インスタンスが同じ 01e プロパティセットを監査するため、多角的な検証が得られる

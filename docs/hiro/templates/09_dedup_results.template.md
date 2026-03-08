あなたは {{PROTOCOL_NAME}} (Sherlock #{{CONTEST_NUMBER}}) の SPECA 監査結果の統合・重複チェック担当です。
N 並列インスタンスの結果を統合し、重複を排除してください。

## セットアップ

cd /Users/hiro/Documents/security-agent
git fetch origin
git checkout hiro/{{BASE_BRANCH}}
git pull origin hiro/{{BASE_BRANCH}}

## Step 1: 全インスタンスの結果を収集

各インスタンスの Phase 04 結果 (レビュー済み) を読み込む:

```bash
ls outputs/inst_*/04_PARTIAL_*.json
```

## Step 2: CONFIRMED 発見を抽出・統合

以下のスクリプトで全インスタンスから CONFIRMED 発見を抽出:

```python
import json, glob

all_findings = {}  # property_id → best finding

for f in sorted(glob.glob("outputs/inst_*/04_PARTIAL_*.json")):
    data = json.load(open(f))
    items = data if isinstance(data, list) else data.get("reviewed_items", data.get("items", []))
    for item in items:
        verdict = item.get("review_verdict", item.get("verdict", ""))
        if verdict not in ("CONFIRMED_VULNERABILITY", "CONFIRMED_POTENTIAL"):
            continue

        prop_id = item.get("property_id", "")
        if not prop_id:
            continue

        if prop_id in all_findings:
            # 同じ property_id が複数インスタンスで CONFIRMED → 独立確認
            existing = all_findings[prop_id]
            existing.setdefault("_confirmed_by_instances", [])
            existing["_confirmed_by_instances"].append(f)
        else:
            item["_source_file"] = f
            item["_confirmed_by_instances"] = [f]
            all_findings[prop_id] = item

print(f"Total unique CONFIRMED findings: {len(all_findings)}")
```

## Step 3: 重複判定

同じ property_id の発見は自動的に統合される (SPECA のスキーマが一意の property_id を保証)。

追加の重複判定基準:
- 異なる property_id だが同じ root cause (同じファイル:行番号) を指す場合
- 異なる property_id だが同じ攻撃シナリオを説明している場合

重複が見つかった場合:
1. より詳細な方 (proof_evidence が充実、code_scope が広い) を残す
2. 残す方に独立確認の情報を追記
3. 重複した方の property_id をログに記録

## Step 4: 結果を Sherlock 形式レポートに変換

CONFIRMED_VULNERABILITY と CONFIRMED_POTENTIAL を Sherlock 形式のレポートに変換:

```
outputs/reports/report_NNN_<snake_case_title>.md
```

レポート形式:

```markdown
# <タイトル (英語)>

## Summary
<property_statement の要約>

## Vulnerability Detail
<proof_evidence からの技術的詳細。根本原因のファイル名:行番号を明記>

## Impact
<影響の説明 + severity>

## Code Snippet
<code_scope からのファイル名:行番号リスト>

## Tool used
SPECA Automated Pipeline ({{NUM_INSTANCES}} parallel instances)
Independently confirmed by N instances.

## Recommendation
<修正案>
```

## Step 5: 統合レポート作成

`outputs/SPECA_DEDUP_LOG.md` に統合ログを記録:

```markdown
# SPECA 結果統合ログ

## 実行情報
- プロトコル: {{PROTOCOL_NAME}}
- インスタンス数: <N>
- 実行日: <日時>

## 統計
| 項目 | 件数 |
|------|------|
| 全 CONFIRMED 発見 (重複含む) | <数> |
| 重複排除後 | <数> |
| CONFIRMED_VULNERABILITY | <数> |
| CONFIRMED_POTENTIAL | <数> |
| 複数インスタンスで独立確認 | <数> |

## 重複排除ログ
| 残した property_id | 排除した property_id | 理由 |
|-------------------|---------------------|------|

## 最終レポート一覧
| ファイル | Severity | Title |
|---------|----------|-------|
```

## Step 6: コミット

```bash
git add outputs/reports/ outputs/SPECA_CONSOLIDATED.json outputs/SPECA_DEDUP_LOG.md
git commit -m "feat: consolidated SPECA results for {{PROTOCOL_NAME}} - N findings from M instances"
git push origin hiro/{{BASE_BRANCH}}
```

## 注意

- property_id が同一 = 同じプロパティに対する監査結果。自動統合される
- 複数インスタンスで独立に CONFIRMED = 信頼度が高い
- DISPUTED_FP は除外 (Phase 04 の 3-gate フィルタで既に除去済み)
- NEEDS_MANUAL_REVIEW は手動確認が必要なため、別途リストアップ

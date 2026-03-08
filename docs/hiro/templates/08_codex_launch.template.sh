#!/bin/bash
# ============================================
# Codex クロスバリデーション起動スクリプト (テンプレート)
# ============================================
# SPECA の結果を Codex (別 AI) で独立検証するためのスクリプト。
# SPECA パイプラインの補完として使用する。
#
# 使い方:
#   1. 変数を編集
#   2. bash docs/hiro/templates/08_codex_launch.sh
#
# 前提条件:
#   - SPECA パイプラインが完了済み (04_PARTIAL_*.json が存在)
#   - Codex CLI がインストール済み

set -e

# === ここを編集 ===
TARGET="${TARGET:-{{TARGET_PATH}}}"
LANGUAGE="${LANGUAGE:-{{LANGUAGE}}}"
CONTRACT_DIR="${CONTRACT_DIR:-contracts/protocol/sources}"
SPECA_RESULTS_DIR="${SPECA_RESULTS_DIR:-outputs}"
# ==================

OUTPUT_DIR="outputs/codex_validation"
mkdir -p "$OUTPUT_DIR"

echo "=== Codex クロスバリデーション ==="
echo "ターゲット: $TARGET"
echo "言語: $LANGUAGE"
echo "SPECA 結果: $SPECA_RESULTS_DIR"
echo "出力先: $OUTPUT_DIR"
echo ""

# --- SPECA の CONFIRMED 発見を抽出 ---
echo "SPECA の CONFIRMED 発見を抽出中..."
python3 -c "
import json, glob, sys

findings = []
for f in sorted(glob.glob('$SPECA_RESULTS_DIR/04_PARTIAL_*.json') + glob.glob('$SPECA_RESULTS_DIR/inst_*/04_PARTIAL_*.json')):
    try:
        data = json.load(open(f))
        items = data if isinstance(data, list) else data.get('reviewed_items', data.get('items', []))
        for item in items:
            verdict = item.get('review_verdict', item.get('verdict', ''))
            if verdict in ('CONFIRMED_VULNERABILITY', 'CONFIRMED_POTENTIAL'):
                findings.append({
                    'property_id': item.get('property_id', '?'),
                    'title': item.get('title', item.get('property_statement', '?'))[:150],
                    'severity': item.get('final_severity', item.get('severity', '?')),
                    'verdict': verdict,
                    'code_scope': item.get('code_scope', {}),
                })
    except Exception as e:
        print(f'Warning: {f}: {e}', file=sys.stderr)

json.dump(findings, open('$OUTPUT_DIR/speca_findings_for_codex.json', 'w'), indent=2, ensure_ascii=False)
print(f'{len(findings)} 件の CONFIRMED 発見を抽出しました')
" || { echo "SPECA 結果の抽出に失敗"; exit 1; }

FINDING_COUNT=$(python3 -c "import json; print(len(json.load(open('$OUTPUT_DIR/speca_findings_for_codex.json'))))")

if [ "$FINDING_COUNT" -eq 0 ]; then
  echo "CONFIRMED 発見がありません。Codex バリデーションをスキップします。"
  exit 0
fi

echo "$FINDING_COUNT 件の発見を Codex で検証します"
echo ""

# --- Codex で各発見を独立検証 ---
BASE_PROMPT="あなたは $LANGUAGE セキュリティ監査の検証者です。
ターゲット: $TARGET/$CONTRACT_DIR

以下の脆弱性報告が正当かどうかを検証してください。
実際のコードを読んで、報告の正確性を判定してください。

判定:
- VALID: 脆弱性は実在する
- INVALID: 誤検知、または脆弱性ではない
- UNCERTAIN: コードだけでは判断不能

各判定には根拠 (具体的なコード参照) を必ず付けてください。"

echo "=== Codex 検証エージェントを起動します ==="

# 発見をバッチに分割 (1 エージェントあたり最大 5 件)
python3 -c "
import json, math

findings = json.load(open('$OUTPUT_DIR/speca_findings_for_codex.json'))
batch_size = 5
num_batches = math.ceil(len(findings) / batch_size)

for i in range(num_batches):
    batch = findings[i*batch_size:(i+1)*batch_size]
    json.dump(batch, open(f'$OUTPUT_DIR/batch_{i+1:02d}.json', 'w'), indent=2, ensure_ascii=False)
    print(f'Batch {i+1}: {len(batch)} findings')
"

BATCH_COUNT=$(ls "$OUTPUT_DIR"/batch_*.json 2>/dev/null | wc -l | tr -d ' ')

for i in $(seq 1 "$BATCH_COUNT"); do
  BATCH_FILE="$OUTPUT_DIR/batch_$(printf '%02d' $i).json"
  RESULT_FILE="$OUTPUT_DIR/result_$(printf '%02d' $i).md"

  echo "$i/$BATCH_COUNT: $(basename $BATCH_FILE)"
  BATCH_CONTENT=$(cat "$BATCH_FILE")

  codex exec --skip-git-repo-check -s read-only -q \
    "$BASE_PROMPT

検証対象の発見:
$BATCH_CONTENT" \
    > "$RESULT_FILE" &
done

echo ""
echo "全 $BATCH_COUNT バッチをバックグラウンドで起動しました。完了を待機中..."
wait

echo ""
echo "=== Codex クロスバリデーション完了 ==="
echo "結果:"
for f in "$OUTPUT_DIR"/result_*.md; do
  SIZE=$(wc -c < "$f" | tr -d ' ')
  echo "  $(basename $f): ${SIZE} bytes"
done

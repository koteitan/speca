#!/bin/bash
# ============================================
# SPECA N 並列インスタンス起動スクリプト
# ============================================
# 使い方:
#   bash docs/hiro/templates/07_mass_launch.sh          # デフォルト 4 インスタンス
#   bash docs/hiro/templates/07_mass_launch.sh 8         # 8 インスタンス
#   bash docs/hiro/templates/07_mass_launch.sh 4 "02c 03 04"  # フェーズ指定
#
# 前提条件:
#   - 共有フェーズ (01a-01e) が実行済み
#   - outputs/BUG_BOUNTY_SCOPE.json が存在
#   - outputs/TARGET_INFO.json が存在
#
# 動作:
#   1. インスタンスディレクトリを作成
#   2. 共有データをシンボリックリンク
#   3. 各インスタンスで SPECA パイプライン (02c→03→04) をバックグラウンド実行

set -e

SPECA_DIR="${SPECA_DIR:-$(pwd)}"
NUM_INSTANCES=${1:-4}
PHASES=${2:-"02c 03 04"}
WORKERS=${WORKERS:-2}

echo "=== SPECA $NUM_INSTANCES 並列インスタンスを準備します ==="
echo "ディレクトリ: $SPECA_DIR"
echo "フェーズ: $PHASES"
echo "ワーカー数/インスタンス: $WORKERS"
echo ""

# --- 前提条件チェック ---
cd "$SPECA_DIR"

if [ ! -f outputs/01a_STATE.json ]; then
  echo "ERROR: outputs/01a_STATE.json が見つかりません。"
  echo "先に共有フェーズを実行してください:"
  echo "  uv run python3 scripts/run_phase.py --phase 01a 01b 01e --workers 4"
  exit 1
fi

if [ ! -f outputs/BUG_BOUNTY_SCOPE.json ]; then
  echo "ERROR: outputs/BUG_BOUNTY_SCOPE.json が見つかりません。"
  echo "スコープ定義ファイルを作成してください。"
  exit 1
fi

if [ ! -f outputs/TARGET_INFO.json ]; then
  echo "ERROR: outputs/TARGET_INFO.json が見つかりません。"
  echo "ターゲット情報ファイルを作成してください。"
  exit 1
fi

echo "--- 前提条件 OK ---"
echo ""

# --- インスタンスディレクトリ作成 + シンボリックリンク ---
for i in $(seq -w 1 "$NUM_INSTANCES"); do
  dir="outputs/inst_$i"
  echo "インスタンス $i: $dir を準備中..."
  mkdir -p "$dir"

  # 共有フェーズ出力をリンク
  ln -sf ../01a_STATE.json "$dir/" 2>/dev/null || true
  for f in ../01b_PARTIAL_*.json; do ln -sf "$f" "$dir/" 2>/dev/null || true; done
  for f in ../01e_PARTIAL_*.json; do ln -sf "$f" "$dir/" 2>/dev/null || true; done
  ln -sf ../graphs "$dir/" 2>/dev/null || true
  ln -sf ../BUG_BOUNTY_SCOPE.json "$dir/" 2>/dev/null || true
  ln -sf ../01b_SUBGRAPH_INDEX.json "$dir/" 2>/dev/null || true

  # TARGET_INFO はコピー
  cp outputs/TARGET_INFO.json "$dir/"
done

echo ""
echo "--- $NUM_INSTANCES インスタンスの準備完了 ---"
echo ""

# --- 並列実行 ---
echo "=== SPECA パイプラインを $NUM_INSTANCES 並列で起動します ==="
echo ""

PIDS=()

for i in $(seq -w 1 "$NUM_INSTANCES"); do
  dir="outputs/inst_$i"
  LOG="outputs/logs/speca_inst_${i}.log"
  mkdir -p outputs/logs

  echo "Instance $i: SPECA_OUTPUT_DIR=$dir で起動..."
  SPECA_OUTPUT_DIR="$dir" uv run python3 scripts/run_phase.py \
    --phase $PHASES \
    --workers "$WORKERS" \
    > "$LOG" 2>&1 &
  PIDS+=($!)

  # API レート制限回避のため少し間隔を空ける
  sleep 5
done

echo ""
echo "=== $NUM_INSTANCES インスタンスをバックグラウンドで起動しました ==="
echo "PID: ${PIDS[*]}"
echo ""
echo "ログ確認: tail -f outputs/logs/speca_inst_*.log"
echo "完了待ち: wait ${PIDS[*]}"
echo ""

# --- 完了待機 ---
echo "全インスタンスの完了を待機中..."
FAILED=0
for i in "${!PIDS[@]}"; do
  N=$((i + 1))
  if wait "${PIDS[$i]}"; then
    echo "  Instance $N: 完了"
  else
    echo "  Instance $N: 失敗 (exit code: $?)"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "=== 全 $NUM_INSTANCES インスタンス完了 (失敗: $FAILED) ==="

# --- 結果サマリー ---
echo ""
echo "=== 結果サマリー ==="
for i in $(seq -w 1 "$NUM_INSTANCES"); do
  dir="outputs/inst_$i"
  COUNT_04=$(ls "$dir"/04_PARTIAL_*.json 2>/dev/null | wc -l | tr -d ' ')
  COUNT_03=$(ls "$dir"/03_PARTIAL_*.json 2>/dev/null | wc -l | tr -d ' ')
  COUNT_02c=$(ls "$dir"/02c_PARTIAL_*.json 2>/dev/null | wc -l | tr -d ' ')
  echo "  Instance $i: 02c=$COUNT_02c, 03=$COUNT_03, 04=$COUNT_04 PARTIAL files"
done

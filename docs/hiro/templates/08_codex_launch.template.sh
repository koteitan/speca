#!/bin/bash
# ============================================
# Codex 12 並列エージェント起動スクリプト (テンプレート)
# ============================================
# 使い方:
#   1. TARGET, LANGUAGE, CONTRACT_DIR の変数を編集
#   2. 攻撃面をターゲットプロトコルに合わせて調整
#   3. bash docs/hiro/templates/08_codex_launch.sh
#
# 変数:
#   TARGET      — ターゲットリポジトリのローカルパス
#   LANGUAGE    — プログラミング言語 (例: "Sui Move", "Solidity", "Rust")
#   CONTRACT_DIR — メインコントラクトのディレクトリ

set -e

# === ここを編集 ===
TARGET="${TARGET:-/path/to/target-repository}"
LANGUAGE="${LANGUAGE:-Sui Move}"
CONTRACT_DIR="${CONTRACT_DIR:-contracts/protocol/sources}"
# ==================

OUTPUT_DIR="outputs/codex_results"
mkdir -p "$OUTPUT_DIR"

echo "=== Codex 12 エージェントを並列起動します ==="
echo "ターゲット: $TARGET"
echo "言語: $LANGUAGE"
echo "出力先: $OUTPUT_DIR"
echo ""

BASE_PROMPT="あなたは $LANGUAGE スマートコントラクトセキュリティ監査人です。
ターゲット: $TARGET/$CONTRACT_DIR
コードベース全体を読み、脆弱性を全て見つけてください。
各発見について: タイトル(英語)、深刻度(HIGH/MEDIUM/LOW)、根本原因(ファイル名:行番号+コードスニペット)、攻撃シナリオ、影響、修正案を詳細に報告してください。"

# === 攻撃面をターゲットに合わせて調整 ===
# DeFi レンディングの例:
ATTACK_SURFACES=(
  "Flash Loan (borrow_flash_loan, repay_flash_loan, hot-potato, fee, reentrancy)"
  "Oracle (get_price, get_spot_price, EMA vs Spot, deviation check, staleness)"
  "Liquidation (liquidation_inner, close_factor, seized amount, revenue_factor)"
  "eMode (borrow cap tracking, collateral_factor, group switching, admin changes)"
  "Interest Rate (accrue_interest, simple vs compound, borrow_index, reserve_factor)"
  "Access Control (AdminCap, whitelist, permissions, caller validation)"
  "Rate Limiter (add_outflow, reduce_outflow, sliding window, segment management)"
  "Deposit/Withdraw (handle_mint, handle_redeem, exchange rate, cToken)"
  "Referral (self-referral check, deposit threshold, generate_referral_code)"
  "ADL Auto-Deleverage (activation vs stop conditions, global vs emode scope)"
  "Math/Precision (floor truncation, ceil, overflow, WAD conversion)"
  "Reserve/Revenue (take_revenue, cash_reserve, protocol fee, repay rounding)"
)

FILENAMES=(
  "01_flash_loan" "02_oracle" "03_liquidation" "04_emode"
  "05_interest" "06_access_control" "07_rate_limiter" "08_deposit_withdraw"
  "09_referral" "10_adl" "11_math_precision" "12_reserve_revenue"
)

for i in "${!ATTACK_SURFACES[@]}"; do
  N=$((i + 1))
  echo "$N/12: ${FILENAMES[$i]}"
  codex exec --skip-git-repo-check -s read-only -q \
    "$BASE_PROMPT 攻撃面: ${ATTACK_SURFACES[$i]}" \
    > "$OUTPUT_DIR/${FILENAMES[$i]}.md" &
done

echo ""
echo "全 12 エージェントをバックグラウンドで起動しました。完了を待機中..."
wait

echo ""
echo "=== 全 Codex エージェント完了 ==="
echo "結果:"
for f in "$OUTPUT_DIR"/*.md; do
  SIZE=$(wc -c < "$f" | tr -d ' ')
  echo "  $(basename $f): ${SIZE} bytes"
done

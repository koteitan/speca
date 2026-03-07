あなたは {{PROTOCOL_NAME}} (Sherlock #{{CONTEST_NUMBER}}) 監査のオーケストレーターです。
12 個の並列エージェントを Agent ツールで起動し、各攻撃面を分担して脆弱性を探してください。

## セットアップ

cd /Users/hiro/Documents/security-agent
git fetch origin
git checkout -b hiro/{{BRANCH_PREFIX}}-agent-<空き番号> origin/hiro/{{BASE_BRANCH}}

## ターゲット

{{TARGET_PATH}}

## 手順

1. ターゲットのコード構造を確認し、主要モジュールを特定する

2. 以下のような攻撃面ごとに Agent ツール (subagent_type="general-purpose") を 12 個同時起動する。攻撃面はターゲットに合わせて調整すること:

DeFi レンディングの場合の典型的な攻撃面:
- Flash Loan, Oracle, Liquidation, eMode/Isolation, Interest Rate, Access Control
- Rate Limiter, Deposit/Withdraw, Referral, ADL, Math/Precision, Reserve/Revenue

DEX の場合:
- Swap, Liquidity, Fee, Oracle, Flash Loan, Governance
- Access Control, Math/Precision, Migration, Emergency, Reward, Front-running

各エージェントのプロンプトテンプレート:
```
あなたは {{LANGUAGE}} スマートコントラクトセキュリティ監査人です。
ターゲット: {{TARGET_PATH}}
攻撃面: [攻撃面名と対象ファイル]

1. 指定されたファイルとその依存先を全て読む
2. STRIDE + CWE Top 25 の観点で脆弱性を探す
3. 各発見を JSON で報告 (title, severity, root_cause, code_snippet, description, impact, recommendation)
```

3. 全エージェント結果を収集し、重複排除、既存レポートとの照合

4. 新規発見を outputs/reports/ に Sherlock 形式でレポート化

5. コミット → PR → 即マージ

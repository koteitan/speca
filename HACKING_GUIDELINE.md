# ハッキング・ガイドライン

## ハッキング・エージェントの全体像
1. [仕様書作成](.claude/commands/01_spec.md): 仕様書とメタデータを洗い出して `security-agent/outputs/01_SPEC.json` へ保存する。 仕様、スコープ、バウンティ条件の唯一のソースとして扱う。
2. [コールグラフ作成](`.claude/commands/02_order.md): ` 探索すべきファイルに優先順位をつけ、 `security-agent/outputs/02_ORDER.json` へ保存する。
3. 監査エージェント実行 (以下のどれかを実行)
   1. [静的コードベース監査](`.claude/commands/03_auditmap.md): ` コードベースを一行ずつチェックしながら、怪しい箇所に@auditコメントを残す。静的レビュー成果 (`security-agent/outputs/03_AUDITMAP.json`) を格納。
   2. [動的テストベース監査](.claude/commands/03b_dynamictest.m): ダイナミックテストやリプレイを行いながらバグを探索する。
   3. [既知バグとの照合による監査](.claude/commands/03c_auditissue.md): `security-agent/outputs/00_issues.json` に事前に用意した既知バグをもとに、類似バグがないかコードベース監査を行う。静的レビュー成果 (`security-agent/outputs/03_AUDITMAP.json`) を格納。
4. [監査結果レビュー](.claude/commands/04_review.md): 監査結果の妥当性をレビューし、逸脱指摘、再調整プランを記録。
   - ここが終わった時点で`03_AUDITMAP.json`を人間レビューへ回し、人間が各結果を理解し、Chat GPT-5-Thinkingも使いながら各報告の妥当性を検証する。
5. [単体テストによるPoC](.claude/commands/05_poc_unit.md): バグを再現する最低限のテストファイルを作成する。
6.  [統合テストによるPoC](.claude/commands/05_poc_integration.md): バグを再現するE2Eのテストファイルを作成する。
7. [報告レポート作成](.claude/commands/07_report.md): 最終レポートを`security-agent/outputs/report_xxxx.md`に作成する。

---

## ハッキング手順書

以下の手順に従い、エージェントベース監査を進めてください。

#### 1. ハッキング対象レポジトリのクローン

以下コマンドでクローン:
```
git clone <ハッキングしたいレポジトリ>
cd <レポジトリのルートディレクトリ>
```

---

#### 2. NyxFoundationのGitHub監査用レポ作成 (絶対にプライベートレポジトリ)

NyxFoundationのGitHub Orgで `audit-<project>`（例: `audit-nimbus`）**プライベート**レポジトリを作成してください。

作成が完了したらリモートに追加:
```
git remote add audit git@github.com:NyxFoundation/<audit-repo>.git
```

---

#### 3. security-agentを準備

監査対象レポジトリのルートディレクトリで以下を実行:
```
git clone -b BRANCH_NAME git@github.com:NyxFoundation/security-agent.git
rm -rf security-agent/.git
```

---

#### 4. ハッキング

[.claude/commands/](.claude/commands/)にあるプロンプトを02,03,04の順番に進めていく。

以下のようにテキストベースで引数を指定。引数はMDファイルのUsageを参考にすること。

03は03_auditmapか03c_auditissueのどちらかを選択して実行。

```
codex --ask-for-approval never --sandbox workspace-write --search
>> Do the following task with ARGMENT=VELUE, ..., . <MDファイルをコピペ>
```

気をつけること
- 03_AUDITMAPでは各実行後に `未着手のPR/ISSUEの調査を続けて` を 10 回前後送信し、バックログ処理を促す。
- 各ステップごとにcodexを立ち上げ直し、コンテキストウィンドウをリセットする。

---

#### 5. ハッキング結果のレビュー

`outputs/03_AUDITMAP.json`に`Vuln`とラベル付けされた項目があれば、それがどのようなバグで、どのような攻撃に繋がるのか理解し、妥当性を自己検証する。

必要であればChat-GPT-5-thinkingにも妥当性を検証してもらう。

---

#### 6. GitHubへアップ

```
git add .
git commit -m"hacking finished"
git push audit HEAD
```

#### 7. Discordでレビュー依頼

@grandchildriceへハッキング終了を報告

```
@grandchildrice

ハッキングが終わったので、確認お願いします。

<GitHubのリンク>
```
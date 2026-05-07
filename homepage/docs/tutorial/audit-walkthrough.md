---
sidebar_position: 1
---

# テストリポジトリで監査をしてみよう

speca-cli がインストール済みの方向けに、公開リポジトリを使って監査の一連の流れを体験するハンズオンです。ターゲットには OpenZeppelin の `Ownable.sol` (アクセス制御の定番実装) を使います。短いコードで動作全体を確認できるため、最初の練習に向いています。

## 前提と準備

speca-cli が動作することを確認します。

```bash
node cli/dist/cli.js doctor
```

出力例:

```
[ok] Node.js 20.x
[ok] Python 3.11 (uv)
[ok] Claude Code CLI authenticated
```

エラーがある場合は [とりあえず動かしてみる](../guide/try-it.md) に戻って環境を整えてください。

## 1. 設定ファイルを準備する

`speca init` を実行すると、2 つのファイルを対話形式で作成できます。

```bash
node cli/dist/cli.js init
```

今回は以下の内容で `outputs/TARGET_INFO.json` を用意します。

```json
{
  "repo_url": "https://github.com/OpenZeppelin/openzeppelin-contracts",
  "commit": "v4.9.6",
  "language": "solidity",
  "description": "OpenZeppelin Contracts v4.9.6"
}
```

`outputs/BUG_BOUNTY_SCOPE.json` にはスコープ情報を書きます。

```json
{
  "scope": "Access control invariants in contracts/access/Ownable.sol",
  "out_of_scope": "UI, deployment scripts",
  "severity_levels": ["High", "Medium", "Low"]
}
```

この 2 ファイルがパイプライン全体の入力になります。

## 2. speca init を実行する

```bash
node cli/dist/cli.js init
```

init は上記の JSON を読み込んで内部設定を確定し、Phase 01a の仕様クロール準備を完了します。成功すると以下のようなメッセージが表示されます。

```
[init] TARGET_INFO loaded: OpenZeppelin Contracts v4.9.6
[init] BUG_BOUNTY_SCOPE loaded: 1 scope entry
[init] Ready. Run: speca run --target 04
```

## 3. 監査を実行する

```bash
node cli/dist/cli.js run --target 04
```

`--target 04` は Phase 04 まで全フェーズを順に実行することを意味します。実行中は NDJSON 形式のログがターミナルに流れます。

```
{"phase":"01a","status":"running","found":3}
{"phase":"01b","status":"running","subgraph":"Ownable-ownership-transfer"}
{"phase":"01e","status":"running","property":"PROP-001","description":"onlyOwner修飾子が全ての管理関数に適用されているか"}
{"phase":"02c","status":"running","resolved":5}
{"phase":"03","status":"running","proof_attempt":"PROP-001","result":"gap_found"}
{"phase":"04","status":"running","verdict":"CONFIRMED_POTENTIAL"}
```

各行の `phase` フィールドを見れば、今どの段階を実行しているかが分かります。`result: gap_found` は「証明できない部分が見つかった」ことを意味し、Phase 04 で最終判定が下ります。

## 4. 結果を眺める

```bash
node cli/dist/cli.js browse outputs/04_PARTIAL_*.json
```

検出された候補が一覧で表示されます。各行には以下の情報が含まれます。

- `property_id`: どのセキュリティプロパティに対する検出か
- `severity`: High / Medium / Low の重要度
- `verdict`: CONFIRMED_VULNERABILITY / CONFIRMED_POTENTIAL / DISPUTED_FP など
- `location`: 問題のあるコードファイルと行番号
- `description`: なぜ問題と判断したかの説明

## 5. 結果の解釈

`Ownable.sol` は短くシンプルなコードなので、今回は大きな脆弱性は見つからないはずです。代わりに「仕様の範囲でオーナー移譲の確認フロー (2-step transfer) が実装されているか」といった条件が CONFIRMED_POTENTIAL として報告されることがあります。

**何が見つかっても、見つからなくても** 、パイプラインが動いて結果が出れば成功です。「検出なし = バグなし」ではなく「指定したスコープと仕様の範囲では問題が見つからなかった」と読んでください。

## 6. 次は自分のリポジトリで

動作を確認したら、`outputs/TARGET_INFO.json` と `outputs/BUG_BOUNTY_SCOPE.json` を自分のプロジェクトの情報に書き換えて同じ手順を繰り返してください。スコープを具体的に書くほど、結果の精度が上がります。

より複雑なターゲット (例: [Lighthouse Ethereum client](https://github.com/sigp/lighthouse)) で試す場合は、仕様書の量が多いため Phase 01a と 01b に時間がかかります。`--workers 4` オプションで並列度を上げると処理が速くなります。

```bash
node cli/dist/cli.js run --target 04 --workers 4
```

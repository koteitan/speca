---
sidebar_position: 1
---

# テストリポジトリで監査を体験

すでに `speca-cli` をインストール済みのユーザー向けハンズオンです。対象は OpenZeppelin の `Ownable.sol` (代表的なアクセス制御実装)。コードが短いので初回エンドツーエンド実行に向きます。

## 0. 環境チェック

```bash
speca doctor
```

期待される出力:

```
[ok] Node.js 20.x
[ok] Python 3.11 (uv)
[ok] Claude Code CLI authenticated
[ok] MCP servers: fetch, tree_sitter
```

`[err]` 行があれば、まず [とりあえず動かしてみる](../guide/try-it.md) に戻って環境を整備してください。

## 1. 設定ファイルを書く

対話 (`speca init`) でも、手書きでも構いません。本ウォークスルーでは以下の値を使います。

`outputs/TARGET_INFO.json`:

```json
{
  "project_name": "openzeppelin-ownable-walkthrough",
  "target_repo": "https://github.com/OpenZeppelin/openzeppelin-contracts",
  "target_commit": "v4.9.6",
  "target_language": "Solidity",
  "target_layer": "library",
  "description": "OpenZeppelin Contracts v4.9.6 — Ownable.sol"
}
```

`outputs/BUG_BOUNTY_SCOPE.json`:

```json
{
  "program_name": "openzeppelin-ownable-walkthrough",
  "scope_version": "1.0",
  "in_scope": ["contracts/access/Ownable.sol"],
  "out_of_scope": ["test/", "scripts/"],
  "severity_classification": {
    "HIGH":   { "description": "Unauthorized owner change",
                "cwe": ["CWE-862", "CWE-863"],
                "examples": ["Bypass of onlyOwner"] },
    "MEDIUM": { "description": "Two-step transfer divergence from spec",
                "cwe": ["CWE-841"],
                "examples": ["Pending owner not cleared"] },
    "LOW":    { "description": "Quality / informational",
                "cwe": ["CWE-710"],
                "examples": ["Misleading event"] }
  },
  "scope_notes": "Walkthrough — single contract."
}
```

両者のスキーマ詳細は [設定ファイル](../getting-started/config-files.md) にあります。

## 2. 監査を実行

```bash
speca run --target 04 --workers 4
```

TUI ダッシュボードにイベントが流れます。1 コントラクトなら 2〜4 分で終わります:

```
{"phase":"01a","status":"running","found":3}
{"phase":"01b","status":"running","subgraph":"Ownable-ownership-transfer"}
{"phase":"01e","status":"running","property":"PROP-001",
 "description":"onlyOwner is applied to all administrative functions"}
{"phase":"02c","status":"running","resolved":5}
{"phase":"03","status":"running","property":"PROP-001","result":"gap_found"}
{"phase":"04","status":"running","verdict":"CONFIRMED_POTENTIAL"}
```

`result: gap_found` は「証明の閉じない部分が見つかった」状態。最終 `verdict` は Phase 04 の 3 ゲート通過後に決まります。TUI の代わりに NDJSON を流すには `speca run --target 04 --json`。

## 3. 結果を閲覧

```bash
speca browse
```

各行に表示されるもの:

- `property_id` — 該当のセキュリティプロパティ
- `severity` — High / Medium / Low / Informational
- `verdict` — `CONFIRMED_VULNERABILITY` / `CONFIRMED_POTENTIAL` / `DISPUTED_FP` / …
- `location` — ファイルと行範囲
- `proof_gap` / `description` — 検出根拠

`c` でコード覗き、`f` でフィルタ調整、`q` で終了。

## 4. 結果の読み方

`Ownable.sol` は短く実績のあるコードなので、クリーン実行で High 重大度の脆弱性が出る可能性は低いです。よく出るパターンとしては、二段階所有権移譲フロー (仕様の "transfer 時に pending owner をクリアする" ルール) に対する `CONFIRMED_POTENTIAL`、あるいは Trust Boundary ゲートで弾かれる `DISPUTED_FP` です。

**何も見つからなかったとしても、パイプラインがエンドツーエンドで通った時点で成功です。** "no findings" は「指定スコープと生成プロパティの範囲では proof gap が残らなかった」という意味で、「バグがない」ではありません。

## 5. 自分のリポジトリへ

`outputs/TARGET_INFO.json` と `outputs/BUG_BOUNTY_SCOPE.json` を自分のプロジェクトの値に差し替えて `speca run --target 04` を再実行します。スコープ (`in_scope` パスと重大度ルブリック) を具体的に書くほど結果の質が上がります。

[Lighthouse Ethereum クライアント](https://github.com/sigp/lighthouse) のような大規模対象では、仕様コーパスが大きいため Phase 01a / 01b に時間がかかります。並列度を上げてください:

```bash
speca run --target 04 --workers 8 --max-concurrent 16 --budget 80
```

`--budget 80` はフェーズを $80 で停止 (終了コード 64)。トレードオフの詳細は [モデル選定の設計ノート](../design-notes/model-benchmark-takeaways.md) を参照してください。

---
sidebar_position: 3
---

# ベンチマーク成果物の配布

`benchmarks/results/` 配下のベンチマーク生出力(per-target audit traces / finding labels / LLM cache、合計 350 MB+)は Git ではなく **GitHub Release** に bundle して配布します。speca リポジトリ自体は「レンダリング済みの図 (`*.png`) と paper の表 (`*.tex`) と人手レビュー文書 (`*.md`)」だけを保持し、生データはタグ単位の tarball で扱います。

## タグ命名規則

```
bench-<rq>-<utc-date>-<suffix>
```

例:

| タグ | 中身 |
|---|---|
| `bench-rq1-20260508-sherlock_ethereum_audit_contest` | RQ1 の Sherlock 出力一式 |
| `bench-rq2a-20260508-sonnet4` | RQ2 の Claude Sonnet 4 sweep |
| `bench-rq2a-20260508-deepseek_r1` | RQ2 の DeepSeek R1 sweep |
| `bench-rq2a-20260508-figures` | RQ2 の図のみ |
| `bench-rq2b-20260508-figures` | RQ2b の図(探索的) |

## ダウンロード(再展開)

```bash
# 一覧
gh release list --repo NyxFoundation/speca | grep '^bench-'

# 展開
bash benchmarks/scripts/restore-results.sh bench-rq2a-20260508-sonnet4
# → benchmarks/results/rq2a/speca_sonnet4/ に展開される
```

`restore-results.sh` の動作:

1. tag 名で release を `gh release download`
2. sidecar `<tag>.manifest.json` の `archive_sha256` で tarball を検証
3. `source_path` に従って **元の場所に in-place 展開**
4. 展開済みファイル数を manifest と照合

オプション:

| フラグ | 用途 |
|---|---|
| `--out <dir>` | 元の場所ではなく指定ディレクトリに展開 |
| `--force` | 既存ターゲットを削除してから展開 |
| `--keep-archive` | 展開先に tarball + manifest のコピーを残す(再アップロード用) |

## 公開(publish)

通常は GitHub Action `Publish benchmark artifacts`(`workflow_dispatch` 専用)を使います:

```bash
gh workflow run publish-bench-artifacts.yml -R NyxFoundation/speca \
  --ref main \
  -f subdir=rq2a/speca_sonnet4
```

主要な input:

| input | 既定 | 説明 |
|---|---|---|
| `subdir` | (必須) | `benchmarks/results/` 直下のパス。例: `rq2a/speca_sonnet4` |
| `tag_suffix` | (空) | 空なら leaf 名から `speca_` を除去 |
| `tag_date` | (空) | YYYYMMDD UTC、空なら今日 |
| `notes` | (空) | release notes に追記する markdown |
| `ref` | (空) | checkout する git ref |

ワークフローは:

1. `benchmarks/scripts/publish-results.sh` で `<tag>.tar.zst` + `<tag>.manifest.json` を生成
2. zstd 圧縮 + sha256 計算 + ファイル数記録
3. pre-release として `gh release create`(既存タグなら `--clobber` で上書き + notes 再生成)

## ローカルから直接 publish したい場合

self-hosted runner にデータがあるとき:

```bash
bash benchmarks/scripts/publish-results.sh \
  benchmarks/results/rq2a/speca_sonnet4 \
  bench-rq2a-20260508-sonnet4

gh release create bench-rq2a-20260508-sonnet4 \
  --title bench-rq2a-20260508-sonnet4 \
  --prerelease \
  --notes "Local publish from $(git rev-parse --short HEAD)" \
  dist/bench-artifacts/bench-rq2a-20260508-sonnet4.tar.zst \
  dist/bench-artifacts/bench-rq2a-20260508-sonnet4.manifest.json
```

## 必要なツール

`tar --zstd`(GNU tar 1.31+ / macOS は `brew install gnu-tar` で `gtar`、または bsdtar 3.5+)、`zstd`、`jq`、`python3`、`gh`。

## `.gitignore` の挙動

`benchmarks/results/**` は ignore、ただし `*.png` / `*.tex` / `*.md` は **allowlist** されています。図やレビュー文書だけは git で管理、生 trace ファイル(`*.json` / `*.jsonl` / `*.csv`)は Release 経由で取得する設計です。新しい種類のドキュメンテーション artifact を commit したい場合は `.gitignore` 側の allowlist を増やしてください(`git add -f` ではなく)。

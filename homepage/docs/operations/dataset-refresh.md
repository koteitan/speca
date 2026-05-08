---
sidebar_position: 2
---

# データセットを更新する

[`NyxFoundation/vulnerability-reports`](https://huggingface.co/datasets/NyxFoundation/vulnerability-reports) は SPECA が公開している監査 finding コーパスです。Code4rena / Sherlock / CodeHawks の高重大度 H/M issue を統一 schema で正規化し、HuggingFace の **マルチコンフィグ datasets**(1 ドメイン = 1 config)として配布します。現在は `defi`(~4,500 行)のみ。

## 何が起こるか

```
  scripts/scrape_*.py を手元で実行
        ↓
  benchmarks/data/defi_audit_reports/*.csv が更新される
        ↓
  workflow `Publish dataset to HuggingFace` を dispatch
        ↓
  HF 側の <domain>/train.parquet が差し替わる
        ↓
  load_dataset("NyxFoundation/vulnerability-reports", "defi", split="train") の中身が新しくなる
```

`<domain>/` 単位で `delete_patterns` が効いているので、`defi` を更新しても `lending` 等は影響を受けません。

## 手順

### 1. scrape を手元で回す

```bash
cd speca
uv run python3 scripts/scrape_code4rena.py
uv run python3 scripts/scrape_sherlock.py
uv run python3 scripts/scrape_codehawks.py
```

それぞれ `benchmarks/data/defi_audit_reports/` 配下に `*_all_issues.csv` を書き出します。`gh auth login` 済みであることが前提です(各スクレイパが GitHub API を叩くため)。

### 2. self-hosted runner に CSV を渡す

`Publish dataset to HuggingFace` workflow は self-hosted runner で動作します。runner 上に scrape 結果を配置してください。同一マシンで scrape も走らせている場合は何もしなくて OK。

### 3. workflow を dispatch

GitHub UI から、または `gh` CLI から:

```bash
gh workflow run datasets-publish.yml -R NyxFoundation/speca \
  --ref main \
  -f domain=defi \
  -f dry_run=false
```

主要な input:

| input | 既定値 | 説明 |
|---|---|---|
| `domain` | `defi` | HF config 名(`[a-z0-9]+(-[a-z0-9]+)*`) |
| `source` | `benchmarks/data/defi_audit_reports/{code4rena,sherlock,codehawks}_all_issues.csv` | カンマ区切り。union される |
| `filter_platforms` | `code4rena,sherlock,codehawks` | プラットフォームフィルタ |
| `severity_filter` | (空) | 例: `High,Medium` |
| `max_rows` | `0` | 0 = 制限なし |
| `dry_run` | `false` | true なら HF push をスキップしてレンダーのみ |

### 4. 結果確認

```bash
gh run watch <run-id> -R NyxFoundation/speca
```

成功すれば run の Summary に manifest(行数・platform 内訳・severity 内訳)が出ます。HF 側を確認:

```bash
uv run --group datasets python3 -c "
from datasets import load_dataset
ds = load_dataset('NyxFoundation/vulnerability-reports', 'defi', split='train')
print(ds.shape, ds.column_names)
"
```

## 新しいドメインを追加する

1. 該当ドメインの CSV を runner からアクセス可能なパスに配置
2. workflow を `domain=<新ドメインの slug>`、`source=<csv-path>` で dispatch

`delete_patterns=["<domain>/*"]` が効くので、既存 `defi` は影響を受けません。HF 側は新しい `<domain>/` フォルダを自動的に config として認識します。

## 内部構造

ビルド/パブリッシュのパイプラインは [`scripts/datasets/`](https://github.com/NyxFoundation/speca/tree/main/scripts/datasets) に実装されています:

- `build_derived.py` — 複数 CSV を unified parquet に正規化
- `publish_hf.py` — parquet + dataset card を HF に push
- `load.py` — consumer 用ロードヘルパー(`load_findings(domain="defi")`)

スキーマ:

| フィールド | 説明 |
|---|---|
| `id` | `<platform>:<contest-slug>:<issue_id>`(欠けていれば hash fallback) |
| `source_platform` | `code4rena` / `sherlock` / `codehawks` |
| `contest` | スラッグ化されたコンテスト ID |
| `issue_id` | プラットフォームローカル ID |
| `severity` | `High` / `Medium` / `Low` / `Info` |
| `title` / `description` | 上流 verbatim |
| `source_url` | 上流リンク(code4rena は決定的に合成、他は scrape 由来があれば) |
| `domain` | `defi` 等 |
| `scraped_at` | ISO 8601 UTC |

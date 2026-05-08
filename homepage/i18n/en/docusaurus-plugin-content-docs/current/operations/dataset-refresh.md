---
sidebar_position: 2
---

# Refresh the dataset

[`NyxFoundation/vulnerability-reports`](https://huggingface.co/datasets/NyxFoundation/vulnerability-reports) is the audit-finding corpus that SPECA publishes. It normalizes high-severity H/M issues from Code4rena / Sherlock / CodeHawks under a unified schema, and distributes them as a HuggingFace **multi-config dataset** (1 domain = 1 config). Currently only `defi` (~4,500 rows) is provided.

## What happens

```
  Run scripts/scrape_*.py locally
        ↓
  benchmarks/data/defi_audit_reports/*.csv is updated
        ↓
  Dispatch workflow `Publish dataset to HuggingFace`
        ↓
  <domain>/train.parquet on HF is replaced
        ↓
  load_dataset("NyxFoundation/vulnerability-reports", "defi", split="train") returns the new content
```

`delete_patterns` works at `<domain>/` granularity, so refreshing `defi` does not affect `lending` and others.

## Procedure

### 1. Run scrape locally

```bash
cd speca
uv run python3 scripts/scrape_code4rena.py
uv run python3 scripts/scrape_sherlock.py
uv run python3 scripts/scrape_codehawks.py
```

Each writes `*_all_issues.csv` under `benchmarks/data/defi_audit_reports/`. Each scraper hits the GitHub API, so `gh auth login` must already be set up.

### 2. Pass the CSVs to the self-hosted runner

The `Publish dataset to HuggingFace` workflow runs on a self-hosted runner. Place the scrape results on the runner. If you also run scraping on the same machine, nothing extra is needed.

### 3. Dispatch the workflow

From the GitHub UI, or via the `gh` CLI:

```bash
gh workflow run datasets-publish.yml -R NyxFoundation/speca \
  --ref main \
  -f domain=defi \
  -f dry_run=false
```

Key inputs:

| input | default | description |
|---|---|---|
| `domain` | `defi` | HF config name (`[a-z0-9]+(-[a-z0-9]+)*`) |
| `source` | `benchmarks/data/defi_audit_reports/{code4rena,sherlock,codehawks}_all_issues.csv` | comma-separated; unioned |
| `filter_platforms` | `code4rena,sherlock,codehawks` | platform filter |
| `severity_filter` | (empty) | e.g. `High,Medium` |
| `max_rows` | `0` | 0 = no limit |
| `dry_run` | `false` | if true, skip the HF push and only render |

### 4. Verify the result

```bash
gh run watch <run-id> -R NyxFoundation/speca
```

On success, the run Summary lists a manifest (row count, platform breakdown, severity breakdown). Verify on the HF side:

```bash
uv run --group datasets python3 -c "
from datasets import load_dataset
ds = load_dataset('NyxFoundation/vulnerability-reports', 'defi', split='train')
print(ds.shape, ds.column_names)
"
```

## Adding a new domain

1. Place the domain's CSV at a path accessible from the runner
2. Dispatch the workflow with `domain=<slug for the new domain>` and `source=<csv-path>`

Because `delete_patterns=["<domain>/*"]` applies, the existing `defi` is not affected. HF will automatically recognize the new `<domain>/` folder as a config.

## Internal structure

The build/publish pipeline is implemented under [`scripts/datasets/`](https://github.com/NyxFoundation/speca/tree/main/scripts/datasets):

- `build_derived.py` — normalizes multiple CSVs into a unified parquet
- `publish_hf.py` — pushes parquet + dataset card to HF
- `load.py` — consumer-side load helper (`load_findings(domain="defi")`)

Schema:

| Field | Description |
|---|---|
| `id` | `<platform>:<contest-slug>:<issue_id>` (hash fallback if missing) |
| `source_platform` | `code4rena` / `sherlock` / `codehawks` |
| `contest` | slugified contest ID |
| `issue_id` | platform-local ID |
| `severity` | `High` / `Medium` / `Low` / `Info` |
| `title` / `description` | upstream verbatim |
| `source_url` | upstream link (deterministically synthesized for code4rena; from scrape if available for others) |
| `domain` | `defi`, etc. |
| `scraped_at` | ISO 8601 UTC |

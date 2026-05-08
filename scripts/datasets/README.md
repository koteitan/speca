# `scripts/datasets/` — SPECA → HuggingFace pipeline

Builds normalized audit-finding parquets from raw scraper output and
pushes them to `NyxFoundation/vulnerability-reports` on HuggingFace.

The repo holds one **config per security domain** — the publisher writes
to `<domain>/train.parquet` + `<domain>/manifest.json`, leaving other
domains' folders untouched. HF auto-detects each `<domain>/` as a config;
consumers load with `load_dataset(repo, "<domain>", split="train")`.

## Files

| Path | Role |
|---|---|
| [`build_derived.py`](build_derived.py) | Read CSV(s) → unified parquet + `manifest.json` under `dist/datasets/<domain>/`. Layout mirrors the HF target: `<domain>/train.parquet` directly. |
| [`publish_hf.py`](publish_hf.py) | Render the global dataset card from `templates/README.md.j2`, stage `<domain>/train.parquet` + `<domain>/manifest.json` + `README.md`, then `upload_folder` with `delete_patterns=["<domain>/*"]` so other configs survive. `--dry-run` skips network. |
| [`load.py`](load.py) | Single helper consumers should call: `load_findings(domain="defi")` returns a pandas DataFrame, defaulting to HF (`NyxFoundation/vulnerability-reports`, config = domain), with a `local_parquet=` override for offline / dev. |
| [`templates/README.md.j2`](templates/README.md.j2) | Jinja template for the GLOBAL HF dataset card (schema + provenance only — per-domain build state lives in `<domain>/manifest.json`). |

## Install

```bash
uv sync --group datasets
```

## Local end-to-end (dry-run, no HF push)

```bash
# 1. Build a parquet from the canonical CSV.
uv run --group datasets python3 scripts/datasets/build_derived.py \
  --domain defi \
  --source csv/similar_audit_findings.csv \
  --out-dir dist/datasets

# 2. Render the dataset card and dry-run the upload.
#    --repo defaults to NyxFoundation/vulnerability-reports.
uv run --group datasets python3 scripts/datasets/publish_hf.py \
  --src dist/datasets/defi \
  --dry-run

# 3. Load it back the way consumers will:
uv run --group datasets python3 - <<'PY'
from scripts.datasets.load import load_findings
df = load_findings(domain="defi", local_parquet="dist/datasets/defi/train.parquet")
print(df.shape, df.columns.tolist())
PY
```

## Publishing for real

The recommended path is the **`Publish dataset to HuggingFace` GitHub
Action** (`.github/workflows/datasets-publish.yml`, `workflow_dispatch`
only, self-hosted, gated to a maintainer allowlist). Inputs:

| Input | Purpose |
|---|---|
| `domain` | Config name (`defi`, `lending`, `oracle`, …). Becomes the top-level folder in the HF repo. |
| `source` | CSV path to ingest. Default: `csv/similar_audit_findings.csv`. |
| `filter_platforms` | Comma-separated; default `code4rena,sherlock,codehawks`. |
| `severity_filter` | Comma-separated; empty means all severities. |
| `max_rows` | Cap row count, useful for sanity checks. `0` = no cap. |
| `dry_run` | If true, render but skip the HF push. Useful before flipping live. |
| `ref` | Git ref to checkout. Default: current branch. |

Required secret: `HF_TOKEN` with write access to the `NyxFoundation`
HF org. Set under Settings → Secrets and variables → Actions.

## Schema (one row per audit finding)

| Field | Description |
|---|---|
| `id` | `<platform>:<contest>:<issue_id>`; hash fallback if any are missing. |
| `source_platform` | `code4rena` / `sherlock` / `codehawks`. |
| `contest` | Platform-specific contest identifier. |
| `issue_id` | Platform-local id, `#`-stripped. |
| `severity` | `High` / `Medium` / `Low` / `Info`. |
| `title` | Verbatim issue title. |
| `description` | Verbatim issue body. |
| `source_url` | Best-effort upstream link (deterministic for code4rena; may be empty for others). |
| `domain` | Always the input `--domain`. |
| `scraped_at` | ISO 8601 UTC. |

## What this PR does NOT include (follow-ups)

- A scheduled scrape → publish loop. Cadence is intentionally manual.
- Migration of `expanded_pattern_search.py`, `find_precedents_and_bugs.py`,
  `filter_similar_audits.py` to the HF loader. Only `match_similar_findings.py`
  is migrated as a proof point.
- HF revision tagging per scrape. We push to `main` only for now; bring
  back per-date revisions once the corpus is large enough that consumers
  benefit from pinning.
- Removal of the bulky CSVs in `csv/` from git history. That's a separate
  history-rewrite issue once this loop has shipped at least one release.

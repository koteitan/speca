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

`csv/` is no longer in the repo — the canonical store is HF. Run
scrapers first to populate `benchmarks/data/defi_audit_reports/`:

```bash
# 0. Scrape (one-time per refresh; writes header-only stubs into
#    real corpora). Skip if the runner already has scrape output.
uv run python3 scripts/scrape_code4rena.py
uv run python3 scripts/scrape_sherlock.py
uv run python3 scripts/scrape_codehawks.py

# 1. Build a parquet from the scraper output.
#    --source can be repeated to union multiple CSVs.
uv run --group datasets python3 scripts/datasets/build_derived.py \
  --domain defi \
  --source benchmarks/data/defi_audit_reports/code4rena_all_issues.csv \
  --source benchmarks/data/defi_audit_reports/sherlock_all_issues.csv \
  --source benchmarks/data/defi_audit_reports/codehawks_all_issues.csv \
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
| `source` | Comma-separated CSV paths; all are unioned into the same parquet. Default points at the three scraper-output paths under `benchmarks/data/defi_audit_reports/` — populate them locally before dispatching. |
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

## Adding a new domain config

The dataset is multi-config: `defi/train.parquet`, `lending/train.parquet`,
`oracle/train.parquet`, …. To add one:

1. Get a CSV (or multiple) for the domain into a runner-accessible path.
   The schema must include at least `source` (or `source_platform`),
   `severity`, `title`, and either `description` or `description_excerpt`.
   `contest` and `issue_id` are recommended for stable IDs.
2. Dispatch `Publish dataset to HuggingFace` with `domain=<your-slug>`
   and `source=<csv-path>`. Slug must match `[a-z0-9]+(-[a-z0-9]+)*`.
3. The publisher uses `delete_patterns=["<domain>/*"]`, so it only
   touches that domain's folder; existing configs (`defi`, etc.) are
   untouched. The repo-root `README.md` is regenerated each push but
   the content is global, so it's idempotent across domains.
4. After the first push, HF auto-detects the new folder as a config —
   `load_dataset(repo, "<your-slug>", split="train")` will work without
   any further setup.

## Known limitations / follow-ups

- **No scheduled scrape → publish loop.** Operators run `scripts/scrape_*.py`
  locally (or on the runner) and dispatch the publish workflow manually.
  Auto-scheduled refresh is a separate, not-yet-implemented step.
- **Three CSV consumers still read local files** — `expanded_pattern_search.py`,
  `find_precedents_and_bugs.py`, `filter_similar_audits.py`. Only
  `match_similar_findings.py` was migrated to the HF loader; the others
  point at scraper output paths under `benchmarks/data/defi_audit_reports/`.
  Migrating them is a small follow-up PR.
- **No HF revisions per scrape.** We push to `main` only. If/when the
  corpus stabilizes and consumers want to pin a snapshot, switch to
  per-date revisions in `publish_hf.push()`.
- **`csv/` is gone.** The historical CSVs were folded into the HF
  `defi` config and removed from the working tree (gitignored). They
  still exist in git history; the `git filter-repo` clone-shrink chore
  is a separate ticket.

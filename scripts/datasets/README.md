# `scripts/datasets/` — SPECA → HuggingFace pipeline

Builds the [`NyxFoundation/vulnerability-reports`](https://huggingface.co/datasets/NyxFoundation/vulnerability-reports)
audit-finding dataset on HuggingFace. Multi-config repo (one config per
security domain — currently `defi` from Code4rena + Sherlock + CodeHawks,
with `ethereum` past-fix coverage of the 11 in-scope clients in flight
per [issue #2](https://github.com/NyxFoundation/speca/issues/2)).

## Operator guide

For the full end-to-end flow (when to dispatch, what inputs to pass,
how to verify), see the documentation site:

→ **[Refreshing the audit-finding dataset](https://speca.pages.dev/docs/operations/dataset-refresh)**

## Files

| Path | Role |
|---|---|
| [`build_derived.py`](build_derived.py) | Read CSV(s) → unified parquet + `manifest.json` under `dist/datasets/<domain>/`. Layout mirrors the HF target: `<domain>/train.parquet`. |
| [`blame_walk.py`](blame_walk.py) | Enrich `introduced_in_commit` in an existing ethereum parquet by resolving each row's fix event to a vulnerable-state commit (parent of the fix). See [Blame-walk step](#blame-walk-step) below. |
| [`publish_hf.py`](publish_hf.py) | Render the global dataset card from `templates/README.md.j2`, stage `<domain>/{train.parquet,manifest.json}` + `README.md`, then `upload_folder` with `delete_patterns=["<domain>/*"]` so other configs survive. `--dry-run` skips network. |
| [`load.py`](load.py) | Single helper consumers should call: `load_findings(domain="defi")` returns a pandas DataFrame, defaulting to HF, with a `local_parquet=` override for offline / dev. |
| [`templates/README.md.j2`](templates/README.md.j2) | Jinja template for the global HF dataset card (schema + provenance only — per-domain build state lives in `<domain>/manifest.json`). |

## Install

```bash
uv sync --group datasets
```

## Local end-to-end (dry-run, no HF push)

```bash
# 0. (Re-)scrape into benchmarks/data/defi_audit_reports/
uv run python3 scripts/scrape_code4rena.py
uv run python3 scripts/scrape_sherlock.py
uv run python3 scripts/scrape_codehawks.py

# 1. Build a parquet from scraper output (multi-source unioned).
uv run --group datasets python3 scripts/datasets/build_derived.py \
  --domain defi \
  --source benchmarks/data/defi_audit_reports/code4rena_all_issues.csv \
  --source benchmarks/data/defi_audit_reports/sherlock_all_issues.csv \
  --source benchmarks/data/defi_audit_reports/codehawks_all_issues.csv \
  --out-dir dist/datasets

# 2. Render the dataset card and dry-run the upload.
uv run --group datasets python3 scripts/datasets/publish_hf.py \
  --src dist/datasets/defi --dry-run

# 3. Load it back the way consumers do:
uv run --group datasets python3 - <<'PY'
from scripts.datasets.load import load_findings
df = load_findings(domain="defi", local_parquet="dist/datasets/defi/train.parquet")
print(df.shape, df.columns.tolist())
PY
```

## Schema

| Field | Type | Description |
|---|---|---|
| `id` | str | `<platform>:<contest-slug>:<issue_id>` (hash fallback if any segment missing) |
| `source_platform` | str | defi: `code4rena` / `sherlock` / `codehawks`. ethereum: client slug (`geth`, `nethermind`, `besu`, `erigon`, `reth`, `lighthouse`, `lodestar`, `nimbus`, `prysm`, `teku`, `grandine`) |
| `contest` | str | Slugified contest (defi) or repo slug (ethereum) |
| `issue_id` | str | Platform-local issue / PR id, `#`-stripped |
| `severity` | str | `High` / `Medium` / `Low` / `Info` |
| `title`, `description` | str | Verbatim from upstream |
| `source_url` | str | Best-effort upstream link (deterministic for code4rena) |
| `introduced_in_commit` | str | Provenance commit (Phase B replay; `""` for defi) |
| `domain` | str | Matches the config name |
| `scraped_at` | str | ISO 8601 UTC |

## Blame-walk step

After `build_derived.py` produces `dist/datasets/ethereum/train.parquet`, run
`blame_walk.py` to fill in `introduced_in_commit`. The v1 semantic is
**vulnerable-state commit = parent of the fix commit** (not the true introducing
commit — that requires `git log -G` across each client repo and is deferred to a
follow-up). For Phase B replay this is sufficient: auditing the pre-fix state
asks "would the prompt catch this bug in the broken codebase?" `blame_walk.py`
writes the enriched parquet in-place and emits a manifest at
`dist/datasets/ethereum/blame_walk_manifest.json`.

```bash
uv run --group datasets python3 -m scripts.datasets.blame_walk \
    --in  dist/datasets/ethereum/train.parquet \
    --out dist/datasets/ethereum/train.parquet \
    --manifest dist/datasets/ethereum/blame_walk_manifest.json
```

**Per-source coverage matrix (v1):**

| Source prefix | Resolution strategy | v1 coverage |
|---|---|---|
| `PR#<n>` | Merge commit's first parent | Resolvable |
| `RELEASE#<tag>#<hex>` | Tag commit's first parent (annotated tags dereffed) | Resolvable |
| `COMMIT#<12hex>` | Commit's first parent (full SHA preferred from source_url) | Resolvable |
| `GHSA-*` | Advisory's `patched_versions` → tag → first parent | Resolvable |
| `ISSUE#<n>` | No canonical fix commit in schema | Always `""` (TODO) |
| `CHANGELOG#<hex>` | No version anchor in unified schema | Always `""` (TODO) |

Expected overall coverage depends on the mix of source types in the parquet.
Rows from the PR, RELEASE, COMMIT, and GHSA crawlers are fully resolvable;
ISSUE and CHANGELOG rows remain empty until a follow-up enricher lands.

## Adding a new domain (worked example: `ethereum`)

The pipeline is domain-agnostic — `--domain ethereum` already works as
soon as a CSV exists. Two operator-facing knobs need different values
than the defi defaults:

1. **`--source`** must point at the ethereum past-fix crawler output
   under `benchmarks/data/ethereum_past_fixes/`. The CSV must include
   `source, contest, issue_id, severity, title, description, source_url,
   introduced_in_commit`. `source` is the client slug (one of the 11
   above).
2. **`--filter-platforms ''`** (empty) disables the platform allow-list
   so the 11 client slugs aren't filtered out by the defi defaults.

Local dry-run:

```bash
uv run --group datasets python3 scripts/datasets/build_derived.py \
  --domain ethereum \
  --source benchmarks/data/ethereum_past_fixes/<crawler>.csv \
  --filter-platforms '' \
  --out-dir dist/datasets

uv run --group datasets python3 scripts/datasets/publish_hf.py \
  --src dist/datasets/ethereum --dry-run
```

When dispatching `.github/workflows/datasets-publish.yml`, set
`domain=ethereum`, swap the `source` input to the ethereum CSV path(s),
and clear `filter_platforms`. The published parquet lands at
`NyxFoundation/vulnerability-reports/ethereum/train.parquet`; the
`defi/` config is untouched (`delete_patterns` is scoped per domain).

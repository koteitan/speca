# `ethereum_past_fixes/` — past-fix corpus for issue #2 Phase A

Output directory for the GitHub crawler that builds the `ethereum`
config of `NyxFoundation/vulnerability-reports` on HuggingFace. The
crawler itself (`benchmarks/scripts/crawl_eth_past_fixes.py`) is not yet
landed; this directory reserves the path so the existing
`scripts/datasets/build_derived.py` and `.github/workflows/datasets-publish.yml`
can be dispatched against the CSVs as soon as the crawler emits them.

## Expected schema

One CSV per crawl run (or per client, unioned at build time). Columns:

| Column | Notes |
|---|---|
| `source` | Client slug — one of `geth`, `nethermind`, `besu`, `erigon`, `reth`, `lighthouse`, `lodestar`, `nimbus`, `prysm`, `teku`, `grandine`. |
| `contest` | Upstream repo slug, e.g. `ethereum/go-ethereum`. |
| `issue_id` | GitHub PR / issue / advisory id, `#`-stripped. |
| `severity` | `High` / `Medium` / `Low` / `Info` (mapped from upstream label). |
| `title` | Verbatim title. |
| `description` | Verbatim body. |
| `source_url` | GitHub URL. |
| `introduced_in_commit` | SHA of the commit that introduced the bug — used by Phase B to slice the corpus by commit-time for held-out replay. |

## Dispatch

Once a CSV lands here, a publish dry-run is one command:

```bash
uv run --group datasets python3 scripts/datasets/build_derived.py \
  --domain ethereum \
  --source benchmarks/data/ethereum_past_fixes/<crawler>.csv \
  --filter-platforms '' \
  --out-dir dist/datasets

uv run --group datasets python3 scripts/datasets/publish_hf.py \
  --src dist/datasets/ethereum --dry-run
```

CSVs in this directory are LFS-tracked
(`.gitattributes`: `benchmarks/data/ethereum_past_fixes/*.csv filter=lfs`).

---
sidebar_position: 3
---

# Distributing benchmark artifacts

The raw benchmark outputs under `benchmarks/results/` (per-target audit traces / finding labels / LLM cache, totalling 350 MB+) are not distributed via Git but bundled into **GitHub Releases**. The speca repository itself only keeps "rendered figures (`*.png`), paper tables (`*.tex`), and human-review documents (`*.md`)", and the raw data is handled via per-tag tarballs.

## Tag naming convention

```
bench-<rq>-<utc-date>-<suffix>
```

Examples:

| Tag | Contents |
|---|---|
| `bench-rq1-20260508-sherlock_ethereum_audit_contest` | Full RQ1 Sherlock outputs |
| `bench-rq2a-20260508-sonnet4` | RQ2 Claude Sonnet 4 sweep |
| `bench-rq2a-20260508-deepseek_r1` | RQ2 DeepSeek R1 sweep |
| `bench-rq2a-20260508-figures` | RQ2 figures only |
| `bench-rq2b-20260508-figures` | RQ2b figures (exploratory) |

## Download (restore)

```bash
# List
gh release list --repo NyxFoundation/speca | grep '^bench-'

# Restore
bash benchmarks/scripts/restore-results.sh bench-rq2a-20260508-sonnet4
# → restored to benchmarks/results/rq2a/speca_sonnet4/
```

What `restore-results.sh` does:

1. `gh release download` by tag name
2. Validate the tarball against `archive_sha256` in the sidecar `<tag>.manifest.json`
3. **In-place restore to the original location** as specified by `source_path`
4. Cross-check the restored file count against the manifest

Options:

| Flag | Purpose |
|---|---|
| `--out <dir>` | Restore to a specified directory instead of the original location |
| `--force` | Delete the existing target before restoring |
| `--keep-archive` | Keep a copy of tarball + manifest at the destination (for re-uploading) |

## Publish

Normally use the GitHub Action `Publish benchmark artifacts` (`workflow_dispatch` only):

```bash
gh workflow run publish-bench-artifacts.yml -R NyxFoundation/speca \
  --ref main \
  -f subdir=rq2a/speca_sonnet4
```

Key inputs:

| input | default | description |
|---|---|---|
| `subdir` | (required) | Path directly under `benchmarks/results/`. Example: `rq2a/speca_sonnet4` |
| `tag_suffix` | (empty) | If empty, strips `speca_` from the leaf name |
| `tag_date` | (empty) | YYYYMMDD UTC; today if empty |
| `notes` | (empty) | markdown to append to release notes |
| `ref` | (empty) | git ref to check out |

The workflow:

1. Generates `<tag>.tar.zst` + `<tag>.manifest.json` via `benchmarks/scripts/publish-results.sh`
2. zstd compression + sha256 computation + file count recording
3. `gh release create` as a pre-release (for an existing tag, `--clobber` overwrites and regenerates notes)

## Publishing locally

When the data is already on a self-hosted runner:

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

## Required tools

`tar --zstd` (GNU tar 1.31+; on macOS install via `brew install gnu-tar` and use `gtar`, or bsdtar 3.5+), `zstd`, `jq`, `python3`, `gh`.

## `.gitignore` behavior

`benchmarks/results/**` is ignored, but `*.png` / `*.tex` / `*.md` are **allowlisted**. Only figures and review documents are tracked in git, while raw trace files (`*.json` / `*.jsonl` / `*.csv`) are obtained via Releases. If you want to commit a new kind of documentation artifact, extend the allowlist on the `.gitignore` side (rather than using `git add -f`).

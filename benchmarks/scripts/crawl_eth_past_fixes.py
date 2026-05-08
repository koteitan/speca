#!/usr/bin/env python3
"""Crawl past security fixes from the 11 in-scope Ethereum clients into a
CSV that round-trips through `scripts/datasets/build_derived.py`.

Sources (v1 vertical slice — geth):
    - GitHub Security Advisories (GHSA): the cleanest data source —
      structured, severity-labeled, deduplicated by upstream. Pulled via
      `gh api repos/<repo>/security-advisories`.

Out of scope for v1 (tracked as TODOs, planned for follow-up slices):
    - Security-relevant PRs / issues that never got a GHSA filed.
    - CHANGELOG / audit-report mining.
    - `introduced_in_commit` blame-walk (defaults to "" — Phase B replay
      can fall back to the advisory's `published_at` minus a fixed
      window until the blame walk lands).

Why `gh` subprocess instead of `requests`?  The repo's other scrapers
(`scripts/scrape_*.py`) all shell out to `gh`. Reusing the same auth
(`gh auth login`) avoids a parallel `GITHUB_TOKEN` env-var dance.

Output layout (mirrors `defi_audit_reports/`):
    benchmarks/data/ethereum_past_fixes/<client>.csv
    benchmarks/data/ethereum_past_fixes/<client>.crawl_manifest.json

The CSV columns match what `scripts/datasets/build_derived.py` already
accepts (issue #2 schema):
    source, contest, issue_id, severity, title, description,
    source_url, introduced_in_commit

Usage:
    # Crawl one client (geth is the v1 vertical):
    uv run python3 benchmarks/scripts/crawl_eth_past_fixes.py \\
        --client geth --out-dir benchmarks/data/ethereum_past_fixes

    # Crawl every in-scope client (skip on a 404 — the per-client gh
    # output writes alongside, so re-run is idempotent):
    uv run python3 benchmarks/scripts/crawl_eth_past_fixes.py \\
        --client all --out-dir benchmarks/data/ethereum_past_fixes
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Ethereum bug-bounty in-scope clients (issue #2). Repo slugs are the
# canonical upstream — re-verify against ethereum.org/bug-bounty at the
# start of Phase C in case the program list shifts.
CLIENT_CONFIG: dict[str, dict] = {
    "geth":       {"repo": "ethereum/go-ethereum"},
    "nethermind": {"repo": "NethermindEth/nethermind"},
    "besu":       {"repo": "hyperledger/besu"},
    "erigon":     {"repo": "erigontech/erigon"},
    "reth":       {"repo": "paradigmxyz/reth"},
    "lighthouse": {"repo": "sigp/lighthouse"},
    "lodestar":   {"repo": "ChainSafe/lodestar"},
    "nimbus":     {"repo": "status-im/nimbus-eth2"},
    "prysm":      {"repo": "prysmaticlabs/prysm"},
    "teku":       {"repo": "Consensys/teku"},
    "grandine":   {"repo": "grandinetech/grandine"},
}

# GHSA `severity` is one of low/medium/high/critical. Map onto the
# unified schema's `severity` (High/Medium/Low/Info). `critical`
# collapses to `High` because the downstream parquet's enum doesn't
# distinguish — the CVSS score on the advisory itself is preserved via
# `description`, so no information is lost.
SEVERITY_MAP = {
    "critical": "High",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

# Per-page when listing advisories. The list-repository-security-advisories
# endpoint uses CURSOR pagination (before/after), not page numbers — so we
# rely on `gh api --paginate` to walk the Link header for us instead of
# rolling our own page loop.
ADVISORIES_PER_PAGE = 100

CSV_FIELDS = (
    "source", "contest", "issue_id", "severity", "title",
    "description", "source_url", "introduced_in_commit",
)


def gh_json(args: list[str], timeout: int = 120):
    """Run `gh` and return parsed JSON, or None on error.

    Mirrors the shape used by `scripts/scrape_code4rena.py` so the
    failure modes (and how they're logged) match the repo's existing
    scrapers."""
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  [warn] gh failed: {e}", file=sys.stderr)
        return None
    if result.returncode != 0:
        # 404 on security-advisories means the repo has none published —
        # surfaced loudly to operators since the alternative would be a
        # silently-empty CSV.
        msg = (result.stderr or "").strip()[:300]
        print(f"  [warn] gh exit {result.returncode}: {msg}", file=sys.stderr)
        return None
    body = result.stdout.strip()
    if not body:
        return []
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        print(f"  [warn] gh output not JSON: {e}", file=sys.stderr)
        return None


def fetch_advisories(repo: str) -> list[dict]:
    """List published GHSA advisories on `<owner>/<repo>`. `gh api
    --paginate` walks the Link-header cursor automatically — works
    whether the upstream uses page numbers or before/after cursors
    (GHSA's endpoint is the latter)."""
    chunk = gh_json([
        "api", f"repos/{repo}/security-advisories",
        "--paginate",
        "-f", f"per_page={ADVISORIES_PER_PAGE}",
        "-f", "state=published",
    ])
    return chunk if isinstance(chunk, list) else []


def normalize_severity(advisory: dict) -> str:
    raw = (advisory.get("severity") or "").strip().lower()
    return SEVERITY_MAP.get(raw, "Info")


def advisory_to_row(advisory: dict, client_slug: str, repo: str) -> dict | None:
    """Project one GHSA advisory onto the build_derived CSV schema.

    Returns None if the advisory is too sparse to keep — e.g. a
    placeholder draft where summary + description are both blank."""
    ghsa_id = (advisory.get("ghsa_id") or "").strip()
    summary = (advisory.get("summary") or "").strip()
    description = (advisory.get("description") or "").strip()

    if not (summary or description):
        return None
    if not ghsa_id:
        # No id → no stable record key. Skip rather than synthesize one,
        # so build_derived doesn't dedupe genuinely-distinct advisories
        # by collision on a hash fallback.
        return None

    return {
        "source": client_slug,
        "contest": repo,
        "issue_id": ghsa_id,
        "severity": normalize_severity(advisory),
        "title": summary,
        "description": description,
        "source_url": (advisory.get("html_url") or "").strip(),
        # TODO(phase-b-replay): walk the advisory's `vulnerabilities[].patched_versions`
        # back to the introducing commit via `git log -G` on patched
        # files. Empty for v1 — Phase B's per-client time slicer can
        # fall back to advisory.published_at - 90 days as a coarse
        # bucket until this lands.
        "introduced_in_commit": "",
    }


def crawl_client(
    client_slug: str,
    *,
    max_records: int | None = None,
    fetcher=fetch_advisories,
) -> list[dict]:
    """Crawl one in-scope client. `fetcher` is injectable so tests can
    stub the GitHub round-trip without monkeypatching subprocess."""
    if client_slug not in CLIENT_CONFIG:
        sys.exit(f"unknown client {client_slug!r}; known: {sorted(CLIENT_CONFIG)}")
    repo = CLIENT_CONFIG[client_slug]["repo"]

    advisories = fetcher(repo)
    rows: list[dict] = []
    for adv in advisories:
        row = advisory_to_row(adv, client_slug, repo)
        if row is None:
            continue
        rows.append(row)
        if max_records and len(rows) >= max_records:
            break
    return rows


def write_csv(rows: Iterable[dict], out_path: Path) -> int:
    """Write rows to `out_path` in the canonical column order. Returns
    the row count (excluding header)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})
            n += 1
    return n


def write_manifest(
    out_path: Path,
    *,
    client_slug: str,
    repo: str,
    n_rows: int,
    sources: list[str],
) -> None:
    """Provenance snapshot — when the crawl ran, what gh version, what
    sources were tapped. Lives next to the CSV so a re-run is auditable."""
    gh_version = ""
    try:
        v = subprocess.run(
            ["gh", "--version"], capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        if v.returncode == 0:
            gh_version = v.stdout.strip().splitlines()[0]
    except Exception:
        pass

    manifest = {
        "client": client_slug,
        "repo": repo,
        "n_rows": n_rows,
        "sources": sources,
        "crawled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gh_version": gh_version,
    }
    out_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def crawl_and_write(client_slug: str, out_dir: Path, *, max_records: int | None = None) -> int:
    """Top-level: crawl, write CSV + manifest, return row count."""
    repo = CLIENT_CONFIG[client_slug]["repo"]
    print(f"[{client_slug}] crawling advisories on {repo}...", file=sys.stderr)
    rows = crawl_client(client_slug, max_records=max_records)
    csv_path = out_dir / f"{client_slug}.csv"
    manifest_path = out_dir / f"{client_slug}.crawl_manifest.json"
    n = write_csv(rows, csv_path)
    write_manifest(
        manifest_path,
        client_slug=client_slug,
        repo=repo,
        n_rows=n,
        sources=[f"https://github.com/{repo}/security/advisories"],
    )
    print(f"[{client_slug}] wrote {n} rows -> {csv_path}", file=sys.stderr)
    return n


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--client", required=True,
        help="Client slug (one of: " + ", ".join(sorted(CLIENT_CONFIG))
             + ") or 'all' for the full set.",
    )
    p.add_argument(
        "--out-dir", default="benchmarks/data/ethereum_past_fixes",
        help="Output directory for <client>.csv + <client>.crawl_manifest.json.",
    )
    p.add_argument(
        "--max-records", type=int, default=0,
        help="Cap rows per client (0 = no cap, useful for smoke tests).",
    )
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    if args.client == "all":
        clients = sorted(CLIENT_CONFIG)
    else:
        if args.client not in CLIENT_CONFIG:
            sys.exit(f"unknown --client {args.client!r}; pass 'all' or one of: {sorted(CLIENT_CONFIG)}")
        clients = [args.client]

    cap = args.max_records or None
    total = 0
    for c in clients:
        total += crawl_and_write(c, out_dir, max_records=cap)
    print(f"done — {total} rows across {len(clients)} client(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

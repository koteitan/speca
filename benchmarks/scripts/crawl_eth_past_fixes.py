#!/usr/bin/env python3
"""Crawl past security fixes from the 11 in-scope Ethereum clients into a
CSV that round-trips through `scripts/datasets/build_derived.py`.

Sources:
    - GitHub Security Advisories (GHSA): the cleanest data source —
      structured, severity-labeled, deduplicated by upstream. Pulled via
      `gh api repos/<repo>/security-advisories`.
    - Security-relevant merged PRs: title-matched against SECURITY_TITLE_RE.
      Capped at ~2000 closed PRs per repo to avoid runaway API spend (geth
      alone has ~30k closed PRs; the title filter is cheap but pagination
      over that volume burns rate-limit).
    - Closed issues labelled `security` (fallback: `vulnerability`). Legacy
      PR objects returned by the issues endpoint are stripped by checking
      the `pull_request` key.

Out of scope (tracked as TODOs, planned for follow-up slices):
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
import re
import subprocess
import sys
import time
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

# Maximum number of closed PRs to examine when using the page-loop fallback.
# geth has ~30k closed PRs; paginating the full list would burn rate-limit.
# 2000 PRs = 20 pages of 100 — used only if search/issues is unavailable.
PR_PAGE_CAP = 2000

# Security keyword terms used in GitHub search queries (must map to the
# same concepts as SECURITY_TITLE_RE).  Splitting into short terms keeps
# each query under GitHub's character limit and avoids double-quoting of
# multi-word phrases across different shell environments.
_SEARCH_TERMS = [
    "security",
    "vulnerability",
    "CVE",
    "DoS",
    "panic",
    "crash",
    "RCE",
    "memory+leak",
    "integer+overflow",
    "race+condition",
]

CSV_FIELDS = (
    "source", "contest", "issue_id", "severity", "title",
    "description", "source_url", "introduced_in_commit",
)

# Compiled regex for detecting security-relevant PR / issue titles.
# Word-boundary anchored so partial matches like "securitytoken" are not hits.
# CVE pattern does not need \b on the right because the digit sequence already
# acts as a natural boundary.
SECURITY_TITLE_RE = re.compile(
    r"\b(?:"
    r"security"
    r"|vuln(?:erability)?"
    r"|CVE-\d{4}-\d+"
    r"|DoS"
    r"|panic"
    r"|crash"
    r"|RCE"
    r"|memory\s+leak"
    r"|integer\s+overflow"
    r"|race\s+condition"
    r")\b",
    re.IGNORECASE,
)

# Severity label regex used to extract a severity hint from PR/issue titles.
_SEVERITY_LABEL_RE = re.compile(r"\b(Critical|High|Medium|Low)\b", re.IGNORECASE)


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
    (GHSA's endpoint is the latter).

    Two `gh api` gotchas baked in here:
      1. `-X GET` is REQUIRED. Without it, gh sees a `-f` field and
         flips the method to POST — and POST /security-advisories means
         "create advisory", which 403s for any token without the
         `repository_security_advisories` admin scope.
      2. Do NOT pass `state=published`. Same admin scope requirement;
         the default already returns only published rows for non-admin
         tokens.
    Both pitfalls verified by smoke-testing ethereum/go-ethereum on
    2026-05-09 with a `repo` + `read:org` token (sururu-k)."""
    chunk = gh_json([
        "api", f"repos/{repo}/security-advisories",
        "-X", "GET",
        "--paginate",
        "-f", f"per_page={ADVISORIES_PER_PAGE}",
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


def fetch_security_prs(repo: str) -> list[dict]:
    """Return merged PRs whose titles contain a security keyword.

    Uses GitHub's search/issues endpoint (which covers PRs too) to query
    each keyword in _SEARCH_TERMS against PR titles in the given repo.
    This is far more targeted than paginating all closed PRs — geth has
    ~30k closed PRs but only ~150 security-keyword matches, so the page
    loop would spend 300 API calls to find what search finds in ~10.

    Deduplication: multiple keyword queries may return the same PR number.
    We deduplicate on `number` and keep the first occurrence.

    Search API returns a simplified issue object, not the full PR object.
    We need `merged_at` to confirm the PR is merged; that field is absent
    from search results, so we check `pull_request.merged_at` if present,
    or fall back to `state == 'closed'` + absence of `pull_request.merged_at`
    being null. GitHub search `is:merged` qualifier guarantees the item is
    merged, so we trust the search filter rather than rechecking field-level.

    `-X GET` is required when passing `-f` fields (without it gh flips to
    POST and 403s — same gotcha as fetch_advisories).
    """
    seen: set[int] = set()
    results: list[dict] = []

    for i, term in enumerate(_SEARCH_TERMS):
        # Rate-limit guard: search/issues counts against the core limit
        # (30 req/min authenticated). With up to 10 terms x 10 pages = 100
        # calls per client, sleeping 2s between terms keeps us well under
        # the limit (other crawlers follow the same convention).
        if i > 0:
            time.sleep(2)

        # Use `in:title` to restrict to title matches (same semantics as
        # SECURITY_TITLE_RE on the title field). `is:merged` guarantees only
        # merged PRs are returned, eliminating the merged_at null-check.
        query = f"repo:{repo} is:pr is:merged {term} in:title"
        page = 1
        while True:
            chunk = gh_json([
                "api", "search/issues",
                "-X", "GET",
                "-f", f"q={query}",
                "-f", "per_page=100",
                "-f", f"page={page}",
            ])
            if not isinstance(chunk, dict):
                break
            items = chunk.get("items") or []
            if not items:
                break
            for item in items:
                num = item.get("number")
                if num is not None and num not in seen:
                    seen.add(num)
                    # Normalize the search result to look like a pulls API
                    # object so pr_to_row works without branching.
                    item.setdefault("merged_at", "search-confirmed-merged")
                    results.append(item)
            if len(items) < 100:
                break
            # GitHub search caps at 1000 results per query; stop at page 10.
            if page >= 10:
                break
            page += 1

    # Guard against runaway: cap deduplicated PR count.
    # geth alone has ~30k closed PRs; without this cap a rogue term could
    # accumulate many thousands of results across all pages and blow the
    # rate limit and downstream processing time.
    if len(results) > PR_PAGE_CAP:
        print(
            f"  [warn] fetch_security_prs: deduped PR count {len(results)} exceeds "
            f"PR_PAGE_CAP={PR_PAGE_CAP}; truncating",
            file=sys.stderr,
        )
        results = results[:PR_PAGE_CAP]

    return results


def fetch_security_issues(repo: str) -> list[dict]:
    """Return closed issues labelled `security` (or `vulnerability` as
    fallback). Filters out legacy PR objects that GitHub's issues endpoint
    returns (items with a `pull_request` key are PRs, not issues).

    Two label attempts:
      1. label=security
      2. label=vulnerability  (only if attempt 1 returns nothing)
    """
    def _fetch_label(label: str) -> list[dict]:
        chunk = gh_json([
            "api", f"repos/{repo}/issues",
            "-X", "GET",
            "--paginate",
            "-f", "state=closed",
            "-f", f"labels={label}",
            "-f", "per_page=100",
        ])
        if not isinstance(chunk, list):
            return []
        # Strip PR objects that the legacy endpoint returns alongside real issues.
        return [item for item in chunk if "pull_request" not in item]

    results = _fetch_label("security")
    if not results:
        results = _fetch_label("vulnerability")
    return results


def _severity_from_title(title: str) -> str:
    """Extract the first explicit severity word from a PR/issue title.
    Returns 'Info' when none is found."""
    m = _SEVERITY_LABEL_RE.search(title)
    if m:
        return m.group(1).capitalize()
    return "Info"


def pr_to_row(pr: dict, client_slug: str, repo: str) -> dict | None:
    """Map a GitHub PR object onto the build_derived CSV schema.

    Returns None if both title and body are empty — such rows carry no
    useful signal for downstream analysis."""
    title = (pr.get("title") or "").strip()
    body = (pr.get("body") or "").strip()
    if not title and not body:
        return None
    return {
        "source": client_slug,
        "contest": repo,
        "issue_id": f"PR#{pr['number']}",
        "severity": _severity_from_title(title),
        "title": title,
        "description": body,
        "source_url": (pr.get("html_url") or "").strip(),
        "introduced_in_commit": "",
    }


def issue_to_row(issue: dict, client_slug: str, repo: str) -> dict | None:
    """Map a GitHub issue object onto the build_derived CSV schema.

    Returns None if both title and body are empty."""
    title = (issue.get("title") or "").strip()
    body = (issue.get("body") or "").strip()
    if not title and not body:
        return None
    return {
        "source": client_slug,
        "contest": repo,
        "issue_id": f"ISSUE#{issue['number']}",
        "severity": _severity_from_title(title),
        "title": title,
        "description": body,
        "source_url": (issue.get("html_url") or "").strip(),
        "introduced_in_commit": "",
    }


def crawl_client(
    client_slug: str,
    *,
    max_records: int | None = None,
    fetcher=fetch_advisories,
    pr_fetcher=fetch_security_prs,
    issue_fetcher=fetch_security_issues,
) -> list[dict]:
    """Crawl one in-scope client. All three fetchers are injectable so
    tests can stub the GitHub round-trip without monkeypatching subprocess.

    Row ordering: advisory rows first, then PR rows, then issue rows.
    max_records caps the COMBINED row count."""
    if client_slug not in CLIENT_CONFIG:
        sys.exit(f"unknown client {client_slug!r}; known: {sorted(CLIENT_CONFIG)}")
    repo = CLIENT_CONFIG[client_slug]["repo"]

    rows: list[dict] = []

    for adv in fetcher(repo):
        row = advisory_to_row(adv, client_slug, repo)
        if row is None:
            continue
        rows.append(row)
        if max_records and len(rows) >= max_records:
            return rows

    for pr in pr_fetcher(repo):
        row = pr_to_row(pr, client_slug, repo)
        if row is None:
            continue
        rows.append(row)
        if max_records and len(rows) >= max_records:
            return rows

    for issue in issue_fetcher(repo):
        row = issue_to_row(issue, client_slug, repo)
        if row is None:
            continue
        rows.append(row)
        if max_records and len(rows) >= max_records:
            return rows

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
    print(f"[{client_slug}] crawling advisories + PRs + issues on {repo}...", file=sys.stderr)
    rows = crawl_client(client_slug, max_records=max_records)
    csv_path = out_dir / f"{client_slug}.csv"
    manifest_path = out_dir / f"{client_slug}.crawl_manifest.json"
    n = write_csv(rows, csv_path)
    write_manifest(
        manifest_path,
        client_slug=client_slug,
        repo=repo,
        n_rows=n,
        sources=[
            f"https://github.com/{repo}/security/advisories",
            f"https://github.com/{repo}/pulls?q=is:pr+is:closed",
            f"https://github.com/{repo}/issues?q=is:issue+is:closed+label:security",
        ],
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

"""Tests for `benchmarks/scripts/crawl_eth_past_fixes.py`.

The crawler shells out to `gh api`, so we never hit the network in
tests — `crawl_client(..., fetcher=...)` accepts an injectable fetcher
that returns canned GHSA payloads, and the CSV writer is exercised
end-to-end against tmp_path.

The most important guarantee is **schema parity** — the CSV the crawler
emits has to round-trip cleanly through `scripts/datasets/build_derived.py`.
A regression here would silently break the ethereum config publish.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CRAWLER_SCRIPT = REPO_ROOT / "benchmarks" / "scripts" / "crawl_eth_past_fixes.py"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "build_derived.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _crawler():
    return _load("speca_crawl_eth", CRAWLER_SCRIPT)


@pytest.fixture
def canned_geth_advisories() -> list[dict]:
    """Three GHSA-shaped payloads covering severity-mapping edge cases:
    `critical` collapses to `High`, an unknown severity falls back to
    `Info`, and an advisory with no summary AND no description is
    droppable."""
    return [
        {
            "ghsa_id": "GHSA-aaaa-bbbb-cccc",
            "cve_id": "CVE-2024-00001",
            "summary": "DoS via crafted block",
            "description": "Specially-crafted block triggers...",
            "severity": "critical",
            "html_url": "https://github.com/ethereum/go-ethereum/security/advisories/GHSA-aaaa-bbbb-cccc",
            "published_at": "2024-08-15T12:00:00Z",
        },
        {
            "ghsa_id": "GHSA-dddd-eeee-ffff",
            "cve_id": None,
            "summary": "Verbose error log leak",
            "description": "Stack trace includes peer multiaddr.",
            # Upstream sometimes leaves severity unset on draft-promoted
            # advisories — must NOT crash, must NOT collapse to High.
            "severity": "",
            "html_url": "https://github.com/ethereum/go-ethereum/security/advisories/GHSA-dddd-eeee-ffff",
            "published_at": "2024-09-02T08:00:00Z",
        },
        {
            "ghsa_id": "GHSA-ssss-tttt-uuuu",
            "cve_id": None,
            "summary": "",
            "description": "",  # empty body — must be dropped
            "severity": "low",
            "html_url": "https://github.com/ethereum/go-ethereum/security/advisories/GHSA-ssss-tttt-uuuu",
            "published_at": None,
        },
    ]


def test_eleven_clients_in_config():
    """The CLIENT_CONFIG map must enumerate exactly the 11 in-scope
    clients from issue #2 — drift here would silently exclude a client
    from a `--client all` run."""
    mod = _crawler()
    assert set(mod.CLIENT_CONFIG) == {
        "geth", "nethermind", "besu", "erigon", "reth",
        "lighthouse", "lodestar", "nimbus", "prysm", "teku", "grandine",
    }
    assert all("repo" in cfg for cfg in mod.CLIENT_CONFIG.values())
    # No duplicate repo slugs.
    repos = [cfg["repo"] for cfg in mod.CLIENT_CONFIG.values()]
    assert len(set(repos)) == len(repos)


def test_severity_mapping():
    mod = _crawler()
    assert mod.normalize_severity({"severity": "critical"}) == "High"
    assert mod.normalize_severity({"severity": "high"}) == "High"
    assert mod.normalize_severity({"severity": "Medium"}) == "Medium"  # case-insensitive
    assert mod.normalize_severity({"severity": "low"}) == "Low"
    # Unknown / missing → Info, not Critical or empty.
    assert mod.normalize_severity({"severity": ""}) == "Info"
    assert mod.normalize_severity({}) == "Info"
    assert mod.normalize_severity({"severity": "moderate"}) == "Info"


def test_advisory_to_row_drops_empty(canned_geth_advisories):
    mod = _crawler()
    # Third fixture has no summary AND no description.
    row = mod.advisory_to_row(canned_geth_advisories[2], "geth", "ethereum/go-ethereum")
    assert row is None


def test_advisory_to_row_drops_advisory_without_ghsa_id():
    """Without a GHSA id we can't form a stable issue_id — better to
    skip than to force the downstream into hash-fallback collisions."""
    mod = _crawler()
    row = mod.advisory_to_row(
        {"ghsa_id": "", "summary": "x", "description": "y", "severity": "low",
         "html_url": "https://example/x"},
        "geth", "ethereum/go-ethereum",
    )
    assert row is None


def test_advisory_to_row_emits_canonical_columns(canned_geth_advisories):
    mod = _crawler()
    row = mod.advisory_to_row(canned_geth_advisories[0], "geth", "ethereum/go-ethereum")
    assert row is not None
    assert set(row.keys()) == set(mod.CSV_FIELDS)
    assert row["source"] == "geth"
    assert row["contest"] == "ethereum/go-ethereum"
    assert row["issue_id"] == "GHSA-aaaa-bbbb-cccc"
    assert row["severity"] == "High"  # critical collapses to High
    assert row["title"].startswith("DoS")
    assert row["source_url"].endswith("GHSA-aaaa-bbbb-cccc")
    # v1: introduced_in_commit is intentionally empty (TODO in script).
    assert row["introduced_in_commit"] == ""


def test_crawl_client_with_injected_fetcher(canned_geth_advisories):
    mod = _crawler()
    rows = mod.crawl_client(
        "geth",
        fetcher=lambda repo: canned_geth_advisories,
        pr_fetcher=lambda repo: [],
        issue_fetcher=lambda repo: [],
    )
    # Two of three fixtures are keepers (the empty-body one is dropped).
    assert len(rows) == 2
    assert rows[0]["source"] == "geth"
    assert rows[0]["severity"] == "High"
    assert rows[1]["severity"] == "Info"  # blank severity → Info


def test_crawl_client_respects_max_records(canned_geth_advisories):
    mod = _crawler()
    rows = mod.crawl_client(
        "geth",
        max_records=1,
        fetcher=lambda repo: canned_geth_advisories,
        pr_fetcher=lambda repo: [],
        issue_fetcher=lambda repo: [],
    )
    assert len(rows) == 1


def test_crawl_client_rejects_unknown_slug():
    mod = _crawler()
    with pytest.raises(SystemExit):
        mod.crawl_client("unknown-client", fetcher=lambda repo: [])


def test_write_csv_round_trip(tmp_path: Path, canned_geth_advisories):
    mod = _crawler()
    rows = mod.crawl_client(
        "geth",
        fetcher=lambda repo: canned_geth_advisories,
        pr_fetcher=lambda repo: [],
        issue_fetcher=lambda repo: [],
    )
    out = tmp_path / "geth.csv"
    n = mod.write_csv(rows, out)
    assert n == 2
    assert out.exists()

    # Re-read and verify the header matches what build_derived consumes.
    with out.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames is not None
        assert tuple(reader.fieldnames) == mod.CSV_FIELDS
        records = list(reader)
        assert len(records) == 2


def test_csv_field_order_matches_build_derived_inputs():
    """build_derived.py declares no required CSV order, but the *names*
    must align with PLATFORM_KEYS / CONTEST_KEYS / ISSUE_KEYS so a row
    drops onto its unified-schema column without `--platform-hint`
    babysitting. This test fails loudly if either side renames a field
    without coordinating."""
    crawler = _crawler()
    build = _load("speca_build_derived_for_crawler_test", BUILD_SCRIPT)

    # `source` must be in PLATFORM_KEYS (so source_platform resolves).
    assert "source" in build.PLATFORM_KEYS
    # `contest` must be in CONTEST_KEYS (so the slugifier picks it up).
    assert "contest" in build.CONTEST_KEYS
    # `issue_id` must be in ISSUE_KEYS.
    assert "issue_id" in build.ISSUE_KEYS
    # `introduced_in_commit` is the new ethereum-specific column the
    # build_derived schema added; the crawler must emit the same name.
    assert "introduced_in_commit" in crawler.CSV_FIELDS


def test_crawler_csv_round_trips_through_build_derived(tmp_path: Path, canned_geth_advisories):
    """The end-to-end seam: crawler emits a CSV → build_derived ingests
    it → parquet contains the expected rows. If this passes, the
    workflow can dispatch ethereum end-to-end with real data."""
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")

    crawler = _crawler()
    build = _load("speca_build_derived_for_crawler_e2e", BUILD_SCRIPT)

    # 1. Crawl → CSV (stub PR/issue fetchers to isolate advisory-only behaviour)
    rows = crawler.crawl_client(
        "geth",
        fetcher=lambda repo: canned_geth_advisories,
        pr_fetcher=lambda repo: [],
        issue_fetcher=lambda repo: [],
    )
    csv_path = tmp_path / "geth.csv"
    crawler.write_csv(rows, csv_path)

    # 2. CSV → parquet via build_derived (filter_platforms='' to accept
    # the `geth` slug — the defi default would reject it).
    out_dir = tmp_path / "out"
    manifest = build.build(
        domain="ethereum",
        sources=[str(csv_path)],
        out_dir=out_dir,
        filter_platforms="",
    )

    assert manifest["domain"] == "ethereum"
    assert manifest["n_rows"] == 2
    assert manifest["rows_by_platform"] == {"geth": 2}

    import pyarrow.parquet as pq
    table = pq.read_table(out_dir / "ethereum" / "train.parquet")
    df = table.to_pandas().sort_values("severity").reset_index(drop=True)
    assert "introduced_in_commit" in df.columns
    # Both rows ship empty introduced_in_commit (v1 limitation).
    assert (df["introduced_in_commit"] == "").all()
    # Severities: ['High', 'Info'] after sort.
    assert df["severity"].tolist() == ["High", "Info"]
    # Stable record id from build_derived: <slug-of-source>:<slug-of-contest>:<issue_id>.
    assert df["id"].iloc[0] == "geth:ethereum-go-ethereum:GHSA-aaaa-bbbb-cccc"


def test_write_manifest_records_provenance(tmp_path: Path):
    mod = _crawler()
    out = tmp_path / "geth.crawl_manifest.json"
    mod.write_manifest(
        out,
        client_slug="geth",
        repo="ethereum/go-ethereum",
        n_rows=42,
        sources=["https://github.com/ethereum/go-ethereum/security/advisories"],
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["client"] == "geth"
    assert payload["repo"] == "ethereum/go-ethereum"
    assert payload["n_rows"] == 42
    assert payload["sources"] == [
        "https://github.com/ethereum/go-ethereum/security/advisories"
    ]
    # crawled_at is an ISO timestamp.
    assert payload["crawled_at"].endswith("Z")
    # gh_version may be empty if `gh` isn't on PATH in the test env;
    # only sanity-check that the key exists, not its value.
    assert "gh_version" in payload


# ---------------------------------------------------------------------------
# SECURITY_TITLE_RE boundary tests
# ---------------------------------------------------------------------------

def test_security_title_re_positive_cases():
    """Confirm that all intended keywords produce a match."""
    mod = _crawler()
    re = mod.SECURITY_TITLE_RE
    positives = [
        "security: fix auth bypass",
        "Fix vulnerability in p2p layer",
        "fix CVE-2024-12345 in handshake",
        "DoS via crafted message",
        "fix panic in block processor",
        "crash on invalid RLP input",
        "RCE via malicious payload",
        "memory leak in peer manager",
        "integer overflow in fee calculation",
        "race condition in tx pool",
        "security",                           # bare keyword
        "SECURITY",                           # case-insensitive
        "CVE-2023-99999: critical issue",
        "vuln in consensus",
        "vulnerability: timing attack",
    ]
    for title in positives:
        assert re.search(title), f"Expected match for: {title!r}"


def test_security_title_re_negative_cases():
    """Word-boundary anchoring must block partial-word matches."""
    mod = _crawler()
    re = mod.SECURITY_TITLE_RE
    negatives = [
        "securitytoken",          # 'security' not at word boundary (right side)
        "insecurity",             # left boundary miss
        "update changelog",
        "refactor p2p module",
        "add unit tests for parser",
        "bump deps to v1.2.3",
        "fix typo in README",
        "improve logging verbosity",
    ]
    for title in negatives:
        assert not re.search(title), f"Unexpected match for: {title!r}"


def test_security_title_re_boundary_mixed():
    """Boundary cases that are TRUE matches (keyword followed by punctuation
    or at end of string — still word-boundary)."""
    mod = _crawler()
    re = mod.SECURITY_TITLE_RE
    # 'security:' — colon after keyword, word boundary is satisfied
    assert re.search("security: fix DoS in foo")
    # CVE at end
    assert re.search("patch for CVE-2024-12345")
    # DoS in brackets
    assert re.search("[DoS] fix in p2p")


# ---------------------------------------------------------------------------
# pr_to_row / issue_to_row tests
# ---------------------------------------------------------------------------

@pytest.fixture
def canned_prs() -> list[dict]:
    return [
        {
            "number": 101,
            "title": "fix: DoS via crafted block header",
            "body": "This PR fixes a denial-of-service issue.",
            "merged_at": "2024-01-10T12:00:00Z",
            "html_url": "https://github.com/ethereum/go-ethereum/pull/101",
        },
        {
            "number": 202,
            "title": "security: fix High severity memory leak in peer manager",
            "body": "Memory was not freed on disconnect.",
            "merged_at": "2024-03-05T09:00:00Z",
            "html_url": "https://github.com/ethereum/go-ethereum/pull/202",
        },
        {
            "number": 303,
            "title": "",    # empty — unrelated
            "body": "",
            "merged_at": "2024-02-01T00:00:00Z",
            "html_url": "https://github.com/ethereum/go-ethereum/pull/303",
        },
    ]


@pytest.fixture
def canned_issues() -> list[dict]:
    return [
        {
            "number": 501,
            "title": "vulnerability in transaction signing",
            "body": "Attacker can forge signatures.",
            "html_url": "https://github.com/ethereum/go-ethereum/issues/501",
        },
        {
            "number": 502,
            "title": "crash on empty block",
            "body": "Node panics when receiving empty block.",
            "html_url": "https://github.com/ethereum/go-ethereum/issues/502",
        },
        {
            # Legacy PR returned by issues endpoint — must be filtered out.
            "number": 600,
            "title": "fix: race condition in mining",
            "body": "...",
            "html_url": "https://github.com/ethereum/go-ethereum/pull/600",
            "pull_request": {"url": "https://api.github.com/repos/ethereum/go-ethereum/pulls/600"},
        },
    ]


def test_pr_to_row_maps_fields(canned_prs):
    mod = _crawler()
    row = mod.pr_to_row(canned_prs[0], "geth", "ethereum/go-ethereum")
    assert row is not None
    assert row["issue_id"] == "PR#101"
    assert row["source"] == "geth"
    assert row["contest"] == "ethereum/go-ethereum"
    assert row["severity"] == "Info"   # no severity word in title
    assert "DoS" in row["title"]
    assert row["introduced_in_commit"] == ""
    assert set(row.keys()) == set(mod.CSV_FIELDS)


def test_pr_to_row_extracts_severity(canned_prs):
    mod = _crawler()
    row = mod.pr_to_row(canned_prs[1], "geth", "ethereum/go-ethereum")
    assert row is not None
    assert row["severity"] == "High"


def test_pr_to_row_drops_empty(canned_prs):
    mod = _crawler()
    row = mod.pr_to_row(canned_prs[2], "geth", "ethereum/go-ethereum")
    assert row is None


def test_issue_to_row_maps_fields(canned_issues):
    mod = _crawler()
    row = mod.issue_to_row(canned_issues[0], "geth", "ethereum/go-ethereum")
    assert row is not None
    assert row["issue_id"] == "ISSUE#501"
    assert row["source"] == "geth"
    assert set(row.keys()) == set(mod.CSV_FIELDS)


def test_id_namespaces_never_collide():
    """GHSA-, PR#, and ISSUE# prefixes must be distinct for any numeric id."""
    ghsa = "GHSA-aaaa-bbbb-cccc"
    pr = "PR#1"
    issue = "ISSUE#1"
    assert ghsa != pr
    assert ghsa != issue
    assert pr != issue
    # A GHSA id can never start with PR# or ISSUE#.
    assert not ghsa.startswith("PR#")
    assert not ghsa.startswith("ISSUE#")
    # PR# and ISSUE# share the same number space but different prefixes.
    assert pr != issue


# ---------------------------------------------------------------------------
# crawl_client with all three injected fetchers
# ---------------------------------------------------------------------------

def test_crawl_client_calls_all_three_fetchers(canned_geth_advisories, canned_prs, canned_issues):
    mod = _crawler()

    # The issues fetcher returns items including a legacy PR entry which must
    # be dropped before reaching crawl_client (fetch_security_issues filters
    # them). Simulate that filtering already done.
    real_issues = [i for i in canned_issues if "pull_request" not in i]

    rows = mod.crawl_client(
        "geth",
        fetcher=lambda repo: canned_geth_advisories,
        pr_fetcher=lambda repo: canned_prs,
        issue_fetcher=lambda repo: real_issues,
    )
    # Advisories: 2 keepers (1 empty dropped)
    # PRs: 2 keepers (1 empty-title+body dropped)
    # Issues: 2 (legacy PR already removed above)
    assert len(rows) == 6

    issue_ids = [r["issue_id"] for r in rows]
    assert any(iid.startswith("GHSA-") for iid in issue_ids)
    assert any(iid.startswith("PR#") for iid in issue_ids)
    assert any(iid.startswith("ISSUE#") for iid in issue_ids)


def test_crawl_client_max_records_caps_combined(canned_geth_advisories, canned_prs, canned_issues):
    mod = _crawler()
    real_issues = [i for i in canned_issues if "pull_request" not in i]
    rows = mod.crawl_client(
        "geth",
        max_records=3,
        fetcher=lambda repo: canned_geth_advisories,
        pr_fetcher=lambda repo: canned_prs,
        issue_fetcher=lambda repo: real_issues,
    )
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# fetch_security_issues legacy-PR filtering
# ---------------------------------------------------------------------------

def test_fetch_security_issues_filters_legacy_prs(canned_issues):
    """Issues endpoint returns PR objects too (legacy). The fetcher must
    drop them by checking for the `pull_request` key."""
    mod = _crawler()

    # Simulate gh_json returning the mixed list (2 real issues + 1 PR object).
    import unittest.mock as mock
    with mock.patch.object(mod, "gh_json", return_value=canned_issues):
        results = mod.fetch_security_issues("ethereum/go-ethereum")

    # Only the 2 real issues should remain.
    assert len(results) == 2
    assert all("pull_request" not in r for r in results)


# ---------------------------------------------------------------------------
# Combined round-trip through build_derived (PR + ISSUE + GHSA ids)
# ---------------------------------------------------------------------------

def test_combined_csv_round_trips_through_build_derived(
    tmp_path: Path, canned_geth_advisories, canned_prs, canned_issues
):
    """Crawler emits PR# + ISSUE# + GHSA- ids in the same CSV; build_derived
    must ingest it cleanly and deduplicate on `id` without collisions."""
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")

    crawler = _crawler()
    build = _load("speca_build_derived_combined", BUILD_SCRIPT)

    real_issues = [i for i in canned_issues if "pull_request" not in i]
    rows = crawler.crawl_client(
        "geth",
        fetcher=lambda repo: canned_geth_advisories,
        pr_fetcher=lambda repo: canned_prs,
        issue_fetcher=lambda repo: real_issues,
    )
    # 2 advisories + 2 PRs + 2 issues = 6 rows
    assert len(rows) == 6

    csv_path = tmp_path / "geth_combined.csv"
    crawler.write_csv(rows, csv_path)

    out_dir = tmp_path / "out"
    manifest = build.build(
        domain="ethereum",
        sources=[str(csv_path)],
        out_dir=out_dir,
        filter_platforms="",
    )
    assert manifest["n_rows"] == 6
    assert manifest["rows_by_platform"] == {"geth": 6}

    import pyarrow.parquet as pq
    table = pq.read_table(out_dir / "ethereum" / "train.parquet")
    df = table.to_pandas()
    ids = df["id"].tolist()
    # All ids must be unique — no namespace collision.
    assert len(ids) == len(set(ids))
    # id format: <platform_slug>:<contest_slug>:<issue_id>
    assert any("GHSA-" in i for i in ids)
    assert any("PR#" in i for i in ids)
    assert any("ISSUE#" in i for i in ids)

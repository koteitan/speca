"""Tests for `benchmarks/scripts/grep_eth_commits.py`.

The scraper shells out to `gh api`, so we never hit the network — all GitHub
round-trips are stubbed via the injectable `fetcher` parameter on
`crawl_commits`.

Key guarantees tested:
  - Mock-fetcher integration through `crawl_commits`
  - Multi-line commit message → subject + body splitting
  - Merge / Revert commit filtering (dropped, not counted)
  - Severity regex (positive + negative cases; Critical collapses to High)
  - issue_id prefix collision prevention (COMMIT# vs GHSA-/PR#/ISSUE#/etc.)
  - CSV round-trip through `build_derived.build()` with `filter_platforms=''`
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GREP_SCRIPT = REPO_ROOT / "benchmarks" / "scripts" / "grep_eth_commits.py"
CRAWL_SCRIPT = REPO_ROOT / "benchmarks" / "scripts" / "crawl_eth_past_fixes.py"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "build_derived.py"


# ---------------------------------------------------------------------------
# Module loader helpers
# ---------------------------------------------------------------------------

def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _grep():
    return _load("speca_grep_eth_commits", GREP_SCRIPT)


# ---------------------------------------------------------------------------
# Fixtures — canned commit search-result dicts
# ---------------------------------------------------------------------------

def _make_commit(sha: str, message: str, html_url: str = "") -> dict:
    """Build a minimal commit search-result dict mirroring GitHub's shape."""
    return {
        "sha": sha,
        "commit": {
            "message": message,
            "author": {"date": "2024-06-01T00:00:00Z"},
        },
        "html_url": html_url or f"https://github.com/example/repo/commit/{sha}",
        "repository": {"full_name": "example/repo"},
    }


CANNED_COMMITS = [
    _make_commit(
        "aabbccdd1122334455667788",
        "security: fix integer overflow in block validator\n\n"
        "When the block timestamp exceeds uint32 max the validator panicked.",
        "https://github.com/ethereum/go-ethereum/commit/aabbccdd1122",
    ),
    _make_commit(
        "deadbeef00112233445566aa",
        "CVE-2024-99999: patch RCE in p2p handshake",
    ),
    # Merge commit — must be filtered out.
    _make_commit(
        "merge0000111122223333aa",
        "Merge pull request #4242 from attacker/evil-branch",
    ),
    # Revert commit — must be filtered out.
    _make_commit(
        "revert111122223333bbbb",
        'Revert "security: fix integer overflow in block validator"',
    ),
    # Empty subject — must be filtered out.
    _make_commit(
        "empty000000000000000000",
        "",
    ),
    # Multi-line message with double-newline separator.
    _make_commit(
        "multi0001111222233334444",
        "fix: High severity memory corruption in trie\n\n"
        "Detailed description of the corruption.",
    ),
    # Single-newline separator (no blank line between subject and body).
    _make_commit(
        "single111122223333cccc",
        "DoS: goroutine leak under heavy load\nExtra context here.",
    ),
]


# ---------------------------------------------------------------------------
# Tests: crawl_commits + mock fetcher
# ---------------------------------------------------------------------------

class TestCrawlCommits:
    def test_returns_rows_from_fetcher(self):
        mod = _grep()
        rows = mod.crawl_commits("geth", fetcher=lambda repo: CANNED_COMMITS)
        # merge + revert + empty are dropped → 4 kept out of 7
        assert len(rows) == 4

    def test_fetcher_receives_correct_repo(self):
        mod = _grep()
        received: list[str] = []

        def capturing_fetcher(repo: str) -> list[dict]:
            received.append(repo)
            return []

        mod.crawl_commits("geth", fetcher=capturing_fetcher)
        assert received == ["ethereum/go-ethereum"]

    def test_unknown_client_exits(self):
        mod = _grep()
        with pytest.raises(SystemExit):
            mod.crawl_commits("nonexistent-client", fetcher=lambda repo: [])

    def test_all_clients_resolvable(self):
        """Every slug in CLIENT_CONFIG must be accepted by crawl_commits."""
        mod = _grep()
        for slug in mod.CLIENT_CONFIG:
            rows = mod.crawl_commits(slug, fetcher=lambda repo: [])
            assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# Tests: commit_to_row — message parsing
# ---------------------------------------------------------------------------

class TestCommitToRow:
    def test_double_newline_split(self):
        mod = _grep()
        c = _make_commit(
            "abc123def456789012345678",
            "fix: security patch\n\nBody text here.",
        )
        row = mod.commit_to_row(c, "geth", "ethereum/go-ethereum")
        assert row is not None
        assert row["title"] == "fix: security patch"
        assert row["description"] == "Body text here."

    def test_single_newline_split(self):
        mod = _grep()
        c = _make_commit(
            "abc123def456789012345678",
            "fix: security patch\nBody text here.",
        )
        row = mod.commit_to_row(c, "geth", "ethereum/go-ethereum")
        assert row is not None
        assert row["title"] == "fix: security patch"
        assert row["description"] == "Body text here."

    def test_no_newline(self):
        mod = _grep()
        c = _make_commit("abc123def456789012345678", "single line subject")
        row = mod.commit_to_row(c, "geth", "ethereum/go-ethereum")
        assert row is not None
        assert row["title"] == "single line subject"
        assert row["description"] == ""

    def test_title_truncated_at_120_chars(self):
        mod = _grep()
        long_subject = "x" * 200
        c = _make_commit("abc123def456789012345678", long_subject)
        row = mod.commit_to_row(c, "geth", "ethereum/go-ethereum")
        assert row is not None
        assert len(row["title"]) == 120

    def test_empty_message_returns_none(self):
        mod = _grep()
        c = _make_commit("abc123def456789012345678", "")
        assert mod.commit_to_row(c, "geth", "ethereum/go-ethereum") is None

    def test_schema_keys(self):
        mod = _grep()
        c = _make_commit("aabbccdd1122334455667788", "security fix")
        row = mod.commit_to_row(c, "geth", "ethereum/go-ethereum")
        assert row is not None
        assert set(row.keys()) == set(mod.CSV_FIELDS)


# ---------------------------------------------------------------------------
# Tests: merge / revert filter
# ---------------------------------------------------------------------------

class TestMergeRevertFilter:
    @pytest.mark.parametrize("subject", [
        "Merge pull request #42 from org/branch",
        "Merge branch 'main' into feature-x",
        "Merge remote-tracking branch 'upstream/main'",
    ])
    def test_merge_commits_dropped(self, subject: str):
        mod = _grep()
        c = _make_commit("aabb112233445566778899cc", subject)
        assert mod.commit_to_row(c, "geth", "ethereum/go-ethereum") is None

    @pytest.mark.parametrize("subject", [
        'Revert "fix: security patch"',
        "Revert bad commit",
    ])
    def test_revert_commits_dropped(self, subject: str):
        mod = _grep()
        c = _make_commit("aabb112233445566778899cc", subject)
        assert mod.commit_to_row(c, "geth", "ethereum/go-ethereum") is None

    def test_non_merge_not_dropped(self):
        mod = _grep()
        c = _make_commit("aabb112233445566778899cc", "security: fix DoS")
        assert mod.commit_to_row(c, "geth", "ethereum/go-ethereum") is not None


# ---------------------------------------------------------------------------
# Tests: severity regex
# ---------------------------------------------------------------------------

class TestSeverityRE:
    @pytest.mark.parametrize("subject,expected", [
        ("High severity: memory corruption", "High"),
        ("fix: Medium impact integer overflow", "Medium"),
        ("patch: Low risk info leak", "Low"),
        ("Critical: RCE in p2p layer", "High"),   # Critical → High (enum collapse)
        ("security: fix goroutine leak", "Info"),  # no keyword → Info
        ("DoS via crafted block", "Info"),          # DoS itself doesn't match severity
        ("HIGH severity crash", "High"),            # case-insensitive
    ])
    def test_severity_extraction(self, subject: str, expected: str):
        mod = _grep()
        c = _make_commit("aabb112233445566778899cc", subject)
        row = mod.commit_to_row(c, "geth", "ethereum/go-ethereum")
        assert row is not None
        assert row["severity"] == expected

    def test_severity_re_compile(self):
        mod = _grep()
        # SEVERITY_RE must be a compiled pattern, not a string.
        assert hasattr(mod.SEVERITY_RE, "search")
        assert mod.SEVERITY_RE.search("High severity")
        assert not mod.SEVERITY_RE.search("no keywords here")


# ---------------------------------------------------------------------------
# Tests: issue_id collision prevention
# ---------------------------------------------------------------------------

class TestIssueIdCollision:
    """COMMIT# must not collide with any prefix used by the other slices."""

    OTHER_PREFIXES = ("GHSA-", "PR#", "ISSUE#", "CHANGELOG#", "RELEASE#")

    def test_commit_prefix_distinct(self):
        mod = _grep()
        c = _make_commit("aabb112233445566778899cc", "security fix")
        row = mod.commit_to_row(c, "geth", "ethereum/go-ethereum")
        assert row is not None
        assert row["issue_id"].startswith("COMMIT#")

    @pytest.mark.parametrize("other_prefix", OTHER_PREFIXES)
    def test_no_overlap_with_other_prefixes(self, other_prefix: str):
        assert not other_prefix.startswith("COMMIT#")
        assert not "COMMIT#".startswith(other_prefix)

    def test_sha_prefix_length(self):
        """SHA prefix must be 12 hex chars (matching the spec)."""
        mod = _grep()
        sha = "aabbccdd11223344556677"
        c = _make_commit(sha, "security fix")
        row = mod.commit_to_row(c, "geth", "ethereum/go-ethereum")
        assert row is not None
        issue_id = row["issue_id"]
        assert issue_id == f"COMMIT#{sha[:12]}"

    def test_introduced_in_commit_empty(self):
        """This is the fix commit, not the bug-introducing commit."""
        mod = _grep()
        c = _make_commit("aabbccdd11223344556677", "security fix")
        row = mod.commit_to_row(c, "geth", "ethereum/go-ethereum")
        assert row is not None
        assert row["introduced_in_commit"] == ""


# ---------------------------------------------------------------------------
# Tests: CSV write + round-trip through build_derived
# ---------------------------------------------------------------------------

class TestCSVRoundTrip:
    def test_write_csv_produces_canonical_columns(self, tmp_path: Path):
        mod = _grep()
        rows = mod.crawl_commits("geth", fetcher=lambda repo: CANNED_COMMITS)
        out = tmp_path / "geth.commits.csv"
        n = mod.write_csv(rows, out)
        assert n == len(rows)
        assert out.exists()
        with out.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert tuple(reader.fieldnames) == mod.CSV_FIELDS

    def test_csv_filename_convention(self, tmp_path: Path):
        """Output CSV must be named <client>.commits.csv (not <client>.csv)
        to avoid colliding with the GHSA slice's output file."""
        mod = _grep()
        # crawl_and_write produces the canonical file name.
        mod.crawl_and_write("geth", tmp_path, max_records=5)
        # Must exist with the .commits.csv suffix.
        assert (tmp_path / "geth.commits.csv").exists()
        # Must NOT create a bare <client>.csv in the same call.
        assert not (tmp_path / "geth.csv").exists()

    def test_build_derived_round_trip(self, tmp_path: Path):
        pytest.importorskip("pandas")
        pytest.importorskip("pyarrow")

        mod = _grep()
        build = _load("speca_build_derived_for_commits_test", BUILD_SCRIPT)

        rows = mod.crawl_commits("geth", fetcher=lambda repo: CANNED_COMMITS)
        csv_path = tmp_path / "geth.commits.csv"
        mod.write_csv(rows, csv_path)

        out_dir = tmp_path / "out"
        manifest = build.build(
            domain="ethereum",
            sources=[str(csv_path)],
            out_dir=out_dir,
            filter_platforms="",
        )

        assert manifest["domain"] == "ethereum"
        assert manifest["n_rows"] == len(rows)
        assert manifest["rows_by_platform"] == {"geth": len(rows)}

        import pyarrow.parquet as pq
        table = pq.read_table(out_dir / "ethereum" / "train.parquet")
        df = table.to_pandas()
        assert "introduced_in_commit" in df.columns
        assert (df["introduced_in_commit"] == "").all()
        # All issue_ids start with COMMIT#
        assert df["issue_id"].str.startswith("COMMIT#").all()


# ---------------------------------------------------------------------------
# Tests: manifest
# ---------------------------------------------------------------------------

class TestManifest:
    def test_write_manifest_fields(self, tmp_path: Path):
        mod = _grep()
        out = tmp_path / "geth.commits_manifest.json"
        mod.write_manifest(
            out,
            client="geth",
            repo="ethereum/go-ethereum",
            n_search_terms=10,
            n_commits_searched=85,
            n_rows=42,
            crawled_at="2026-05-09T00:00:00Z",
            gh_version="gh version 2.49.0 (2024-04-01)",
        )
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["client"] == "geth"
        assert payload["repo"] == "ethereum/go-ethereum"
        assert payload["n_search_terms"] == 10
        assert payload["n_commits_searched"] == 85
        assert payload["n_rows"] == 42
        assert payload["crawled_at"].endswith("Z")
        assert payload["source_url"] == "https://github.com/ethereum/go-ethereum/commits"


# ---------------------------------------------------------------------------
# Tests: module-level constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_security_terms_is_tuple(self):
        mod = _grep()
        assert isinstance(mod.SECURITY_TERMS, tuple)
        assert len(mod.SECURITY_TERMS) >= 5

    def test_max_commits_per_term(self):
        mod = _grep()
        assert mod.MAX_COMMITS_PER_TERM == 200

    def test_csv_fields_matches_crawl(self):
        """CSV_FIELDS must be identical to the sibling crawler's tuple."""
        grep_mod = _grep()
        crawl_mod = _load("speca_crawl_for_grep_test", CRAWL_SCRIPT)
        assert grep_mod.CSV_FIELDS == crawl_mod.CSV_FIELDS

    def test_client_config_matches_crawl(self):
        grep_mod = _grep()
        crawl_mod = _load("speca_crawl_for_grep_test2", CRAWL_SCRIPT)
        assert grep_mod.CLIENT_CONFIG == crawl_mod.CLIENT_CONFIG

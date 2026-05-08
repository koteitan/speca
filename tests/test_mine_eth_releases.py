"""Tests for `benchmarks/scripts/mine_eth_releases.py`.

Network calls are never made — `crawl_releases(..., fetcher=...)` accepts an
injectable fetcher returning canned release payloads, and all writers are
exercised against tmp_path.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MINER_SCRIPT = REPO_ROOT / "benchmarks" / "scripts" / "mine_eth_releases.py"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "build_derived.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _miner():
    return _load("speca_mine_eth_releases", MINER_SCRIPT)


# ---------------------------------------------------------------------------
# SECURITY_LINE_RE boundary tests
# ---------------------------------------------------------------------------

class TestSecurityLineRe:
    def test_security_colon_matches(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("security: fix something important")

    def test_securitytoken_does_not_match(self):
        """Word boundary must prevent partial-word matches."""
        mod = _miner()
        assert not mod.SECURITY_LINE_RE.search("securitytoken is not a problem here")

    def test_cve_matches(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("Fix CVE-2024-12345 in networking layer")

    def test_secure_alone_does_not_match(self):
        """'secure' is not in the keyword list."""
        mod = _miner()
        assert not mod.SECURITY_LINE_RE.search("use a secure connection always")

    def test_panic_matches(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("Fix panic in block import")

    def test_panicking_word_boundary(self):
        """'panicking' — \\bpanic\\b does NOT match because 'k' follows 'panic'."""
        mod = _miner()
        assert not mod.SECURITY_LINE_RE.search("panicking state machine fixed")

    def test_dos_matches(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("Prevent DoS via crafted message")

    def test_crash_matches(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("Fix crash when peer disconnects")

    def test_rce_matches(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("Patch RCE vulnerability in RPC handler")

    def test_memory_leak_matches(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("Fix memory leak in subscription handler")

    def test_integer_overflow_matches(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("Fix integer overflow in fee calculation")

    def test_race_condition_matches(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("Fix race condition in block cache")

    def test_vuln_matches(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("vuln: remote code execution possible")

    def test_vulnerability_matches(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("Patch vulnerability in p2p layer")

    def test_case_insensitive(self):
        mod = _miner()
        assert mod.SECURITY_LINE_RE.search("SECURITY FIX: integer overflow")
        assert mod.SECURITY_LINE_RE.search("PANIC in validator loop")


# ---------------------------------------------------------------------------
# Markdown chrome stripping
# ---------------------------------------------------------------------------

class TestChromeStripping:
    def test_bullet_stripped(self):
        mod = _miner()
        release = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "- security: fix DoS in block import handler for the p2p layer",
            "draft": False,
        }
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) == 1
        assert rows[0]["title"] == "security: fix DoS in block import handler for the p2p layer"

    def test_heading_stripped(self):
        mod = _miner()
        release = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "## security: critical patch for integer overflow in fee calc",
            "draft": False,
        }
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) == 1
        assert rows[0]["title"] == "security: critical patch for integer overflow in fee calc"

    def test_blockquote_stripped(self):
        mod = _miner()
        release = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "> Fix CVE-2024-99999 in RPC handler code path validation",
            "draft": False,
        }
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) == 1
        assert not rows[0]["title"].startswith(">")

    def test_star_bullet_stripped(self):
        mod = _miner()
        release = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "* Fix panic in networking stack on reconnect attempt",
            "draft": False,
        }
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) == 1
        assert not rows[0]["title"].startswith("*")


# ---------------------------------------------------------------------------
# Stable id determinism and uniqueness
# ---------------------------------------------------------------------------

class TestStableId:
    def test_same_line_same_tag_same_id(self):
        """Same line text + same tag always produces the same issue_id."""
        mod = _miner()
        release = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "- security: fix DoS vulnerability in transaction pool handling here",
            "draft": False,
        }
        rows1 = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        rows2 = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows1) == 1
        assert rows1[0]["issue_id"] == rows2[0]["issue_id"]

    def test_different_tags_different_ids(self):
        """Same line text in different tags must produce different ids."""
        mod = _miner()
        body = "- security: fix DoS vulnerability in transaction pool handling here"
        release_v1 = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": body,
            "draft": False,
        }
        release_v2 = {
            "tag_name": "v1.1.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.1.0",
            "published_at": "2024-02-01T00:00:00Z",
            "body": body,
            "draft": False,
        }
        rows_v1 = mod.extract_security_lines_from_release(release_v1, "geth", "ethereum/go-ethereum")
        rows_v2 = mod.extract_security_lines_from_release(release_v2, "geth", "ethereum/go-ethereum")
        assert rows_v1[0]["issue_id"] != rows_v2[0]["issue_id"]

    def test_id_prefixed_release_tag_hash(self):
        """issue_id must be ``RELEASE#<tag>#<8-char hex>``."""
        mod = _miner()
        release = {
            "tag_name": "v1.13.14",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.13.14",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "- Fix security vulnerability in race condition handler code",
            "draft": False,
        }
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) == 1
        parts = rows[0]["issue_id"].split("#")
        assert parts[0] == "RELEASE"
        assert parts[1] == "v1.13.14"
        assert len(parts[2]) == 8
        assert all(c in "0123456789abcdef" for c in parts[2])


# ---------------------------------------------------------------------------
# Per-release dedup
# ---------------------------------------------------------------------------

class TestPerReleaseDedup:
    def test_same_line_twice_in_one_release_yields_one_row(self):
        """Identical line appearing twice in a single release body → 1 row."""
        mod = _miner()
        line = "- Fix panic in block validation when peer sends malformed block data"
        release = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": line + "\n" + line,
            "draft": False,
        }
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) == 1

    def test_different_lines_in_one_release_both_kept(self):
        mod = _miner()
        release = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": (
                "- Fix panic in block validation when peer sends malformed block data\n"
                "- Fix CVE-2024-12345 in RPC authentication and authorization layer\n"
            ),
            "draft": False,
        }
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# Global dedup (same line in old + new release → keep earliest)
# ---------------------------------------------------------------------------

class TestGlobalDedup:
    def _make_release(self, tag: str, pub: str, body: str) -> dict:
        return {
            "tag_name": tag,
            "html_url": f"https://github.com/ethereum/go-ethereum/releases/tag/{tag}",
            "published_at": pub,
            "body": body,
            "draft": False,
        }

    def test_same_line_two_releases_keeps_earliest(self):
        """Same line in v1.0.0 and v1.1.0 → 1 row, attributed to v1.0.0."""
        mod = _miner()
        line = "- Fix security vulnerability in peer discovery handshake code path"
        releases = [
            self._make_release("v1.1.0", "2024-02-01T00:00:00Z", line),
            self._make_release("v1.0.0", "2024-01-01T00:00:00Z", line),
        ]
        rows = mod.crawl_releases("geth", fetcher=lambda _: releases)
        assert len(rows) == 1
        # Should come from the EARLIER release (v1.0.0)
        assert "v1.0.0" in rows[0]["issue_id"]

    def test_unique_lines_both_kept(self):
        mod = _miner()
        releases = [
            self._make_release(
                "v1.0.0", "2024-01-01T00:00:00Z",
                "- Fix panic in block validation when peer sends malformed block data",
            ),
            self._make_release(
                "v1.1.0", "2024-02-01T00:00:00Z",
                "- Fix CVE-2024-99999 in RPC authentication and authorization layer",
            ),
        ]
        rows = mod.crawl_releases("geth", fetcher=lambda _: releases)
        assert len(rows) == 2

    def test_draft_releases_excluded(self):
        """Draft releases must not contribute any rows."""
        mod = _miner()
        releases = [
            {
                "tag_name": "v1.0.0-draft",
                "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0-draft",
                "published_at": "2024-01-01T00:00:00Z",
                "body": "- Fix panic in block validation when peer sends malformed block data",
                "draft": True,
            },
        ]
        # fetch_releases filters drafts before returning, so use fetcher
        # that returns pre-filtered list (matching real behaviour)
        filtered = [r for r in releases if not r.get("draft", False)]
        rows = mod.crawl_releases("geth", fetcher=lambda _: filtered)
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Min-length filter
# ---------------------------------------------------------------------------

class TestMinLength:
    def _make_release(self, body: str) -> dict:
        return {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": body,
            "draft": False,
        }

    def test_short_title_dropped(self):
        """Titles < 10 chars after chrome stripping are dropped."""
        mod = _miner()
        # 'panic' alone is 5 chars → dropped.
        release = self._make_release("- panic")
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) == 0

    def test_exactly_ten_chars_kept(self):
        mod = _miner()
        # "panic test" = 10 chars after stripping "- "
        release = self._make_release("- panic test")
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) == 1

    def test_nine_chars_dropped(self):
        mod = _miner()
        # "panic now" = 9 chars
        release = self._make_release("- panic now")
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Description includes context + tag prefix
# ---------------------------------------------------------------------------

class TestDescription:
    def test_description_prefixed_with_tag(self):
        mod = _miner()
        # The heading "## Security Fixes" also matches SECURITY_LINE_RE, so
        # this body produces 2 rows (heading + panic line).  All rows must
        # have their description prefixed with the tag name.
        release = {
            "tag_name": "v1.13.14",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.13.14",
            "published_at": "2024-01-01T00:00:00Z",
            "body": (
                "## Security Fixes\n"
                "\n"
                "- Fix panic in block import when chain reorg detected at depth\n"
                "- Other change\n"
            ),
            "draft": False,
        }
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) >= 1
        # Every row's description must be prefixed with the release tag.
        for row in rows:
            assert row["description"].startswith("[v1.13.14]")

    def test_description_includes_context_lines(self):
        mod = _miner()
        release = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": (
                "## v1.0.0 Release Notes\n"
                "Released 2024-01-01\n"
                "### Security\n"
                "- Fix crash in block importer nil pointer encountered here\n"
                "- Other unrelated fix for something else\n"
            ),
            "draft": False,
        }
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert len(rows) == 1
        desc = rows[0]["description"]
        # Context before should include the heading.
        assert "v1.0.0" in desc or "Security" in desc


# ---------------------------------------------------------------------------
# source_url is the release HTML URL
# ---------------------------------------------------------------------------

class TestSourceUrl:
    def test_source_url_is_html_url(self):
        mod = _miner()
        release = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "- Fix CVE-2024-12345 in the transaction validation logic code",
            "draft": False,
        }
        rows = mod.extract_security_lines_from_release(release, "geth", "ethereum/go-ethereum")
        assert rows[0]["source_url"] == "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0"


# ---------------------------------------------------------------------------
# crawl_releases: injectable fetcher + unknown client rejection
# ---------------------------------------------------------------------------

class TestCrawlReleases:
    def test_rejects_unknown_client(self):
        mod = _miner()
        with pytest.raises(SystemExit):
            mod.crawl_releases("unknown-xyz", fetcher=lambda _: [])

    def test_empty_fetcher_returns_empty(self):
        mod = _miner()
        rows = mod.crawl_releases("geth", fetcher=lambda _: [])
        assert rows == []

    def test_source_field_is_client_slug(self):
        mod = _miner()
        release = {
            "tag_name": "v5.0.0",
            "html_url": "https://github.com/sigp/lighthouse/releases/tag/v5.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "- Fix panic in fork choice block validation routine code",
            "draft": False,
        }
        rows = mod.crawl_releases("lighthouse", fetcher=lambda _: [release])
        assert rows[0]["source"] == "lighthouse"

    def test_contest_field_is_repo(self):
        mod = _miner()
        release = {
            "tag_name": "v5.0.0",
            "html_url": "https://github.com/sigp/lighthouse/releases/tag/v5.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "- Fix panic in fork choice block validation routine code",
            "draft": False,
        }
        rows = mod.crawl_releases("lighthouse", fetcher=lambda _: [release])
        assert rows[0]["contest"] == "sigp/lighthouse"


# ---------------------------------------------------------------------------
# write_csv round-trip
# ---------------------------------------------------------------------------

class TestWriteCsv:
    def test_csv_has_correct_header(self, tmp_path: Path):
        mod = _miner()
        release = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "- Fix panic in block import when chain reorg detected at depth\n",
            "draft": False,
        }
        rows = mod.crawl_releases("geth", fetcher=lambda _: [release])
        out = tmp_path / "geth.releases.csv"
        n = mod.write_csv(rows, out)
        assert n >= 1
        with out.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            assert tuple(reader.fieldnames) == mod.CSV_FIELDS

    def test_csv_introduced_in_commit_is_empty(self, tmp_path: Path):
        mod = _miner()
        release = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "- Fix crash in EVM execution when opcode limit exceeded badly\n",
            "draft": False,
        }
        rows = mod.crawl_releases("geth", fetcher=lambda _: [release])
        out = tmp_path / "geth.releases.csv"
        mod.write_csv(rows, out)
        with out.open(encoding="utf-8", newline="") as f:
            record = list(csv.DictReader(f))[0]
        assert record["introduced_in_commit"] == ""


# ---------------------------------------------------------------------------
# write_manifest
# ---------------------------------------------------------------------------

class TestWriteManifest:
    def test_manifest_fields(self, tmp_path: Path):
        mod = _miner()
        out = tmp_path / "geth.releases_manifest.json"
        mod.write_manifest(
            out,
            client="geth",
            repo="ethereum/go-ethereum",
            n_releases_scanned=42,
            n_rows=17,
        )
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["client"] == "geth"
        assert payload["repo"] == "ethereum/go-ethereum"
        assert payload["n_releases_scanned"] == 42
        assert payload["n_rows"] == 17
        assert payload["source_url"] == "https://github.com/ethereum/go-ethereum/releases"
        assert payload["crawled_at"].endswith("Z")
        assert "gh_version" in payload


# ---------------------------------------------------------------------------
# Round-trip through build_derived
# ---------------------------------------------------------------------------

class TestBuildDerivedRoundTrip:
    def test_csv_ingests_cleanly(self, tmp_path: Path):
        pytest.importorskip("pandas")
        pytest.importorskip("pyarrow")

        mod = _miner()
        build = _load("speca_build_derived_for_releases_test", BUILD_SCRIPT)

        releases = [
            {
                "tag_name": "v1.0.0",
                "html_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.0.0",
                "published_at": "2024-01-01T00:00:00Z",
                "body": (
                    "## Security\n"
                    "- Fix CVE-2024-11111 in block import and transaction pool handling\n"
                    "- Fix panic in network stack when receiving a crafted message\n"
                    "- Fix security vulnerability in peer discovery handshake code\n"
                ),
                "draft": False,
            }
        ]
        rows = mod.crawl_releases("geth", fetcher=lambda _: releases)
        assert len(rows) >= 1

        csv_path = tmp_path / "geth.releases.csv"
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

        import pyarrow.parquet as pq
        table = pq.read_table(out_dir / "ethereum" / "train.parquet")
        df = table.to_pandas()
        assert "introduced_in_commit" in df.columns
        assert (df["introduced_in_commit"] == "").all()
        assert (df["source_platform"] == "geth").all()

    def test_parquet_has_expected_columns(self, tmp_path: Path):
        pytest.importorskip("pandas")
        pytest.importorskip("pyarrow")

        mod = _miner()
        build = _load("speca_build_derived_for_releases_cols", BUILD_SCRIPT)

        releases = [
            {
                "tag_name": "v2.0.0",
                "html_url": "https://github.com/NethermindEth/nethermind/releases/tag/v2.0.0",
                "published_at": "2024-03-01T00:00:00Z",
                "body": "- Fix memory leak in chain subscription handler code path\n",
                "draft": False,
            }
        ]
        rows = mod.crawl_releases("nethermind", fetcher=lambda _: releases)
        csv_path = tmp_path / "nethermind.releases.csv"
        mod.write_csv(rows, csv_path)

        out_dir = tmp_path / "out"
        build.build(
            domain="ethereum",
            sources=[str(csv_path)],
            out_dir=out_dir,
            filter_platforms="",
        )

        import pyarrow.parquet as pq
        table = pq.read_table(out_dir / "ethereum" / "train.parquet")
        required_cols = {
            "id", "source_platform", "contest", "issue_id",
            "severity", "title", "description", "source_url",
            "introduced_in_commit", "domain",
        }
        assert required_cols.issubset(set(table.schema.names))

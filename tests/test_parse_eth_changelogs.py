"""Tests for `benchmarks/scripts/parse_eth_changelogs.py`.

Network calls are never made — `crawl_changelog` accepts injectable
`finder` and `branch_resolver` callables that return canned data.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PARSER_SCRIPT = REPO_ROOT / "benchmarks" / "scripts" / "parse_eth_changelogs.py"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "build_derived.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _parser():
    return _load("speca_parse_eth_changelogs", PARSER_SCRIPT)


# ---------------------------------------------------------------------------
# SECURITY_LINE_RE boundary tests
# ---------------------------------------------------------------------------

class TestSecurityLineRe:
    def test_security_colon_matches(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("security: fix something important")

    def test_securitytoken_does_not_match(self):
        """Word boundary must prevent partial-word matches.

        'securitytoken' must NOT match — the \b after 'security' is not
        satisfied because 't' is a word character.  We test against a
        string that contains ONLY 'securitytoken' (no other keywords).
        """
        mod = _parser()
        assert not mod.SECURITY_LINE_RE.search("securitytoken is not a problem here")

    def test_cve_matches(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("Fix CVE-2024-12345 in networking layer")

    def test_secure_alone_does_not_match(self):
        """'secure' is not in the keyword list and must not match."""
        mod = _parser()
        # 'secure' is a substring of 'security' but SECURITY_LINE_RE only
        # matches full keywords; 'secure' alone should not match.
        # (The regex is \bsecurity\b not \bsecure\b.)
        assert not mod.SECURITY_LINE_RE.search("use a secure connection always")

    def test_panic_matches(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("Fix panic in block import")

    def test_panicking_word_boundary(self):
        """'panicking' contains 'panic' — word boundary determines behaviour.

        'panic' IS a prefix of 'panicking'; \bpanic\b will NOT match inside
        'panicking' because 'k' after 'panic' is a word character.  This is
        the documented behaviour for word-boundary anchoring.
        """
        mod = _parser()
        # panicking: the 'c' in 'panic' is followed by 'k' (word char) so
        # \bpanic\b does NOT match.
        assert not mod.SECURITY_LINE_RE.search("panicking state machine fixed")

    def test_dos_matches(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("Prevent DoS via crafted message")

    def test_crash_matches(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("Fix crash when peer disconnects")

    def test_rce_matches(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("Patch RCE vulnerability in RPC handler")

    def test_memory_leak_matches(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("Fix memory leak in subscription handler")

    def test_integer_overflow_matches(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("Fix integer overflow in fee calculation")

    def test_race_condition_matches(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("Fix race condition in block cache")

    def test_vuln_matches(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("vuln: remote code execution possible")

    def test_vulnerability_matches(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("Patch vulnerability in p2p layer")

    def test_case_insensitive(self):
        mod = _parser()
        assert mod.SECURITY_LINE_RE.search("SECURITY FIX: integer overflow")
        assert mod.SECURITY_LINE_RE.search("PANIC in validator loop")


# ---------------------------------------------------------------------------
# Markdown chrome stripping
# ---------------------------------------------------------------------------

class TestChromeStripping:
    def test_bullet_stripped(self):
        mod = _parser()
        # Use extract_security_lines with a single-line changelog.
        line = "- security: fix DoS in block import handler"
        rows = mod.extract_security_lines(
            line, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert len(rows) == 1
        assert rows[0]["title"] == "security: fix DoS in block import handler"

    def test_heading_stripped(self):
        mod = _parser()
        line = "## security: critical patch for integer overflow"
        rows = mod.extract_security_lines(
            line, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert len(rows) == 1
        assert rows[0]["title"] == "security: critical patch for integer overflow"

    def test_blockquote_stripped(self):
        mod = _parser()
        line = "> Fix CVE-2024-99999 in RPC handler code"
        rows = mod.extract_security_lines(
            line, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert len(rows) == 1
        assert not rows[0]["title"].startswith(">")

    def test_star_bullet_stripped(self):
        mod = _parser()
        line = "* Fix panic in networking stack on reconnect"
        rows = mod.extract_security_lines(
            line, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert len(rows) == 1
        assert not rows[0]["title"].startswith("*")


# ---------------------------------------------------------------------------
# Stable id determinism
# ---------------------------------------------------------------------------

class TestStableId:
    def test_same_line_same_id_across_two_calls(self):
        mod = _parser()
        line = "- security: fix DoS vulnerability in transaction pool handling"
        rows1 = mod.extract_security_lines(
            line, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        rows2 = mod.extract_security_lines(
            line, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert rows1[0]["issue_id"] == rows2[0]["issue_id"]

    def test_different_lines_different_ids(self):
        mod = _parser()
        text = (
            "- security: fix DoS vulnerability in transaction pool handling\n"
            "- Fix CVE-2024-12345 in block import validation logic here"
        )
        rows = mod.extract_security_lines(
            text, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert len(rows) == 2
        assert rows[0]["issue_id"] != rows[1]["issue_id"]

    def test_id_prefixed_with_changelog_hash(self):
        mod = _parser()
        line = "- security: fix race condition in peer manager thread"
        rows = mod.extract_security_lines(
            line, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert rows[0]["issue_id"].startswith("CHANGELOG#")
        # 16-char hex after the prefix
        hex_part = rows[0]["issue_id"].split("#")[1]
        assert len(hex_part) == 16
        assert all(c in "0123456789abcdef" for c in hex_part)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDedup:
    def test_same_line_twice_yields_one_row(self):
        mod = _parser()
        # Identical line appearing twice (e.g. duplicate changelog entry).
        line = "- Fix panic in block validation when peer sends malformed block"
        text = line + "\n" + line
        rows = mod.extract_security_lines(
            text, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert len(rows) == 1

    def test_same_line_different_positions_keeps_first(self):
        mod = _parser()
        line = "- Fix crash in EVM execution when stack depth exceeded badly"
        text = (
            "## v1.0.0\n"
            + line + "\n"
            + "## v0.9.0\n"
            + line + "\n"
        )
        rows = mod.extract_security_lines(
            text, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert len(rows) == 1
        # First occurrence is on line 2 (1-indexed), so source_url ends with #L2.
        assert rows[0]["source_url"].endswith("#L2")


# ---------------------------------------------------------------------------
# Min-length filter
# ---------------------------------------------------------------------------

class TestMinLength:
    def test_short_title_dropped(self):
        """Titles shorter than 10 chars after chrome stripping are noise."""
        mod = _parser()
        # 'panic' alone is 5 chars → dropped.
        line = "- panic"
        rows = mod.extract_security_lines(
            line, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert len(rows) == 0

    def test_exactly_ten_chars_kept(self):
        mod = _parser()
        # Exactly 10 chars after stripping: "panic test" (10)
        line = "- panic test"  # after stripping: "panic test" = 10 chars
        rows = mod.extract_security_lines(
            line, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert len(rows) == 1

    def test_nine_chars_dropped(self):
        mod = _parser()
        # 9 chars after stripping: "panic now" = 9 chars
        line = "- panic now"
        rows = mod.extract_security_lines(
            line, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Context lines in description
# ---------------------------------------------------------------------------

class TestContextLines:
    def test_description_includes_surrounding_lines(self):
        mod = _parser()
        text = (
            "## v1.13.0\n"
            "Released 2024-01-01\n"
            "### Bugfixes\n"
            "- Fix crash in block importer when nil pointer encountered\n"
            "- Other unrelated fix\n"
            "- Another unrelated fix\n"
        )
        rows = mod.extract_security_lines(
            text, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert len(rows) == 1
        desc = rows[0]["description"]
        # The context before (up to 3 lines) should include the heading.
        assert "v1.13.0" in desc or "Released" in desc or "Bugfixes" in desc

    def test_description_lines_joined_with_newline(self):
        mod = _parser()
        text = (
            "## v1.0.0\n"
            "- Fix security: crash in network handler\n"
            "- Next line\n"
        )
        rows = mod.extract_security_lines(
            text, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert "\n" in rows[0]["description"]


# ---------------------------------------------------------------------------
# source_url format
# ---------------------------------------------------------------------------

class TestSourceUrl:
    def test_source_url_format(self):
        mod = _parser()
        line = "- Fix CVE-2024-12345 in the transaction validation logic code"
        rows = mod.extract_security_lines(
            line, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert rows[0]["source_url"] == (
            "https://github.com/ethereum/go-ethereum"
            "/blob/master/CHANGELOG.md#L1"
        )

    def test_source_url_line_number_is_1indexed(self):
        mod = _parser()
        # Line 1: plain heading with no security keyword
        # Line 2: security-relevant line — must get #L2
        text = "## v1.0.0\n- Fix crash in p2p layer due to nil pointer deref\n"
        rows = mod.extract_security_lines(
            text, "CHANGELOG.md", "ethereum/go-ethereum", "master", "geth"
        )
        assert rows[0]["source_url"].endswith("#L2")


# ---------------------------------------------------------------------------
# crawl_changelog injection
# ---------------------------------------------------------------------------

class TestCrawlChangelog:
    def test_returns_empty_when_finder_returns_none(self):
        mod = _parser()
        rows = mod.crawl_changelog(
            "geth",
            finder=lambda repo: None,
            branch_resolver=lambda repo: "master",
        )
        assert rows == []

    def test_uses_injected_finder_and_branch_resolver(self):
        mod = _parser()
        fake_text = (
            "## v1.0.0\n"
            "- Fix CVE-2024-99999 in block import and sync mechanism\n"
        )
        rows = mod.crawl_changelog(
            "geth",
            finder=lambda repo: ("CHANGELOG.md", fake_text),
            branch_resolver=lambda repo: "master",
        )
        assert len(rows) == 1
        assert "CVE-2024-99999" in rows[0]["title"] or "CVE-2024-99999" in rows[0]["description"]

    def test_source_field_is_client_slug(self):
        mod = _parser()
        fake_text = "- Fix panic in fork choice block validation routine\n"
        rows = mod.crawl_changelog(
            "lighthouse",
            finder=lambda repo: ("CHANGELOG.md", fake_text),
            branch_resolver=lambda repo: "main",
        )
        assert rows[0]["source"] == "lighthouse"

    def test_contest_field_is_repo(self):
        mod = _parser()
        fake_text = "- Fix panic in fork choice block validation routine\n"
        rows = mod.crawl_changelog(
            "lighthouse",
            finder=lambda repo: ("CHANGELOG.md", fake_text),
            branch_resolver=lambda repo: "main",
        )
        assert rows[0]["contest"] == "sigp/lighthouse"

    def test_rejects_unknown_client(self):
        mod = _parser()
        with pytest.raises(SystemExit):
            mod.crawl_changelog("unknown-xyz", finder=lambda r: None, branch_resolver=lambda r: "main")


# ---------------------------------------------------------------------------
# write_csv round-trip
# ---------------------------------------------------------------------------

class TestWriteCsv:
    def test_csv_has_correct_header(self, tmp_path: Path):
        mod = _parser()
        fake_text = "- Fix panic in block import when chain reorg detected at depth\n"
        rows = mod.crawl_changelog(
            "geth",
            finder=lambda repo: ("CHANGELOG.md", fake_text),
            branch_resolver=lambda repo: "master",
        )
        out = tmp_path / "geth.changelog.csv"
        n = mod.write_csv(rows, out)
        assert n == 1
        with out.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            assert tuple(reader.fieldnames) == mod.CSV_FIELDS

    def test_csv_introduced_in_commit_is_empty(self, tmp_path: Path):
        mod = _parser()
        fake_text = "- Fix crash in EVM execution when opcode limit exceeded badly\n"
        rows = mod.crawl_changelog(
            "geth",
            finder=lambda repo: ("CHANGELOG.md", fake_text),
            branch_resolver=lambda repo: "master",
        )
        out = tmp_path / "geth.changelog.csv"
        mod.write_csv(rows, out)
        with out.open(encoding="utf-8", newline="") as f:
            record = list(csv.DictReader(f))[0]
        assert record["introduced_in_commit"] == ""


# ---------------------------------------------------------------------------
# Round-trip through build_derived
# ---------------------------------------------------------------------------

class TestBuildDerivedRoundTrip:
    def test_csv_ingests_cleanly(self, tmp_path: Path):
        pytest.importorskip("pandas")
        pytest.importorskip("pyarrow")

        mod = _parser()
        build = _load("speca_build_derived_for_changelog_test", BUILD_SCRIPT)

        fake_text = (
            "## v1.0.0\n"
            "- Fix CVE-2024-11111 in block import and transaction pool\n"
            "- Fix panic in network stack when receiving crafted message\n"
            "- Fix security vulnerability in peer discovery handshake code\n"
        )
        rows = mod.crawl_changelog(
            "geth",
            finder=lambda repo: ("CHANGELOG.md", fake_text),
            branch_resolver=lambda repo: "master",
        )
        assert len(rows) >= 1

        csv_path = tmp_path / "geth.changelog.csv"
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
        # All rows should be for geth.
        assert (df["source_platform"] == "geth").all()

    def test_parquet_has_expected_columns(self, tmp_path: Path):
        pytest.importorskip("pandas")
        pytest.importorskip("pyarrow")

        mod = _parser()
        build = _load("speca_build_derived_for_changelog_cols", BUILD_SCRIPT)

        fake_text = "- Fix memory leak in chain subscription handler code path\n"
        rows = mod.crawl_changelog(
            "nethermind",
            finder=lambda repo: ("CHANGELOG.md", fake_text),
            branch_resolver=lambda repo: "master",
        )
        csv_path = tmp_path / "nethermind.changelog.csv"
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

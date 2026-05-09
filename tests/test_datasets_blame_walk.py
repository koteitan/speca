"""Tests for `scripts/datasets/blame_walk.py`.

All resolvers are tested with canned gh fetchers — no network I/O.
Covers:
    - Happy path for PR, RELEASE, COMMIT, GHSA resolvers
    - Edge cases: 404, missing parents, annotated tag dereference
    - dispatch routing by issue_id prefix
    - walk() round-trip: same columns, introduced_in_commit populated
    - Cache: same (repo, sha) hit → only one gh call
    - Issue and Changelog resolvers return "" in v1

The module-level pandas/pyarrow skip mirrors test_datasets_build.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BLAME_WALK_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "blame_walk.py"

# Skip module if optional deps are absent
_required = ("pandas", "pyarrow")
_missing = [m for m in _required if importlib.util.find_spec(m) is None]
if _missing:
    pytest.skip(
        f"missing optional deps {_missing}; install with `uv sync --group datasets`",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

def _load_blame_walk():
    spec = importlib.util.spec_from_file_location("speca_blame_walk", BLAME_WALK_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["speca_blame_walk"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Canned gh payloads
# ---------------------------------------------------------------------------

_MERGE_SHA = "aabbccdd" * 5  # 40 chars
_PARENT_SHA = "11223344" * 5
_TAG_COMMIT_SHA = "deadbeef" * 5
_TAG_PARENT_SHA = "cafebabe" * 5
_ANNOTATED_TAG_OBJ_SHA = "feedface" * 5
_ANNOTATED_COMMIT_SHA = "baadf00d" * 5
_ANNOTATED_PARENT_SHA = "d00dfeed" * 5

PR_PAYLOADS = {
    f"repos/ethereum/go-ethereum/pulls/1234": {
        "merge_commit_sha": _MERGE_SHA,
        "state": "closed",
    },
    f"repos/ethereum/go-ethereum/commits/{_MERGE_SHA}": {
        "sha": _MERGE_SHA,
        "parents": [{"sha": _PARENT_SHA}],
    },
}

RELEASE_PAYLOADS = {
    "repos/ethereum/go-ethereum/git/ref/tags/v1.14.0": {
        "ref": "refs/tags/v1.14.0",
        "object": {"sha": _TAG_COMMIT_SHA, "type": "commit"},
    },
    f"repos/ethereum/go-ethereum/commits/{_TAG_COMMIT_SHA}": {
        "sha": _TAG_COMMIT_SHA,
        "parents": [{"sha": _TAG_PARENT_SHA}],
    },
}

ANNOTATED_TAG_PAYLOADS = {
    "repos/ethereum/go-ethereum/git/ref/tags/v2.0.0": {
        "ref": "refs/tags/v2.0.0",
        "object": {"sha": _ANNOTATED_TAG_OBJ_SHA, "type": "tag"},
    },
    f"repos/ethereum/go-ethereum/git/tags/{_ANNOTATED_TAG_OBJ_SHA}": {
        "object": {"sha": _ANNOTATED_COMMIT_SHA, "type": "commit"},
    },
    f"repos/ethereum/go-ethereum/commits/{_ANNOTATED_COMMIT_SHA}": {
        "sha": _ANNOTATED_COMMIT_SHA,
        "parents": [{"sha": _ANNOTATED_PARENT_SHA}],
    },
}

_FULL_COMMIT_SHA = "a" * 40
_FULL_COMMIT_PARENT = "b" * 40

COMMIT_PAYLOADS = {
    f"repos/ethereum/go-ethereum/commits/{_FULL_COMMIT_SHA}": {
        "sha": _FULL_COMMIT_SHA,
        "parents": [{"sha": _FULL_COMMIT_PARENT}],
    },
    # short sha fallback
    "repos/ethereum/go-ethereum/commits/abcdef123456": {
        "sha": "abcdef123456" + "0" * 28,
        "parents": [{"sha": "0" * 40}],
    },
}

ADVISORY_PAYLOADS = {
    "repos/ethereum/go-ethereum/security-advisories/GHSA-aaaa-bbbb-cccc": {
        "ghsa_id": "GHSA-aaaa-bbbb-cccc",
        "vulnerabilities": [
            {"patched_versions": ">= 1.14.0"},
        ],
    },
    # Tag for advisory resolution (reuse RELEASE_PAYLOADS)
    **RELEASE_PAYLOADS,
}


def _make_gh(payloads: dict):
    """Return a gh fetcher backed by a dict of path → payload."""
    call_log: list[str] = []

    def fetcher(path: str):
        call_log.append(path)
        return payloads.get(path)

    fetcher.call_log = call_log  # type: ignore[attr-defined]
    return fetcher


# ---------------------------------------------------------------------------
# resolve_pr tests
# ---------------------------------------------------------------------------

class TestResolvePr:
    def test_happy_path(self):
        mod = _load_blame_walk()
        gh = _make_gh(PR_PAYLOADS)
        row = {"issue_id": "PR#1234", "source_platform": "geth"}
        result = mod.resolve_pr(row, gh)
        assert result == _PARENT_SHA

    def test_pr_closed_without_merge(self):
        mod = _load_blame_walk()
        payloads = {
            "repos/ethereum/go-ethereum/pulls/999": {
                "merge_commit_sha": None,
                "state": "closed",
            },
        }
        gh = _make_gh(payloads)
        row = {"issue_id": "PR#999", "source_platform": "geth"}
        result = mod.resolve_pr(row, gh)
        assert result == ""

    def test_404_on_pr(self):
        mod = _load_blame_walk()
        gh = _make_gh({})  # all 404s
        row = {"issue_id": "PR#9999", "source_platform": "geth"}
        result = mod.resolve_pr(row, gh)
        assert result == ""

    def test_unknown_platform(self):
        mod = _load_blame_walk()
        gh = _make_gh(PR_PAYLOADS)
        row = {"issue_id": "PR#1234", "source_platform": "unknown-client"}
        result = mod.resolve_pr(row, gh)
        assert result == ""

    def test_bad_issue_id_format(self):
        mod = _load_blame_walk()
        gh = _make_gh(PR_PAYLOADS)
        row = {"issue_id": "PR#abc", "source_platform": "geth"}
        result = mod.resolve_pr(row, gh)
        assert result == ""

    def test_no_parents_on_commit(self):
        mod = _load_blame_walk()
        payloads = {
            "repos/ethereum/go-ethereum/pulls/1": {
                "merge_commit_sha": _MERGE_SHA,
            },
            f"repos/ethereum/go-ethereum/commits/{_MERGE_SHA}": {
                "sha": _MERGE_SHA,
                "parents": [],
            },
        }
        gh = _make_gh(payloads)
        row = {"issue_id": "PR#1", "source_platform": "geth"}
        result = mod.resolve_pr(row, gh)
        assert result == ""


# ---------------------------------------------------------------------------
# resolve_release tests
# ---------------------------------------------------------------------------

class TestResolveRelease:
    def test_happy_path(self):
        mod = _load_blame_walk()
        gh = _make_gh(RELEASE_PAYLOADS)
        row = {"issue_id": "RELEASE#v1.14.0#abcd1234", "source_platform": "geth"}
        result = mod.resolve_release(row, gh)
        assert result == _TAG_PARENT_SHA

    def test_annotated_tag_dereference(self):
        mod = _load_blame_walk()
        gh = _make_gh(ANNOTATED_TAG_PAYLOADS)
        row = {"issue_id": "RELEASE#v2.0.0#cafecafe", "source_platform": "geth"}
        result = mod.resolve_release(row, gh)
        assert result == _ANNOTATED_PARENT_SHA

    def test_404_on_tag(self):
        mod = _load_blame_walk()
        gh = _make_gh({})
        row = {"issue_id": "RELEASE#v99.0.0#deadbeef", "source_platform": "geth"}
        result = mod.resolve_release(row, gh)
        assert result == ""

    def test_v_prefix_retry(self):
        """If the tag without 'v' 404s, the resolver retries with 'v' prefix."""
        mod = _load_blame_walk()
        # Only the 'v' prefixed tag exists
        payloads = {
            "repos/ethereum/go-ethereum/git/ref/tags/v1.14.0": {
                "ref": "refs/tags/v1.14.0",
                "object": {"sha": _TAG_COMMIT_SHA, "type": "commit"},
            },
            f"repos/ethereum/go-ethereum/commits/{_TAG_COMMIT_SHA}": {
                "sha": _TAG_COMMIT_SHA,
                "parents": [{"sha": _TAG_PARENT_SHA}],
            },
        }
        gh = _make_gh(payloads)
        # issue_id uses tag without 'v' — resolver should retry with 'v'
        row = {"issue_id": "RELEASE#1.14.0#abcd1234", "source_platform": "geth"}
        result = mod.resolve_release(row, gh)
        assert result == _TAG_PARENT_SHA

    def test_bad_issue_id_format(self):
        mod = _load_blame_walk()
        gh = _make_gh(RELEASE_PAYLOADS)
        row = {"issue_id": "RELEASE#", "source_platform": "geth"}
        result = mod.resolve_release(row, gh)
        assert result == ""

    def test_initial_commit_no_parents(self):
        mod = _load_blame_walk()
        payloads = {
            "repos/ethereum/go-ethereum/git/ref/tags/v0.1.0": {
                "ref": "refs/tags/v0.1.0",
                "object": {"sha": _TAG_COMMIT_SHA, "type": "commit"},
            },
            f"repos/ethereum/go-ethereum/commits/{_TAG_COMMIT_SHA}": {
                "sha": _TAG_COMMIT_SHA,
                "parents": [],
            },
        }
        gh = _make_gh(payloads)
        row = {"issue_id": "RELEASE#v0.1.0#00000000", "source_platform": "geth"}
        result = mod.resolve_release(row, gh)
        assert result == ""


# ---------------------------------------------------------------------------
# resolve_commit tests
# ---------------------------------------------------------------------------

class TestResolveCommit:
    def test_happy_path_full_sha_from_url(self):
        mod = _load_blame_walk()
        gh = _make_gh(COMMIT_PAYLOADS)
        row = {
            "issue_id": f"COMMIT#{'a' * 12}",
            "source_platform": "geth",
            "source_url": f"https://github.com/ethereum/go-ethereum/commit/{'a' * 40}",
        }
        result = mod.resolve_commit(row, gh)
        assert result == _FULL_COMMIT_PARENT

    def test_fallback_to_short_sha(self):
        mod = _load_blame_walk()
        gh = _make_gh(COMMIT_PAYLOADS)
        row = {
            "issue_id": "COMMIT#abcdef123456",
            "source_platform": "geth",
            "source_url": "https://github.com/ethereum/go-ethereum/pull/1234",  # no /commit/
        }
        result = mod.resolve_commit(row, gh)
        assert result == "0" * 40

    def test_404_on_commit(self):
        mod = _load_blame_walk()
        gh = _make_gh({})
        row = {
            "issue_id": "COMMIT#abcdef123456",
            "source_platform": "geth",
            "source_url": "",
        }
        result = mod.resolve_commit(row, gh)
        assert result == ""

    def test_bad_issue_id_format(self):
        mod = _load_blame_walk()
        gh = _make_gh(COMMIT_PAYLOADS)
        row = {"issue_id": "COMMIT#xyz", "source_platform": "geth", "source_url": ""}
        result = mod.resolve_commit(row, gh)
        assert result == ""


# ---------------------------------------------------------------------------
# resolve_advisory tests
# ---------------------------------------------------------------------------

class TestResolveAdvisory:
    def test_happy_path(self):
        mod = _load_blame_walk()
        gh = _make_gh(ADVISORY_PAYLOADS)
        row = {"issue_id": "GHSA-aaaa-bbbb-cccc", "source_platform": "geth"}
        result = mod.resolve_advisory(row, gh)
        assert result == _TAG_PARENT_SHA

    def test_404_on_advisory(self):
        mod = _load_blame_walk()
        gh = _make_gh({})
        row = {"issue_id": "GHSA-zzzz-yyyy-xxxx", "source_platform": "geth"}
        result = mod.resolve_advisory(row, gh)
        assert result == ""

    def test_empty_patched_versions(self):
        mod = _load_blame_walk()
        payloads = {
            "repos/ethereum/go-ethereum/security-advisories/GHSA-test-test-test": {
                "ghsa_id": "GHSA-test-test-test",
                "vulnerabilities": [{"patched_versions": ""}],
            },
        }
        gh = _make_gh(payloads)
        row = {"issue_id": "GHSA-test-test-test", "source_platform": "geth"}
        result = mod.resolve_advisory(row, gh)
        assert result == ""

    def test_no_vulnerabilities(self):
        mod = _load_blame_walk()
        payloads = {
            "repos/ethereum/go-ethereum/security-advisories/GHSA-empty-vuln-list": {
                "ghsa_id": "GHSA-empty-vuln-list",
                "vulnerabilities": [],
            },
        }
        gh = _make_gh(payloads)
        row = {"issue_id": "GHSA-empty-vuln-list", "source_platform": "geth"}
        result = mod.resolve_advisory(row, gh)
        assert result == ""

    def test_non_ghsa_prefix_returns_empty(self):
        mod = _load_blame_walk()
        gh = _make_gh(ADVISORY_PAYLOADS)
        row = {"issue_id": "CVE-2024-1234", "source_platform": "geth"}
        result = mod.resolve_advisory(row, gh)
        assert result == ""


# ---------------------------------------------------------------------------
# _parse_first_semver tests
# ---------------------------------------------------------------------------

class TestParseFirstSemver:
    def test_gte_prefix(self):
        mod = _load_blame_walk()
        assert mod._parse_first_semver(">= 1.16.9") == "1.16.9"

    def test_caret(self):
        mod = _load_blame_walk()
        assert mod._parse_first_semver("^1.2.3") == "1.2.3"

    def test_tilde(self):
        mod = _load_blame_walk()
        assert mod._parse_first_semver("~2.0.0") == "2.0.0"

    def test_multiple_constraints(self):
        mod = _load_blame_walk()
        # Takes first semver-like token
        result = mod._parse_first_semver(">= 1.5.0, < 2.0.0")
        assert result in ("1.5.0", "2.0.0")

    def test_empty(self):
        mod = _load_blame_walk()
        assert mod._parse_first_semver("") == ""

    def test_no_semver(self):
        mod = _load_blame_walk()
        assert mod._parse_first_semver(">= latest") == ""


# ---------------------------------------------------------------------------
# resolve_issue and resolve_changelog (v1: always "")
# ---------------------------------------------------------------------------

class TestV1Stubs:
    def test_resolve_issue_returns_empty(self):
        mod = _load_blame_walk()
        gh = _make_gh({})
        row = {"issue_id": "ISSUE#42", "source_platform": "geth"}
        assert mod.resolve_issue(row, gh) == ""

    def test_resolve_changelog_returns_empty(self):
        mod = _load_blame_walk()
        gh = _make_gh({})
        row = {"issue_id": "CHANGELOG#abcdef1234567890", "source_platform": "geth"}
        assert mod.resolve_changelog(row, gh) == ""


# ---------------------------------------------------------------------------
# dispatch routing
# ---------------------------------------------------------------------------

class TestDispatch:
    def _gh(self):
        return _make_gh({})  # all 404s — routing test only cares about prefix dispatch

    def test_routes_pr(self):
        mod = _load_blame_walk()
        row = {"issue_id": "PR#1", "source_platform": "geth"}
        # No crash even on 404; returns ""
        result = mod.dispatch(row, self._gh())
        assert result == ""

    def test_routes_issue(self):
        mod = _load_blame_walk()
        row = {"issue_id": "ISSUE#1", "source_platform": "geth"}
        assert mod.dispatch(row, self._gh()) == ""

    def test_routes_changelog(self):
        mod = _load_blame_walk()
        row = {"issue_id": "CHANGELOG#abc123def456abcd", "source_platform": "geth"}
        assert mod.dispatch(row, self._gh()) == ""

    def test_routes_release(self):
        mod = _load_blame_walk()
        row = {"issue_id": "RELEASE#v1.0.0#abcd1234", "source_platform": "geth"}
        assert mod.dispatch(row, self._gh()) == ""

    def test_routes_commit(self):
        mod = _load_blame_walk()
        row = {"issue_id": "COMMIT#abcdef123456", "source_platform": "geth", "source_url": ""}
        assert mod.dispatch(row, self._gh()) == ""

    def test_routes_ghsa(self):
        mod = _load_blame_walk()
        row = {"issue_id": "GHSA-aaaa-bbbb-cccc", "source_platform": "geth"}
        assert mod.dispatch(row, self._gh()) == ""

    def test_unknown_prefix_returns_empty(self):
        mod = _load_blame_walk()
        row = {"issue_id": "WEIRD#something", "source_platform": "geth"}
        assert mod.dispatch(row, self._gh()) == ""

    def test_exception_in_resolver_returns_empty(self):
        """A resolver that raises must not propagate — dispatch catches all."""
        mod = _load_blame_walk()

        def exploding_gh(path: str):
            raise RuntimeError("simulated API failure")

        row = {"issue_id": "PR#1", "source_platform": "geth"}
        # Should not raise
        result = mod.dispatch(row, exploding_gh)
        assert result == ""

    def test_routes_correctly_with_resolvable_pr(self):
        """dispatch correctly calls resolve_pr and returns the parent SHA."""
        mod = _load_blame_walk()
        gh = _make_gh(PR_PAYLOADS)
        row = {"issue_id": "PR#1234", "source_platform": "geth"}
        result = mod.dispatch(row, gh)
        assert result == _PARENT_SHA


# ---------------------------------------------------------------------------
# walk() round-trip test
# ---------------------------------------------------------------------------

@pytest.fixture
def fixture_parquet(tmp_path: Path) -> Path:
    """Create a 5-row fixture parquet with mixed issue_id types."""
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows = [
        {
            "id": "geth:ethereum-go-ethereum:PR#1234",
            "source_platform": "geth",
            "contest": "ethereum-go-ethereum",
            "issue_id": "PR#1234",
            "severity": "High",
            "title": "Test PR fix",
            "description": "A vulnerability fixed via PR",
            "source_url": "https://github.com/ethereum/go-ethereum/pull/1234",
            "introduced_in_commit": "",
            "domain": "ethereum",
            "scraped_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": "geth:ethereum-go-ethereum:RELEASE#v1.14.0#abcd1234",
            "source_platform": "geth",
            "contest": "ethereum-go-ethereum",
            "issue_id": "RELEASE#v1.14.0#abcd1234",
            "severity": "Medium",
            "title": "Test release fix",
            "description": "A vulnerability fixed in a release",
            "source_url": "https://github.com/ethereum/go-ethereum/releases/tag/v1.14.0",
            "introduced_in_commit": "",
            "domain": "ethereum",
            "scraped_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": f"geth:ethereum-go-ethereum:COMMIT#{'a' * 12}",
            "source_platform": "geth",
            "contest": "ethereum-go-ethereum",
            "issue_id": f"COMMIT#{'a' * 12}",
            "severity": "High",
            "title": "Test commit fix",
            "description": "A vulnerability fixed in a specific commit",
            "source_url": f"https://github.com/ethereum/go-ethereum/commit/{'a' * 40}",
            "introduced_in_commit": "",
            "domain": "ethereum",
            "scraped_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": "geth:ethereum-go-ethereum:ISSUE#42",
            "source_platform": "geth",
            "contest": "ethereum-go-ethereum",
            "issue_id": "ISSUE#42",
            "severity": "Low",
            "title": "Test issue",
            "description": "An issue that stays empty in v1",
            "source_url": "https://github.com/ethereum/go-ethereum/issues/42",
            "introduced_in_commit": "",
            "domain": "ethereum",
            "scraped_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": "geth:ethereum-go-ethereum:CHANGELOG#abcdef1234567890",
            "source_platform": "geth",
            "contest": "ethereum-go-ethereum",
            "issue_id": "CHANGELOG#abcdef1234567890",
            "severity": "Low",
            "title": "Test changelog entry",
            "description": "A changelog row that stays empty in v1",
            "source_url": "",
            "introduced_in_commit": "",
            "domain": "ethereum",
            "scraped_at": "2026-01-01T00:00:00Z",
        },
    ]

    df = pd.DataFrame(rows)
    out = tmp_path / "fixture.parquet"
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, out, compression="zstd")
    return out


def test_walk_round_trip(fixture_parquet: Path, tmp_path: Path):
    """walk() must:
    - Produce output with the SAME columns as input
    - Populate introduced_in_commit for resolvable rows
    - Leave "" for ISSUE# and CHANGELOG# (v1 stubs)
    - Return manifest with correct counts
    """
    import pandas as pd
    import pyarrow.parquet as pq

    mod = _load_blame_walk()

    all_payloads = {**PR_PAYLOADS, **RELEASE_PAYLOADS, **COMMIT_PAYLOADS}
    gh = _make_gh(all_payloads)

    out_path = tmp_path / "out.parquet"
    manifest = mod.walk(fixture_parquet, out_path, fetcher=gh)

    assert out_path.exists()

    # Same columns
    df_in = pd.read_parquet(fixture_parquet)
    df_out = pd.read_parquet(out_path)
    assert set(df_in.columns) == set(df_out.columns)
    assert len(df_out) == len(df_in)

    # Manifest shape
    assert "n_rows" in manifest
    assert "n_resolved" in manifest
    assert "coverage_pct" in manifest
    assert "by_source" in manifest
    assert "failed_samples" in manifest
    assert "started_at" in manifest
    assert "ended_at" in manifest

    assert manifest["n_rows"] == 5

    # PR, RELEASE, COMMIT rows should be resolved
    pr_row = df_out[df_out["issue_id"] == "PR#1234"].iloc[0]
    assert pr_row["introduced_in_commit"] == _PARENT_SHA

    release_row = df_out[df_out["issue_id"] == "RELEASE#v1.14.0#abcd1234"].iloc[0]
    assert release_row["introduced_in_commit"] == _TAG_PARENT_SHA

    commit_row = df_out[df_out["issue_id"].str.startswith("COMMIT#")].iloc[0]
    assert commit_row["introduced_in_commit"] == _FULL_COMMIT_PARENT

    # ISSUE# and CHANGELOG# remain ""
    issue_row = df_out[df_out["issue_id"] == "ISSUE#42"].iloc[0]
    assert issue_row["introduced_in_commit"] == ""

    changelog_row = df_out[df_out["issue_id"] == "CHANGELOG#abcdef1234567890"].iloc[0]
    assert changelog_row["introduced_in_commit"] == ""

    # n_resolved should be 3 (PR + RELEASE + COMMIT)
    assert manifest["n_resolved"] == 3


def test_walk_max_rows(fixture_parquet: Path, tmp_path: Path):
    """max_rows cap limits processed rows."""
    mod = _load_blame_walk()
    gh = _make_gh({})
    out_path = tmp_path / "out.parquet"
    manifest = mod.walk(fixture_parquet, out_path, max_rows=2, fetcher=gh)
    assert manifest["n_rows"] == 2


def test_walk_manifest_by_source(fixture_parquet: Path, tmp_path: Path):
    """by_source tracks counts per issue_id prefix."""
    mod = _load_blame_walk()
    gh = _make_gh({})
    out_path = tmp_path / "out.parquet"
    manifest = mod.walk(fixture_parquet, out_path, fetcher=gh)
    by_source = manifest["by_source"]
    assert by_source.get("PR") == 1
    assert by_source.get("RELEASE") == 1
    assert by_source.get("COMMIT") == 1
    assert by_source.get("ISSUE") == 1
    assert by_source.get("CHANGELOG") == 1


def test_walk_failed_samples(fixture_parquet: Path, tmp_path: Path):
    """failed_samples captures row ids where resolution returned ""."""
    mod = _load_blame_walk()
    gh = _make_gh({})  # all 404s — everything returns ""
    out_path = tmp_path / "out.parquet"
    manifest = mod.walk(fixture_parquet, out_path, fetcher=gh)
    # All 5 rows failed (404 everywhere)
    assert manifest["n_resolved"] == 0
    assert len(manifest["failed_samples"]) <= 10
    assert "PR#1234" in manifest["failed_samples"]


# ---------------------------------------------------------------------------
# Cache test: same (repo, sha) lookup hit twice → only one gh call
# ---------------------------------------------------------------------------

def test_walk_cache_deduplicates_gh_calls(tmp_path: Path):
    """Two rows with the same PR number → same merge_commit_sha → one
    gh call for the commit lookup (the second is served from cache)."""
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    mod = _load_blame_walk()

    # Two rows for the same PR (e.g. duplicate after dedup failure upstream)
    rows = [
        {
            "id": "geth:ethereum-go-ethereum:PR#1234-a",
            "source_platform": "geth",
            "contest": "ethereum-go-ethereum",
            "issue_id": "PR#1234",
            "severity": "High",
            "title": "First",
            "description": "d",
            "source_url": "",
            "introduced_in_commit": "",
            "domain": "ethereum",
            "scraped_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": "geth:ethereum-go-ethereum:PR#1234-b",
            "source_platform": "geth",
            "contest": "ethereum-go-ethereum",
            "issue_id": "PR#1234",
            "severity": "Medium",
            "title": "Second",
            "description": "d",
            "source_url": "",
            "introduced_in_commit": "",
            "domain": "ethereum",
            "scraped_at": "2026-01-01T00:00:00Z",
        },
    ]

    df = pd.DataFrame(rows)
    in_path = tmp_path / "in.parquet"
    out_path = tmp_path / "out.parquet"
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), in_path, compression="zstd")

    call_counts: dict[str, int] = {}

    def counting_gh(path: str):
        call_counts[path] = call_counts.get(path, 0) + 1
        return PR_PAYLOADS.get(path)

    mod.walk(in_path, out_path, fetcher=counting_gh)

    # The commit lookup for _MERGE_SHA should appear at most once
    commit_path = f"repos/ethereum/go-ethereum/commits/{_MERGE_SHA}"
    assert call_counts.get(commit_path, 0) <= 1

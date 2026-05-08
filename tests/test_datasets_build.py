"""Tests for `scripts/datasets/build_derived.py`.

Verify:
  1. Normalization handles the canonical csv/similar_audit_findings.csv shape.
  2. Code4rena URLs are synthesized; other platforms left blank.
  3. Severity / platform filters work.
  4. Duplicate `id`s are deduped, last write wins.
  5. Output parquet is readable + has the documented schema.

These tests gate on the optional `datasets` dep group; they skip cleanly
when those deps are absent so a base `uv sync` (no extras) still passes.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "build_derived.py"

# Skip the whole module when the optional deps aren't installed.
_required = ("pandas", "pyarrow")
_missing = [m for m in _required if importlib.util.find_spec(m) is None]
if _missing:
    pytest.skip(
        f"missing optional deps {_missing}; install with `uv sync --group datasets`",
        allow_module_level=True,
    )


def _load_build_module():
    spec = importlib.util.spec_from_file_location("speca_build_derived", BUILD_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["speca_build_derived"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fixture_csv(tmp_path: Path) -> Path:
    """A tiny CSV mirroring `csv/similar_audit_findings.csv`'s schema."""
    p = tmp_path / "fixture.csv"
    # Force utf-8 — the fixture body contains a U+2026 ellipsis; without
    # this Python falls back to the system locale (cp932 on Japanese
    # Windows) and writes bytes that build_derived's utf-8 reader rejects.
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "contest", "issue_id", "severity", "title", "description"])
        w.writerow([
            "code4rena", "2022-01-behodler-findings", "#102", "Medium",
            "Calling generateFLNQuote twice prevents migration",
            "# Handle\n\ncamden\n\n# Vulnerability details\n…",
        ])
        w.writerow([
            "sherlock", "12-redacted-cargo", "23", "High",
            "Reentrancy in withdraw()",
            "When the user calls withdraw, …",
        ])
        w.writerow([
            "codehawks", "2024-08-bracket", "M-04", "Low",
            "Off-by-one in iteration bound",
            "Loop terminates one iteration early because …",
        ])
        # Duplicate of row 1 — should be deduped.
        w.writerow([
            "code4rena", "2022-01-behodler-findings", "#102", "Medium",
            "DUPLICATE row that should drop",
            "duplicate body",
        ])
    return p


def test_normalize_synthesizes_code4rena_url():
    mod = _load_build_module()
    row = {
        "source": "code4rena",
        "contest": "2022-01-behodler-findings",
        "issue_id": "#102",
        "severity": "medium",
        "title": "x",
        "description": "y",
    }
    out = mod.normalize_row(row, domain="defi", scraped_at="2026-01-01T00:00:00Z")
    assert out["source_url"] == "https://github.com/code-423n4/2022-01-behodler-findings/issues/102"
    assert out["severity"] == "Medium"
    assert out["id"] == "code4rena:2022-01-behodler-findings:102"


def test_normalize_skips_url_for_sherlock():
    mod = _load_build_module()
    row = {
        "source": "sherlock", "contest": "c", "issue_id": "1",
        "severity": "High", "title": "t", "description": "d",
    }
    out = mod.normalize_row(row, domain="defi", scraped_at="2026-01-01T00:00:00Z")
    assert out["source_url"] == ""


def test_normalize_drops_empty_rows():
    mod = _load_build_module()
    row = {"source": "code4rena", "contest": "c", "issue_id": "1",
           "severity": "Low", "title": "", "description": ""}
    assert mod.normalize_row(row, domain="defi", scraped_at="t") is None


def test_normalize_uses_description_excerpt_when_description_missing():
    """past_defi_patterns / chainlink_v2 CSVs ship `description_excerpt`
    instead of `description`; the normalizer should fall back to it so
    those sources can union with similar_audit_findings.csv."""
    mod = _load_build_module()
    row = {
        "source": "code4rena", "contest": "2024-01-foo", "issue_id": "5",
        "severity": "High", "title": "T",
        "description_excerpt": "An excerpted body...",
    }
    out = mod.normalize_row(row, domain="defi", scraped_at="t")
    assert out is not None
    assert out["description"] == "An excerpted body..."

    # If both are present, `description` wins (it's the canonical full text).
    row2 = dict(row, description="full body")
    out2 = mod.normalize_row(row2, domain="defi", scraped_at="t")
    assert out2["description"] == "full body"


def test_build_round_trip(fixture_csv: Path, tmp_path: Path):
    import pyarrow.parquet as pq
    mod = _load_build_module()

    manifest = mod.build(
        domain="defi",
        sources=[str(fixture_csv)],
        out_dir=tmp_path,
    )
    assert manifest["domain"] == "defi"
    assert manifest["n_rows"] == 3, "duplicate row should have been deduped"
    assert manifest["rows_by_platform"] == {"code4rena": 1, "sherlock": 1, "codehawks": 1}

    parquet = tmp_path / "defi" / "train.parquet"
    assert parquet.exists()
    table = pq.read_table(parquet)
    expected_cols = {
        "id", "source_platform", "contest", "issue_id", "severity",
        "title", "description", "source_url",
        # Phase B replay column for ethereum past-fixes; empty string for
        # defi rows but always present so the parquet schema is stable.
        "introduced_in_commit",
        "domain", "scraped_at",
    }
    assert set(table.column_names) == expected_cols
    assert table.num_rows == 3
    # introduced_in_commit defaults to "" for defi sources (no provenance column).
    df = table.to_pandas()
    assert (df["introduced_in_commit"] == "").all()

    # Manifest is on disk too.
    on_disk = json.loads((tmp_path / "defi" / "manifest.json").read_text())
    assert on_disk["n_rows"] == 3


def test_build_filter_platforms(fixture_csv: Path, tmp_path: Path):
    mod = _load_build_module()
    manifest = mod.build(
        domain="defi",
        sources=[str(fixture_csv)],
        out_dir=tmp_path,
        filter_platforms="sherlock",
    )
    assert manifest["n_rows"] == 1
    assert manifest["rows_by_platform"] == {"sherlock": 1}


def test_build_severity_filter(fixture_csv: Path, tmp_path: Path):
    mod = _load_build_module()
    manifest = mod.build(
        domain="defi",
        sources=[str(fixture_csv)],
        out_dir=tmp_path,
        severity_filter="high",
    )
    assert manifest["n_rows"] == 1
    assert manifest["rows_by_severity"] == {"High": 1}

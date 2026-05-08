"""Render-only tests for `scripts/datasets/publish_hf.py` — no network.

The push path is exercised in CI under `.github/workflows/datasets-publish.yml`
with `HF_TOKEN`; here we just verify:
  1. The dataset card template renders against a fully-populated manifest.
  2. The size_categories bucket logic is correct at the boundary.
  3. `--dry-run` exits 0 and emits the expected stdout markers.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLISH_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "publish_hf.py"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "build_derived.py"

_required = ("jinja2", "pandas", "pyarrow")
_missing = [m for m in _required if importlib.util.find_spec(m) is None]
if _missing:
    pytest.skip(
        f"missing optional deps {_missing}; install with `uv sync --group datasets`",
        allow_module_level=True,
    )


def _load_publish_module():
    spec = importlib.util.spec_from_file_location("speca_publish_hf", PUBLISH_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["speca_publish_hf"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_size_category_buckets():
    mod = _load_publish_module()
    assert mod.size_category(0) == "n<1K"
    assert mod.size_category(999) == "n<1K"
    assert mod.size_category(1_000) == "1K<n<10K"
    assert mod.size_category(9_999) == "1K<n<10K"
    assert mod.size_category(10_000) == "10K<n<100K"
    assert mod.size_category(100_000) == "100K<n<1M"
    assert mod.size_category(2_000_000) == "1M<n<10M"
    assert mod.size_category(20_000_000) == "10M<n<100M"
    assert mod.size_category(2_000_000_000) == "n>1B"


def test_render_card_includes_provenance():
    mod = _load_publish_module()
    manifest = {
        "domain": "defi",
        "n_rows": 3909,
        "parquet_bytes": 18_300_000,
        "scraped_at": "2026-05-07T00:00:00Z",
        "speca_commit": "deadbeef",
        "rows_by_platform": {"code4rena": 3570, "sherlock": 263, "codehawks": 76},
        "rows_by_severity": {"High": 1299, "Medium": 2610},
        "parquet_path": "data/train.parquet",
    }
    card = mod.render_card(manifest, repo_id="NyxFoundation/defi-audit-findings")

    # YAML frontmatter
    assert card.startswith("---\n")
    assert "license: mit" in card
    # size_categories tag picks the right bucket for ~3.9k rows
    assert "1K<n<10K" in card
    # Per-platform stats rendered
    assert "| `code4rena` | 3570 |" in card
    assert "| `sherlock` | 263 |" in card
    # Provenance section + repo id propagated
    assert "Code4rena" in card and "Sherlock" in card and "CodeHawks" in card
    assert "NyxFoundation/defi-audit-findings" in card
    # Build details bound to the manifest
    assert "deadbeef" in card
    assert "3909" in card


def test_dry_run_cli_round_trip(tmp_path: Path):
    """End-to-end: build_derived → publish_hf --dry-run, no network."""
    csv_path = tmp_path / "fixture.csv"
    csv_path.write_text(
        "source,contest,issue_id,severity,title,description\n"
        "code4rena,2022-01-foo,#1,High,Title A,Desc A\n"
        "sherlock,12-bar,2,Medium,Title B,Desc B\n"
    )

    out_dir = tmp_path / "out"
    subprocess.run(
        [
            sys.executable, str(BUILD_SCRIPT),
            "--domain", "defi",
            "--source", str(csv_path),
            "--out-dir", str(out_dir),
        ],
        check=True,
        capture_output=True,
    )

    src = out_dir / "defi"
    result = subprocess.run(
        [
            sys.executable, str(PUBLISH_SCRIPT),
            "--src", str(src),
            "--repo", "NyxFoundation/defi-audit-findings",
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "[dry-run] would push:" in result.stdout
    assert "data/train.parquet" in result.stdout
    assert "README.md" in result.stdout
    # Source dir must NOT be polluted with the rendered README — we stage
    # into a tempdir instead. Regression guard for issue #34 review.
    assert not (src / "README.md").exists(), "src must stay read-only on dry-run"

    # Manifest still valid JSON.
    json.loads((src / "manifest.json").read_text())

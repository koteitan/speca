"""Render-only tests for `scripts/datasets/publish_hf.py` — no network.

The push path is exercised in CI under `.github/workflows/datasets-publish.yml`
with `HF_TOKEN`; here we just verify:
  1. The dataset card template renders (it is now global / domain-agnostic
     and only takes `repo_id`).
  2. `--dry-run` exits 0, prints the staged tree, and leaves --src clean.
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


def test_render_card_is_global_and_uses_repo_id():
    """Card content describes the project; only `repo_id` is templated.
    No per-domain stats — those live in <domain>/manifest.json."""
    mod = _load_publish_module()
    card = mod.render_card(repo_id="NyxFoundation/vulnerability-reports")

    # YAML frontmatter
    assert card.startswith("---\n")
    assert 'license: mit' in card
    assert 'pretty_name: "SPECA Vulnerability Reports"' in card
    # repo_id propagates
    assert 'NyxFoundation/vulnerability-reports' in card
    # Provenance covers all three platforms
    assert "Code4rena" in card and "Sherlock" in card and "CodeHawks" in card
    # The card mentions `manifest.json` since per-domain build details
    # live there, not in the global card.
    assert "manifest.json" in card


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
    # Build now writes train.parquet directly under the domain dir
    # (no `data/` subdir), mirroring the HF target layout.
    assert (src / "train.parquet").exists()
    assert (src / "manifest.json").exists()

    result = subprocess.run(
        [
            sys.executable, str(PUBLISH_SCRIPT),
            "--src", str(src),
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "[dry-run] would push:" in result.stdout
    # Staged paths reflect the HF folder-per-config layout.
    assert "defi/train.parquet" in result.stdout
    assert "defi/manifest.json" in result.stdout
    assert "README.md" in result.stdout
    assert "config: defi" in result.stdout
    # Source dir must NOT be polluted with the rendered README.
    assert not (src / "README.md").exists(), "src must stay read-only on dry-run"

    # Manifest still valid JSON.
    json.loads((src / "manifest.json").read_text())

"""Tests for `scripts/datasets/load.py` — both branches.

  1. Local parquet path: read a fixture parquet, expect schema + alias.
  2. HF path: monkeypatch `datasets.load_dataset` to return a fake dataset
     and assert the resolved repo_id and shape.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOAD_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "load.py"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "build_derived.py"

_required = ("pandas", "pyarrow")
_missing = [m for m in _required if importlib.util.find_spec(m) is None]
if _missing:
    pytest.skip(
        f"missing optional deps {_missing}; install with `uv sync --group datasets`",
        allow_module_level=True,
    )


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def fixture_parquet(tmp_path: Path) -> Path:
    """Build a small parquet via build_derived against a tiny CSV."""
    import csv as _csv
    csv_path = tmp_path / "fixture.csv"
    with csv_path.open("w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["source", "contest", "issue_id", "severity", "title", "description"])
        w.writerow(["code4rena", "2024-01-foo", "#1", "High", "T1", "D1"])
        w.writerow(["sherlock", "12-bar", "2", "Medium", "T2", "D2"])

    build = _load_module("speca_build_for_load", BUILD_SCRIPT)
    build.build(domain="defi", sources=[str(csv_path)], out_dir=tmp_path)
    return tmp_path / "defi" / "train.parquet"


def test_load_local_parquet_with_compat_alias(fixture_parquet: Path):
    load = _load_module("speca_load_local", LOAD_SCRIPT)
    df = load.load_findings(domain="defi", local_parquet=fixture_parquet)
    assert len(df) == 2
    assert "source_platform" in df.columns
    assert "source" in df.columns, "compat alias must be present by default"
    # Alias is a copy, not a rename.
    assert (df["source"] == df["source_platform"]).all()


def test_load_local_parquet_without_alias(fixture_parquet: Path):
    load = _load_module("speca_load_no_alias", LOAD_SCRIPT)
    df = load.load_findings(
        domain="defi", local_parquet=fixture_parquet, add_compat_aliases=False
    )
    assert "source_platform" in df.columns
    assert "source" not in df.columns


def test_load_hf_path_monkeypatch(monkeypatch: pytest.MonkeyPatch):
    """Force the HF branch by passing local_parquet=None and stubbing
    `datasets.load_dataset` so no network is touched."""
    load = _load_module("speca_load_hf", LOAD_SCRIPT)

    captured: dict = {}

    class _FakeDataset:
        def __init__(self, df):
            self._df = df

        def to_pandas(self):
            return self._df

    def fake_load_dataset(repo_id, name, split, revision):
        import pandas as pd

        captured["repo_id"] = repo_id
        captured["name"] = name
        captured["split"] = split
        captured["revision"] = revision
        return _FakeDataset(
            pd.DataFrame(
                {
                    "id": ["x"],
                    "source_platform": ["sherlock"],
                    "contest": ["c"],
                    "issue_id": ["1"],
                    "severity": ["High"],
                    "title": ["t"],
                    "description": ["d"],
                    "source_url": [""],
                    "domain": ["defi"],
                    "scraped_at": ["2026-01-01T00:00:00Z"],
                }
            )
        )

    # Inject a fake `datasets` module so `from datasets import load_dataset`
    # inside load_findings() picks up our stub.
    import types

    fake_mod = types.ModuleType("datasets")
    fake_mod.load_dataset = fake_load_dataset
    monkeypatch.setitem(sys.modules, "datasets", fake_mod)

    df = load.load_findings(domain="defi")
    assert len(df) == 1
    assert captured["repo_id"] == "NyxFoundation/vulnerability-reports"
    assert captured["name"] == "defi", "domain must be passed as the HF config name"
    assert captured["split"] == "train"
    assert captured["revision"] == "main"
    assert "source" in df.columns  # alias still applied


def test_load_hf_explicit_repo(monkeypatch: pytest.MonkeyPatch):
    load = _load_module("speca_load_hf_explicit", LOAD_SCRIPT)

    captured = {}

    def fake_load_dataset(repo_id, name, split, revision):
        import pandas as pd

        captured["repo_id"] = repo_id
        captured["name"] = name
        return type(
            "F", (), {"to_pandas": lambda self: pd.DataFrame({"source_platform": []})}
        )()

    import types

    fake_mod = types.ModuleType("datasets")
    fake_mod.load_dataset = fake_load_dataset
    monkeypatch.setitem(sys.modules, "datasets", fake_mod)

    load.load_findings(domain="lending", repo_id="custom/repo")
    assert captured["repo_id"] == "custom/repo"
    assert captured["name"] == "lending"

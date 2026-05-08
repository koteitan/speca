"""Tests for the ethereum past-fix path through `build_derived.py`.

Covers issue #2 Phase A wiring:
  1. The ethereum past-fix CSV schema (source = client slug,
     introduced_in_commit provenance column) round-trips through
     build_derived without losing the provenance column.
  2. `--filter-platforms ''` (empty) disables the platform allow-list,
     which is required because the 11 client slugs aren't in the defi
     `PLATFORMS` enum.
  3. The published parquet lands at `<out>/ethereum/`, sibling to
     `<out>/defi/`, so a downstream `publish_hf` call only touches
     the ethereum config.
  4. The defi default filter rejects ethereum rows — guard so that an
     accidental `--filter-platforms code4rena,sherlock,codehawks` on an
     ethereum CSV doesn't silently produce an empty parquet.
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

_required = ("pandas", "pyarrow")
_missing = [m for m in _required if importlib.util.find_spec(m) is None]
if _missing:
    pytest.skip(
        f"missing optional deps {_missing}; install with `uv sync --group datasets`",
        allow_module_level=True,
    )


def _load_build_module():
    spec = importlib.util.spec_from_file_location("speca_build_eth", BUILD_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["speca_build_eth"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ethereum_csv(tmp_path: Path) -> Path:
    """A tiny ethereum past-fix CSV mirroring what the Phase A crawler
    will emit under benchmarks/data/ethereum_past_fixes/."""
    p = tmp_path / "eth_past_fixes.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "source", "contest", "issue_id", "severity", "title", "description",
            "source_url", "introduced_in_commit",
        ])
        w.writerow([
            "geth", "ethereum/go-ethereum", "27530", "High",
            "DoS via crafted block",
            "Specially-crafted block triggers...",
            "https://github.com/ethereum/go-ethereum/pull/27530",
            "1a2b3c4d5e6f7890abcdef1234567890abcdef12",
        ])
        w.writerow([
            "lighthouse", "sigp/lighthouse", "4801", "Medium",
            "Slot import race",
            "Beacon node accepts a duplicate slot...",
            "https://github.com/sigp/lighthouse/pull/4801",
            "feedfacecafebeef0000111122223333deadbeef",
        ])
        w.writerow([
            "prysm", "prysmaticlabs/prysm", "13123", "Low",
            "Verbose log leak",
            "Stack trace leaks peer multiaddr...",
            "https://github.com/prysmaticlabs/prysm/pull/13123",
            "abcdef0123456789abcdef0123456789abcdef01",
        ])
    return p


def test_eth_clients_constant_lists_eleven_in_scope_clients():
    """Sanity check the constant matches issue #2's scope table — if
    Ethereum bug-bounty drops or adds a client, this catches the drift."""
    mod = _load_build_module()
    assert set(mod.ETH_CLIENTS) == {
        "geth", "nethermind", "besu", "erigon", "reth",
        "lighthouse", "lodestar", "nimbus", "prysm", "teku", "grandine",
    }
    assert len(mod.ETH_CLIENTS) == 11


def test_normalize_preserves_introduced_in_commit():
    mod = _load_build_module()
    row = {
        "source": "geth",
        "contest": "ethereum/go-ethereum",
        "issue_id": "27530",
        "severity": "High",
        "title": "T",
        "description": "D",
        "source_url": "https://github.com/ethereum/go-ethereum/pull/27530",
        "introduced_in_commit": "1a2b3c4d5e6f7890abcdef1234567890abcdef12",
    }
    out = mod.normalize_row(row, domain="ethereum", scraped_at="2026-05-08T00:00:00Z")
    assert out is not None
    assert out["source_platform"] == "geth"
    assert out["introduced_in_commit"] == "1a2b3c4d5e6f7890abcdef1234567890abcdef12"
    # Slugify keeps the `/` since it's not in the slug-safe charset → '-'.
    assert out["contest"] == "ethereum-go-ethereum"
    assert out["id"] == "geth:ethereum-go-ethereum:27530"


def test_normalize_defaults_introduced_in_commit_to_empty():
    """Defi rows lack the column; passthrough must default to '' so the
    parquet schema is uniform across configs."""
    mod = _load_build_module()
    row = {
        "source": "code4rena", "contest": "c", "issue_id": "1",
        "severity": "High", "title": "t", "description": "d",
    }
    out = mod.normalize_row(row, domain="defi", scraped_at="t")
    assert out is not None
    assert out["introduced_in_commit"] == ""


def test_build_ethereum_round_trip(ethereum_csv: Path, tmp_path: Path):
    import pyarrow.parquet as pq
    mod = _load_build_module()

    manifest = mod.build(
        domain="ethereum",
        sources=[str(ethereum_csv)],
        out_dir=tmp_path,
        # Empty filter — ethereum's source_platform values aren't in
        # the defi PLATFORMS enum, so any allow-list would drop them.
        filter_platforms="",
    )

    assert manifest["domain"] == "ethereum"
    assert manifest["n_rows"] == 3
    assert manifest["rows_by_platform"] == {"geth": 1, "lighthouse": 1, "prysm": 1}
    # platforms_included is empty when filtering is disabled. Consumers
    # read `rows_by_platform` to see what actually landed.
    assert manifest["platforms_included"] == []

    parquet = tmp_path / "ethereum" / "train.parquet"
    assert parquet.exists()
    table = pq.read_table(parquet)
    assert "introduced_in_commit" in table.column_names

    df = table.to_pandas().sort_values("source_platform").reset_index(drop=True)
    assert df["introduced_in_commit"].iloc[0] == "1a2b3c4d5e6f7890abcdef1234567890abcdef12"
    assert df["domain"].tolist() == ["ethereum"] * 3

    # Manifest is on disk too.
    on_disk = json.loads((tmp_path / "ethereum" / "manifest.json").read_text())
    assert on_disk["n_rows"] == 3


def test_build_ethereum_with_defi_filter_drops_everything(
    ethereum_csv: Path, tmp_path: Path
):
    """If an operator forgets to clear `filter_platforms` when dispatching
    for ethereum, the build aborts (no rows after filtering) — which is
    the loudest possible failure mode and prevents an empty parquet from
    silently overwriting the live config."""
    mod = _load_build_module()
    with pytest.raises(SystemExit) as exc:
        mod.build(
            domain="ethereum",
            sources=[str(ethereum_csv)],
            out_dir=tmp_path,
            filter_platforms="code4rena,sherlock,codehawks",
        )
    assert "no rows after filtering" in str(exc.value)


def test_build_ethereum_writes_to_sibling_folder(
    ethereum_csv: Path, tmp_path: Path
):
    """Critical for the multi-config HF layout: a build of the ethereum
    domain must NOT touch any sibling defi/ folder if one already exists
    in the same out-dir from a prior run."""
    mod = _load_build_module()

    # Pretend a prior defi build already populated the out-dir.
    (tmp_path / "defi").mkdir()
    sentinel = tmp_path / "defi" / "train.parquet"
    sentinel.write_bytes(b"PRIOR-DEFI")

    mod.build(
        domain="ethereum",
        sources=[str(ethereum_csv)],
        out_dir=tmp_path,
        filter_platforms="",
    )

    # Sibling defi/ untouched.
    assert sentinel.read_bytes() == b"PRIOR-DEFI"
    # Ethereum landed.
    assert (tmp_path / "ethereum" / "train.parquet").exists()

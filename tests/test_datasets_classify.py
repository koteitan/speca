"""Tests for `scripts/datasets/classify_stride_cwe.py`.

Verify:
  1. parse_classification returns clean enum on valid input.
  2. parse_classification coerces invalid values to "Other" / "N/A".
  3. parse_classification strips markdown fences.
  4. build_prompt_for_row truncates descriptions > 2000 chars.
  5. classify(..., dry_run=True) round-trips a 3-row parquet with new columns.
  6. End-to-end: 5-row fixture parquet -> output has original schema + stride + cwe_top25.
  7. classify(..., dry_run=True) writes a manifest JSON with the correct fields.
  8. CLI invocation shape: claude -p is called with --model and --output-format stream-json.

These tests gate on the optional `datasets` dep group (pandas / pyarrow);
they skip cleanly when those deps are absent so a base `uv sync` (no extras) still passes.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CLASSIFY_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "classify_stride_cwe.py"

# Skip the whole module when the optional deps aren't installed.
_required = ("pandas", "pyarrow")
_missing = [m for m in _required if importlib.util.find_spec(m) is None]
if _missing:
    pytest.skip(
        f"missing optional deps {_missing}; install with `uv sync --group datasets`",
        allow_module_level=True,
    )


def _load_classify_module():
    spec = importlib.util.spec_from_file_location("speca_classify_stride_cwe", CLASSIFY_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["speca_classify_stride_cwe"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_classify_module()


# ---------------------------------------------------------------------------
# parse_classification tests
# ---------------------------------------------------------------------------


def test_parse_valid_input(mod):
    result = mod.parse_classification('{"stride": "Tampering", "cwe_top25": "CWE-190"}')
    assert result == {"stride": "Tampering", "cwe_top25": "CWE-190"}


def test_parse_valid_dos(mod):
    result = mod.parse_classification('{"stride": "Denial of Service", "cwe_top25": "CWE-400"}')
    assert result == {"stride": "Denial of Service", "cwe_top25": "CWE-400"}


def test_parse_coerces_invalid_stride(mod):
    result = mod.parse_classification('{"stride": "lol", "cwe_top25": "CWE-9999"}')
    assert result == {"stride": "Other", "cwe_top25": "N/A"}


def test_parse_coerces_invalid_cwe(mod):
    result = mod.parse_classification('{"stride": "Spoofing", "cwe_top25": "CWE-9999"}')
    assert result["stride"] == "Spoofing"
    assert result["cwe_top25"] == "N/A"


def test_parse_na_passthrough(mod):
    result = mod.parse_classification('{"stride": "Other", "cwe_top25": "N/A"}')
    assert result == {"stride": "Other", "cwe_top25": "N/A"}


def test_parse_strips_markdown_fences(mod):
    text = '```json\n{"stride": "Spoofing", "cwe_top25": "CWE-287"}\n```'
    result = mod.parse_classification(text)
    assert result == {"stride": "Spoofing", "cwe_top25": "CWE-287"}


def test_parse_strips_plain_fences(mod):
    text = '```\n{"stride": "Elevation of Privilege", "cwe_top25": "CWE-269"}\n```'
    result = mod.parse_classification(text)
    assert result == {"stride": "Elevation of Privilege", "cwe_top25": "CWE-269"}


def test_parse_bad_json_returns_defaults(mod):
    result = mod.parse_classification("not json at all")
    assert result == {"stride": "Other", "cwe_top25": "N/A"}


def test_parse_missing_keys_defaults(mod):
    # JSON with missing keys should not crash
    result = mod.parse_classification("{}")
    assert result["stride"] == "Other"
    assert result["cwe_top25"] == "N/A"


# ---------------------------------------------------------------------------
# build_prompt_for_row tests (replaces build_batch_request)
# ---------------------------------------------------------------------------


def test_build_prompt_for_row_truncates_description(mod):
    long_desc = "x" * 5000
    row = {"id": "geth:go-ethereum:99", "title": "T", "description": long_desc}
    prompt = mod.build_prompt_for_row(row)
    # The description in the prompt should be at most 2000 chars of 'x'
    assert "x" * 2001 not in prompt
    assert "x" * 2000 in prompt


def test_build_prompt_for_row_includes_title(mod):
    row = {"id": "geth:go-ethereum:1", "title": "DoS vuln", "description": "boom"}
    prompt = mod.build_prompt_for_row(row)
    assert "DoS vuln" in prompt
    assert "boom" in prompt


def test_build_prompt_for_row_model_id(mod):
    # MODEL_ID is claude-haiku-4-5-20251001
    assert mod.MODEL_ID == "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# classify dry-run tests
# ---------------------------------------------------------------------------


def _make_fixture_parquet(tmp_path: Path, n: int = 3) -> Path:
    """Create a minimal fixture parquet with n rows."""
    import pandas as pd

    rows = []
    for i in range(n):
        rows.append(
            {
                "id": f"geth:go-ethereum:{i}",
                "source_platform": "geth",
                "contest": "go-ethereum",
                "issue_id": str(i),
                "severity": "High",
                "title": f"Bug {i}",
                "description": f"Some vulnerability description {i}",
                "source_url": f"https://github.com/ethereum/go-ethereum/issues/{i}",
                "introduced_in_commit": "abc123",
                "domain": "ethereum",
                "scraped_at": "2026-01-01T00:00:00Z",
            }
        )
    df = pd.DataFrame(rows)
    p = tmp_path / "fixture.parquet"
    df.to_parquet(p, index=False)
    return p


def test_classify_dry_run_adds_columns(mod, tmp_path):
    parquet_in = _make_fixture_parquet(tmp_path, n=3)
    parquet_out = tmp_path / "out.parquet"

    manifest = mod.classify(parquet_in, parquet_out, dry_run=True)

    import pandas as pd

    df = pd.read_parquet(parquet_out)
    assert "stride" in df.columns
    assert "cwe_top25" in df.columns
    assert len(df) == 3
    assert all(df["stride"] == "Other")
    assert all(df["cwe_top25"] == "N/A")


def test_classify_dry_run_preserves_original_schema(mod, tmp_path):
    parquet_in = _make_fixture_parquet(tmp_path, n=3)
    parquet_out = tmp_path / "out.parquet"

    mod.classify(parquet_in, parquet_out, dry_run=True)

    import pandas as pd

    df_in = pd.read_parquet(parquet_in)
    df_out = pd.read_parquet(parquet_out)

    # All original columns must be present in output
    for col in df_in.columns:
        assert col in df_out.columns, f"missing original column: {col}"

    # Original data must be unchanged
    for col in df_in.columns:
        assert list(df_in[col]) == list(df_out[col]), f"column {col} data changed"


def test_classify_dry_run_manifest(mod, tmp_path):
    parquet_in = _make_fixture_parquet(tmp_path, n=3)
    parquet_out = tmp_path / "out.parquet"

    manifest = mod.classify(parquet_in, parquet_out, dry_run=True)

    assert manifest["n_rows"] == 3
    assert manifest["n_classified"] == 0
    assert manifest["n_failed"] == 0
    assert manifest["dry_run"] is True
    assert manifest["model"] == mod.MODEL_ID
    assert "prompt_sha" in manifest
    assert "started_at" in manifest
    assert "ended_at" in manifest


def test_classify_dry_run_writes_manifest_file(mod, tmp_path):
    parquet_in = _make_fixture_parquet(tmp_path, n=3)
    parquet_out = tmp_path / "out.parquet"
    manifest_path = tmp_path / "test_manifest.json"

    mod.classify(parquet_in, parquet_out, dry_run=True, manifest_path=manifest_path)

    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["n_rows"] == 3
    assert data["dry_run"] is True
    assert "prompt_sha" in data


def test_classify_dry_run_default_manifest_path(mod, tmp_path):
    """When manifest_path is None, manifest lands next to parquet_out."""
    parquet_in = _make_fixture_parquet(tmp_path, n=2)
    parquet_out = tmp_path / "sub" / "out.parquet"
    parquet_out.parent.mkdir(parents=True, exist_ok=True)

    mod.classify(parquet_in, parquet_out, dry_run=True)

    default_manifest = tmp_path / "sub" / "classify_stride_cwe_manifest.json"
    assert default_manifest.exists()


# ---------------------------------------------------------------------------
# End-to-end: 5-row fixture parquet
# ---------------------------------------------------------------------------


def test_e2e_dry_run_five_rows(mod, tmp_path):
    parquet_in = _make_fixture_parquet(tmp_path, n=5)
    parquet_out = tmp_path / "out5.parquet"

    manifest = mod.classify(parquet_in, parquet_out, dry_run=True)

    import pandas as pd

    df_in = pd.read_parquet(parquet_in)
    df_out = pd.read_parquet(parquet_out)

    assert len(df_out) == 5
    assert manifest["n_rows"] == 5

    original_cols = set(df_in.columns)
    new_cols = {"stride", "cwe_top25"}
    assert set(df_out.columns) == original_cols | new_cols


# ---------------------------------------------------------------------------
# CLI invocation shape test: assert claude -p is called with right flags
# ---------------------------------------------------------------------------


def test_classify_row_async_calls_claude_with_stream_json(mod, tmp_path):
    """Verify _classify_row_async passes --output-format stream-json and --model to claude."""
    import asyncio

    call_args_captured = []

    async def mock_create_subprocess_exec(*args, **kwargs):
        call_args_captured.append(list(args))
        # Return a mock process that exits successfully with valid JSON output
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.stdin = None
        result_line = json.dumps({
            "type": "result",
            "result": '{"stride": "Tampering", "cwe_top25": "CWE-190"}',
        })
        mock_proc.communicate = AsyncMock(return_value=(
            result_line.encode("utf-8"), b""
        ))
        return mock_proc

    row = {"id": "geth:go-ethereum:1", "title": "DoS", "description": "boom"}

    with patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess_exec):
        semaphore = asyncio.Semaphore(1)
        result_idx, classification = asyncio.run(
            mod._classify_row_async(row, semaphore, 0)
        )

    assert result_idx == 0
    # At least one call was made
    assert len(call_args_captured) >= 1
    # The first positional arg is the claude binary, followed by flags
    cmd = call_args_captured[0]
    cmd_str = " ".join(str(c) for c in cmd)
    assert "--output-format" in cmd_str
    assert "stream-json" in cmd_str
    assert "--model" in cmd_str
    assert mod.MODEL_ID in cmd_str

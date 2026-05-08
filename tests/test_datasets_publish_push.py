"""Tests for the network-touching path of `publish_hf.py`.

We monkeypatch `huggingface_hub.HfApi` so the test runs offline, then
assert that `push()` calls `create_repo` and `upload_folder` with the
correct arguments — in particular `revision="main"` and
`delete_patterns=["data/*"]` so stale files get pruned.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLISH_SCRIPT = REPO_ROOT / "scripts" / "datasets" / "publish_hf.py"

_required = ("jinja2", "pandas", "pyarrow")
_missing = [m for m in _required if importlib.util.find_spec(m) is None]
if _missing:
    pytest.skip(
        f"missing optional deps {_missing}; install with `uv sync --group datasets`",
        allow_module_level=True,
    )


def _load():
    spec = importlib.util.spec_from_file_location("speca_publish_push", PUBLISH_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["speca_publish_push"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def staged(tmp_path: Path) -> Path:
    """Mimic what `_stage()` produces: a temp dir with data/ + README.md."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "train.parquet").write_bytes(b"PARQUET-FAKE")
    (tmp_path / "README.md").write_text("# fake card\n")
    return tmp_path


def test_repo_id_validation_rejects_path_traversal():
    mod = _load()
    # The CLI validation lives in main(); push() trusts its caller, so we
    # exercise the regex directly.
    assert mod.REPO_RE.fullmatch("NyxFoundation/defi-audit-findings")
    assert mod.REPO_RE.fullmatch("NyxFoundation/x.y_z-1")
    assert not mod.REPO_RE.fullmatch("NyxFoundation/../foo")
    assert not mod.REPO_RE.fullmatch("NyxFoundation/x/y")
    assert not mod.REPO_RE.fullmatch("Nyx Foundation/x")
    assert not mod.REPO_RE.fullmatch("/foo")


def test_size_category_boundaries():
    mod = _load()
    cases = [
        (0, "n<1K"), (999, "n<1K"),
        (1_000, "1K<n<10K"), (9_999, "1K<n<10K"),
        (10_000, "10K<n<100K"), (99_999, "10K<n<100K"),
        (100_000, "100K<n<1M"), (999_999, "100K<n<1M"),
        (1_000_000, "1M<n<10M"), (9_999_999, "1M<n<10M"),
        (10_000_000, "10M<n<100M"),
        (100_000_000, "100M<n<1B"),
        (1_000_000_000, "n>1B"),
    ]
    for n, expected in cases:
        assert mod.size_category(n) == expected, f"n={n}"


def test_push_invokes_hf_api_correctly(monkeypatch: pytest.MonkeyPatch, staged: Path):
    mod = _load()

    calls = {"create_repo": None, "upload_folder": None}

    class _FakeApi:
        def __init__(self, token=None):
            calls["token"] = token

        def create_repo(self, repo_id, repo_type, exist_ok):
            calls["create_repo"] = {
                "repo_id": repo_id, "repo_type": repo_type, "exist_ok": exist_ok,
            }

        def upload_folder(self, folder_path, repo_id, repo_type, revision,
                          commit_message, delete_patterns):
            calls["upload_folder"] = {
                "folder_path": folder_path,
                "repo_id": repo_id,
                "repo_type": repo_type,
                "revision": revision,
                "commit_message": commit_message,
                "delete_patterns": delete_patterns,
            }
            class _CI:
                commit_url = "https://huggingface.co/datasets/x/commit/abc"
            return _CI()

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.HfApi = _FakeApi
    fake_utils = types.ModuleType("huggingface_hub.utils")

    class _FakeHfHubHTTPError(Exception):
        pass

    fake_utils.HfHubHTTPError = _FakeHfHubHTTPError
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", fake_utils)

    url = mod.push(staged, "NyxFoundation/defi-audit-findings", token="t", commit_message="msg")
    assert "abc" in url
    assert calls["create_repo"]["repo_id"] == "NyxFoundation/defi-audit-findings"
    assert calls["create_repo"]["repo_type"] == "dataset"
    assert calls["create_repo"]["exist_ok"] is True

    uf = calls["upload_folder"]
    assert uf["repo_id"] == "NyxFoundation/defi-audit-findings"
    assert uf["repo_type"] == "dataset"
    assert uf["revision"] == "main"
    assert uf["commit_message"] == "msg"
    assert uf["delete_patterns"] == ["data/*"]
    assert Path(uf["folder_path"]) == staged


def test_stage_does_not_pollute_src(tmp_path: Path):
    """Regression: --dry-run / --src must NOT write README into the source
    directory. The build_derived output is treated as read-only."""
    mod = _load()

    src = tmp_path / "defi"
    (src / "data").mkdir(parents=True)
    parquet = src / "data" / "train.parquet"
    parquet.write_bytes(b"PARQUET-FAKE")
    manifest = {"parquet_path": "data/train.parquet"}
    (src / "manifest.json").write_text(json.dumps(manifest))

    td = mod._stage(src, manifest, "card body")
    try:
        staging = Path(td.name)
        assert (staging / "README.md").read_text() == "card body"
        assert (staging / "data" / "train.parquet").exists()
        # Source is untouched.
        assert not (src / "README.md").exists(), "src/README.md must not be written"
    finally:
        td.cleanup()

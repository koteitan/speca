"""Tests for the network-touching path of `publish_hf.py`.

We monkeypatch `huggingface_hub.HfApi` so the test runs offline, then
assert that `push()` calls `create_repo` and `upload_folder` with the
correct arguments — `revision="main"` and `delete_patterns=["<domain>/*"]`
so OTHER domain folders stay intact across publishes.
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
    """Mimic what `_stage()` produces for a `defi` push: a tempdir with
    README.md at root + defi/{train.parquet,manifest.json}."""
    (tmp_path / "defi").mkdir()
    (tmp_path / "defi" / "train.parquet").write_bytes(b"PARQUET-FAKE")
    (tmp_path / "defi" / "manifest.json").write_text("{}")
    (tmp_path / "README.md").write_text("# fake card\n")
    return tmp_path


def test_repo_id_validation_rejects_path_traversal():
    mod = _load()
    assert mod.REPO_RE.fullmatch("NyxFoundation/vulnerability-reports")
    assert mod.REPO_RE.fullmatch("NyxFoundation/x.y_z-1")
    assert not mod.REPO_RE.fullmatch("NyxFoundation/../foo")
    assert not mod.REPO_RE.fullmatch("NyxFoundation/x/y")
    assert not mod.REPO_RE.fullmatch("Nyx Foundation/x")
    assert not mod.REPO_RE.fullmatch("/foo")


def test_default_repo_constant():
    mod = _load()
    assert mod.DEFAULT_REPO == "NyxFoundation/vulnerability-reports"


def test_domain_validation():
    mod = _load()
    assert mod.DOMAIN_RE.fullmatch("defi")
    assert mod.DOMAIN_RE.fullmatch("ai-agents")
    assert not mod.DOMAIN_RE.fullmatch("DeFi")
    assert not mod.DOMAIN_RE.fullmatch("--bad")
    assert not mod.DOMAIN_RE.fullmatch("foo--bar")
    assert not mod.DOMAIN_RE.fullmatch("foo_bar")


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

    url = mod.push(staged, "NyxFoundation/vulnerability-reports",
                   domain="defi", token="t", commit_message="msg")
    assert "abc" in url
    assert calls["create_repo"]["repo_id"] == "NyxFoundation/vulnerability-reports"
    assert calls["create_repo"]["repo_type"] == "dataset"

    uf = calls["upload_folder"]
    assert uf["repo_id"] == "NyxFoundation/vulnerability-reports"
    assert uf["repo_type"] == "dataset"
    assert uf["revision"] == "main"
    assert uf["commit_message"] == "msg"
    # Crucially, scoped to ONLY this domain's folder so other domains
    # under the same repo aren't deleted on a partial publish.
    assert uf["delete_patterns"] == ["defi/*"]
    assert Path(uf["folder_path"]) == staged


def test_stage_layout_mirrors_hf_repo(tmp_path: Path):
    """`_stage()` must produce <td>/README.md + <td>/<domain>/{train.parquet,manifest.json}
    so `upload_folder` lands the parquet at the correct config path."""
    mod = _load()

    src = tmp_path / "defi"
    src.mkdir(parents=True)
    parquet = src / "train.parquet"
    parquet.write_bytes(b"PARQUET-FAKE")
    manifest = {"parquet_path": "train.parquet", "domain": "defi", "scraped_at": "t"}
    (src / "manifest.json").write_text(json.dumps(manifest))

    td = mod._stage(src, manifest, "defi", "card body")
    try:
        staging = Path(td.name)
        # Global README at root.
        assert (staging / "README.md").read_text() == "card body"
        # Domain-folder layout.
        assert (staging / "defi" / "train.parquet").exists()
        assert (staging / "defi" / "manifest.json").exists()
        # Source is untouched.
        assert not (src / "README.md").exists(), "src/README.md must not be written"
    finally:
        td.cleanup()

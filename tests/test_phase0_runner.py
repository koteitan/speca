"""Tests for :mod:`scripts.orchestrator.phase0_runner`.

The Phase 0 runners are intentionally thin wrappers around subprocess and
file IO, so the test goal is to assert the *contract* (env vars, output
schema, exit codes) without ever launching a real ``claude`` CLI or
network call.

Strategy:

* Phase 0a — replace ``Phase0aRunner._runner`` with a mock that emulates
  ``claude --print`` by writing the JSON files itself and returning a
  zero-rc ``CompletedProcess``. We also assert the rendered prompt
  contains the bug bounty URL and the contract-address context line when
  applicable.
* Phase 0b — create a tmp_path with a ``.git`` directory and assert the
  breadcrumb file is written.
* Phase 0c — build a real on-disk git repo (mirrors the pattern in
  ``web/server/tests/test_workspace_manager.py``) and assert the resulting
  ``TARGET_INFO.json`` matches the Action's schema.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make ``scripts/`` importable the same way conftest.py does for the rest of
# the suite.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from orchestrator.phase0_runner import (  # noqa: E402  — sys.path mutated above
    PHASE_0A_PROMPT_TEMPLATE,
    Phase0aRunner,
    Phase0bRunner,
    Phase0cRunner,
    _build_phase_0a_prompt,
    get_phase0_runner,
    is_phase0,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> None:
    """Run ``git`` inside ``cwd`` with a hermetic identity."""

    subprocess.run(
        [
            "git",
            "-c",
            "core.longpaths=true",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            *args,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )


def _make_local_repo(tmp_path: Path) -> Path:
    """Build a tiny local git repo and return its working directory.

    We deliberately omit the bare/worktree dance from
    ``test_workspace_manager.py`` — Phase 0c only needs a single branch
    with one commit so ``git rev-parse HEAD`` and
    ``git symbolic-ref refs/remotes/origin/HEAD`` produce sensible output.
    """

    repo = tmp_path / "workspace"
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=repo)
    (repo / "README.md").write_text("test", encoding="utf-8")
    _git(["add", "."], cwd=repo)
    _git(["commit", "-m", "init"], cwd=repo)
    return repo


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip env vars that the runners look at so each test starts clean."""

    for key in (
        "BUG_BOUNTY_URL",
        "CONTRACT_ADDRESSES",
        "SPECA_TARGET_WORKSPACE",
        "TARGET_REPO",
        "TARGET_REF",
        "SPECA_OUTPUT_DIR",
    ):
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# Factory dispatch
# ---------------------------------------------------------------------------


def test_is_phase0_recognises_known_ids() -> None:
    assert is_phase0("0a")
    assert is_phase0("0b")
    assert is_phase0("0c")
    assert not is_phase0("01a")
    assert not is_phase0("03")


def test_get_phase0_runner_dispatches(tmp_path: Path) -> None:
    assert isinstance(get_phase0_runner("0a", output_dir=tmp_path), Phase0aRunner)
    assert isinstance(get_phase0_runner("0b", output_dir=tmp_path), Phase0bRunner)
    assert isinstance(get_phase0_runner("0c", output_dir=tmp_path), Phase0cRunner)


# ---------------------------------------------------------------------------
# Phase 0a — prompt rendering + claude CLI dispatch
# ---------------------------------------------------------------------------


def test_phase_0a_prompt_template_contains_schema_keys() -> None:
    """Sanity check: the prompt must request every key the Action defines."""

    for key in (
        "program_url",
        "program_name",
        "in_scope_assets",
        "in_scope_contracts",
        "out_of_scope",
        "severity_ratings",
        "reward_range",
        "notes",
        "spec_urls",
        "keywords",
    ):
        assert key in PHASE_0A_PROMPT_TEMPLATE, f"prompt missing key {key}"


def test_phase_0a_build_prompt_inlines_url_and_addr_context(tmp_path: Path) -> None:
    prompt = _build_phase_0a_prompt(
        bug_bounty_url="https://immunefi.com/bounty/example",
        scope_path=tmp_path / "BUG_BOUNTY_SCOPE.json",
        extracted_path=tmp_path / "EXTRACTED_INPUTS.json",
        contract_addresses="0xabc, 0xdef",
    )
    assert "https://immunefi.com/bounty/example" in prompt
    assert "0xabc, 0xdef" in prompt
    assert "Additional in-scope contract addresses provided by user" in prompt


def test_phase_0a_build_prompt_omits_addr_context_when_none(tmp_path: Path) -> None:
    prompt = _build_phase_0a_prompt(
        bug_bounty_url="https://example.com",
        scope_path=tmp_path / "BUG_BOUNTY_SCOPE.json",
        extracted_path=tmp_path / "EXTRACTED_INPUTS.json",
        contract_addresses=None,
    )
    assert "Additional in-scope contract addresses provided by user" not in prompt


def test_phase_0a_missing_url_fails(
    tmp_path: Path, clean_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without BUG_BOUNTY_URL we must exit non-zero and complain on stderr."""

    runner = Phase0aRunner(output_dir=tmp_path)
    rc = runner.run()
    assert rc == 1
    err = capsys.readouterr().err
    assert "BUG_BOUNTY_URL" in err


def test_phase_0a_runs_claude_and_verifies_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_env: None,
) -> None:
    """Happy path: env set, claude writes both JSON files, rc == 0."""

    monkeypatch.setenv("BUG_BOUNTY_URL", "https://example.com/bounty")
    monkeypatch.setenv("CONTRACT_ADDRESSES", "0xdeadbeef")

    runner = Phase0aRunner(output_dir=tmp_path)
    captured_args: dict[str, object] = {}

    def fake_run(args, **kwargs):  # noqa: ANN001 — match subprocess.run signature
        captured_args["args"] = list(args)
        captured_args["kwargs"] = kwargs
        # Emulate claude writing the JSON files via its Write tool.
        runner.scope_path.write_text(
            json.dumps({"program_url": "https://example.com/bounty"}), encoding="utf-8"
        )
        runner.extracted_path.write_text(
            json.dumps({"spec_urls": "https://x", "keywords": "k1,k2"}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="ok", stderr=""
        )

    # Patch the bound staticmethods on the instance (so we don't mutate the
    # class state and leak into other tests).
    runner._runner = fake_run
    runner._which = lambda _: "/fake/claude"

    rc = runner.run()
    assert rc == 0
    # Args order is [bin, --print, --dangerously-skip-permissions].
    # The prompt itself flows through stdin (``input=``) so Windows
    # ``cmd.exe`` cannot interpret JSON angle brackets ``<asset>`` as
    # redirection. ``--dangerously-skip-permissions`` is required so the
    # model can write BUG_BOUNTY_SCOPE.json / EXTRACTED_INPUTS.json
    # without an interactive tool-permission prompt that the non-TTY
    # ``--print`` path cannot answer.
    args = captured_args["args"]
    assert args[0] == "/fake/claude"
    assert args[1] == "--print"
    assert args[2] == "--dangerously-skip-permissions"
    # Prompt is no longer in argv — should be on stdin.
    assert len(args) == 3, f"unexpected extra argv: {args!r}"
    stdin_prompt = captured_args["kwargs"].get("input", "")
    assert "https://example.com/bounty" in stdin_prompt
    assert "0xdeadbeef" in stdin_prompt
    # subprocess must be invoked with shell=False for cross-platform safety.
    assert captured_args["kwargs"].get("shell") is False
    # Files exist.
    assert runner.scope_path.is_file()
    assert runner.extracted_path.is_file()


def test_phase_0a_fails_when_claude_returns_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("BUG_BOUNTY_URL", "https://example.com/bounty")
    runner = Phase0aRunner(output_dir=tmp_path)
    runner._which = lambda _: "/fake/claude"
    runner._runner = lambda *a, **kw: subprocess.CompletedProcess(
        args=a[0], returncode=42, stdout="", stderr="boom"
    )
    rc = runner.run()
    assert rc == 42
    err = capsys.readouterr().err
    assert "boom" in err


def test_phase_0a_fails_when_claude_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("BUG_BOUNTY_URL", "https://example.com/bounty")
    runner = Phase0aRunner(output_dir=tmp_path)
    runner._which = lambda _: None  # CLI not installed
    rc = runner.run()
    assert rc == 2
    assert "claude" in capsys.readouterr().err.lower()


def test_phase_0a_fails_when_outputs_not_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_env: None,
) -> None:
    """If claude returns 0 but does not produce the JSONs, we must abort."""

    monkeypatch.setenv("BUG_BOUNTY_URL", "https://example.com/bounty")
    runner = Phase0aRunner(output_dir=tmp_path)
    runner._which = lambda _: "/fake/claude"
    runner._runner = lambda *a, **kw: subprocess.CompletedProcess(
        args=a[0], returncode=0, stdout="", stderr=""
    )
    rc = runner.run()
    assert rc == 4


# ---------------------------------------------------------------------------
# Phase 0b — workspace verification
# ---------------------------------------------------------------------------


def test_phase_0b_missing_env_fails(
    tmp_path: Path, clean_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = Phase0bRunner(output_dir=tmp_path)
    assert runner.run() == 1
    assert "SPECA_TARGET_WORKSPACE" in capsys.readouterr().err


def test_phase_0b_missing_workspace_dir_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    monkeypatch.setenv("SPECA_TARGET_WORKSPACE", str(tmp_path / "does-not-exist"))
    runner = Phase0bRunner(output_dir=tmp_path)
    assert runner.run() == 2


def test_phase_0b_workspace_without_git_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.setenv("SPECA_TARGET_WORKSPACE", str(workspace))
    runner = Phase0bRunner(output_dir=tmp_path)
    assert runner.run() == 3


def test_phase_0b_writes_breadcrumb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".git").mkdir()
    monkeypatch.setenv("SPECA_TARGET_WORKSPACE", str(workspace))

    out_dir = tmp_path / "outputs"
    runner = Phase0bRunner(output_dir=out_dir)
    assert runner.run() == 0
    breadcrumb = out_dir / ".phase0b.json"
    assert breadcrumb.is_file()
    parsed = json.loads(breadcrumb.read_text(encoding="utf-8"))
    assert parsed["workspace_path"].endswith("ws") or parsed["workspace_path"].endswith(
        os.sep + "ws"
    )
    assert "verified_at" in parsed


def test_phase_0b_accepts_git_file_form(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    """``git worktree`` workspaces have a regular file at ``.git``."""

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
    monkeypatch.setenv("SPECA_TARGET_WORKSPACE", str(workspace))
    runner = Phase0bRunner(output_dir=tmp_path)
    assert runner.run() == 0


# ---------------------------------------------------------------------------
# Phase 0c — TARGET_INFO.json generation
# ---------------------------------------------------------------------------


def test_phase_0c_missing_workspace_env_fails(
    tmp_path: Path, clean_env: None
) -> None:
    runner = Phase0cRunner(output_dir=tmp_path)
    assert runner.run() == 1


def test_phase_0c_missing_target_repo_env_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    monkeypatch.setenv("SPECA_TARGET_WORKSPACE", str(tmp_path))
    runner = Phase0cRunner(output_dir=tmp_path)
    assert runner.run() == 1


def test_phase_0c_writes_target_info_from_local_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    repo = _make_local_repo(tmp_path)
    monkeypatch.setenv("SPECA_TARGET_WORKSPACE", str(repo))
    monkeypatch.setenv("TARGET_REPO", "owner/example")
    monkeypatch.setenv("TARGET_REF", "v1.2.3")

    out_dir = tmp_path / "outputs"
    runner = Phase0cRunner(output_dir=out_dir)
    rc = runner.run()
    assert rc == 0

    target_info_path = out_dir / "TARGET_INFO.json"
    assert target_info_path.is_file()
    info = json.loads(target_info_path.read_text(encoding="utf-8"))
    # Schema parity with .github/workflows/full-audit.yml Step 0c.
    assert set(info.keys()) == {
        "target_repo",
        "target_ref",
        "target_ref_label",
        "target_commit",
        "target_commit_short",
    }
    assert info["target_repo"] == "owner/example"
    assert info["target_ref"] == "v1.2.3"
    assert info["target_ref_label"] == "v1.2.3"
    # Commit hash is 40 hex chars, short is 7+.
    assert len(info["target_commit"]) == 40
    assert info["target_commit"].startswith(info["target_commit_short"])


def test_phase_0c_default_ref_falls_back_to_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    """No TARGET_REF -> use default branch (or ``main`` fallback)."""

    repo = _make_local_repo(tmp_path)
    monkeypatch.setenv("SPECA_TARGET_WORKSPACE", str(repo))
    monkeypatch.setenv("TARGET_REPO", "owner/example")
    # TARGET_REF intentionally unset; the local repo has no `origin/HEAD`
    # symbolic ref (no remote), so the fallback path should kick in.

    runner = Phase0cRunner(output_dir=tmp_path / "outputs")
    assert runner.run() == 0
    info = json.loads((tmp_path / "outputs" / "TARGET_INFO.json").read_text())
    # main is the fallback when no symbolic-ref exists.
    assert info["target_ref"] == "main"
    assert info["target_ref_label"] == "main"

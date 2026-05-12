"""
Phase 0 Runners (0a / 0b / 0c) — Pipeline Setup

These runners reproduce the work that the CI workflow's Step 0a/0b/0c performs
inline (see .github/workflows/full-audit.yml). They are intentionally small
and synchronous because Phase 0 is one-off setup that happens before the
async batch pipeline starts.

Contract:
  * Inputs come from environment variables (BUG_BOUNTY_URL, TARGET_REPO,
    SPECA_TARGET_WORKSPACE, ...). The Web UI / CI / local CLI all pass the
    same env vars, so this layer is the single source of truth.
  * Outputs land in ``output_dir`` (defaults to the SPECA_OUTPUT_DIR root) so
    downstream phases find ``BUG_BOUNTY_SCOPE.json`` / ``TARGET_INFO.json`` /
    ``EXTRACTED_INPUTS.json`` where they expect.
  * ``run()`` returns ``0`` on success and a non-zero int on failure. We do
    *not* raise PhaseAbortError here because Phase 0 is not part of the async
    batch lifecycle that error type is wired into.

Phase 0b deliberately does NOT clone the workspace — that responsibility
lives in ``web.server.services.workspace_manager.WorkspaceManager`` (Slice
H2). Phase 0b only verifies that the path the caller pointed at really is a
git workspace.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import ClassVar


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class Phase0RunnerBase:
    """Shared scaffolding for Phase 0 runners.

    Subclasses set ``phase_id`` and implement :meth:`run`. The base resolves
    and creates ``output_dir`` so the subclasses can write outputs without
    re-implementing directory bootstrap.
    """

    phase_id: ClassVar[str] = ""

    def __init__(self, output_dir: Path | str | None = None) -> None:
        if output_dir is None:
            output_dir = os.environ.get("SPECA_OUTPUT_DIR", "outputs")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> int:  # pragma: no cover — abstract
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Phase 0a — Bug bounty scope extraction
# ---------------------------------------------------------------------------


# Mirrors .github/workflows/full-audit.yml Step 0a's `claude --print "..."`.
# The shell-escaped JSON in the YAML is transposed back to ordinary Python
# triple-string form. Keep the *schema* identical so downstream phases
# (especially 01e which consumes BUG_BOUNTY_SCOPE.json) keep working.
PHASE_0A_PROMPT_TEMPLATE = """\
Read the bug bounty program page at {bug_bounty_url} and create {scope_path} with:
{{
  "program_url": "{bug_bounty_url}",
  "program_name": "<name>",
  "in_scope_assets": ["<assets - include repos, contract addresses, and file paths>"],
  "in_scope_contracts": [{{"address": "0x...", "network": "ethereum|base|...", "name": "<if available>"}}],
  "out_of_scope": ["<excluded>"],
  "severity_ratings": "<if available>",
  "reward_range": "<if available>",
  "notes": "<special rules>"
}}
IMPORTANT: Many bug bounty programs (e.g., Sherlock, Immunefi) define scope using:
- Specific repository URLs with commit hashes
- Smart contract addresses on various networks (Ethereum, Base, Arbitrum, etc.)
- Specific file paths within repositories
Extract ALL of these. For contract addresses, include the network and contract name if available.
{addr_context}
Also extract specification URLs and keywords for Phase 01a discovery.
Write them to {extracted_path}:
{{
  "spec_urls": "<comma-separated URLs>",
  "keywords": "<comma-separated keywords>"
}}
"""


def _build_phase_0a_prompt(
    bug_bounty_url: str,
    scope_path: Path,
    extracted_path: Path,
    contract_addresses: str | None,
) -> str:
    """Render the Phase 0a prompt with the caller's run-specific inputs.

    Kept as a free function so tests can exercise the prompt construction
    without going through subprocess.
    """

    addr_context = ""
    if contract_addresses:
        addr_context = (
            f"Additional in-scope contract addresses provided by user: {contract_addresses}"
        )
    return PHASE_0A_PROMPT_TEMPLATE.format(
        bug_bounty_url=bug_bounty_url,
        scope_path=str(scope_path),
        extracted_path=str(extracted_path),
        addr_context=addr_context,
    )


class Phase0aRunner(Phase0RunnerBase):
    """Extract bug bounty scope from a program URL via ``claude --print``.

    Env contract:
      * ``BUG_BOUNTY_URL`` — required; the program page URL to read.
      * ``CONTRACT_ADDRESSES`` — optional; extra in-scope addresses (free-form
        string, passed through to the prompt).
      * ``SPECA_OUTPUT_DIR`` — optional; where to write the JSON outputs.

    Outputs (Action-compatible schema):
      * ``<output_dir>/BUG_BOUNTY_SCOPE.json``
      * ``<output_dir>/EXTRACTED_INPUTS.json``
    """

    phase_id: ClassVar[str] = "0a"

    # Injection points so tests can mock subprocess and the claude CLI lookup.
    _runner = staticmethod(subprocess.run)
    _which = staticmethod(shutil.which)

    def __init__(
        self,
        output_dir: Path | str | None = None,
        *,
        max_budget_usd: float = 0.50,
    ) -> None:
        super().__init__(output_dir)
        self.max_budget_usd = max_budget_usd

    @property
    def scope_path(self) -> Path:
        return self.output_dir / "BUG_BOUNTY_SCOPE.json"

    @property
    def extracted_path(self) -> Path:
        return self.output_dir / "EXTRACTED_INPUTS.json"

    def build_prompt(self, bug_bounty_url: str, contract_addresses: str | None) -> str:
        return _build_phase_0a_prompt(
            bug_bounty_url,
            self.scope_path,
            self.extracted_path,
            contract_addresses,
        )

    def run(self) -> int:
        bug_bounty_url = os.environ.get("BUG_BOUNTY_URL", "").strip()
        if not bug_bounty_url:
            print(
                "Phase 0a: BUG_BOUNTY_URL is required but was not set.",
                file=sys.stderr,
            )
            return 1

        contract_addresses = os.environ.get("CONTRACT_ADDRESSES", "").strip() or None
        prompt = self.build_prompt(bug_bounty_url, contract_addresses)

        # ``claude --print`` exits with a non-zero status if the CLI is
        # missing; locate it explicitly so we produce a clear error message
        # instead of letting subprocess raise FileNotFoundError mid-stream.
        claude_bin = self._which("claude")
        if not claude_bin:
            print(
                "Phase 0a: `claude` CLI not found on PATH. "
                "Install @anthropic-ai/claude-code or set CLAUDE_BIN.",
                file=sys.stderr,
            )
            return 2

        start = time.time()
        print(f"Phase 0a: scope extraction (budget cap: ${self.max_budget_usd:.2f})")
        print(f"  URL: {bug_bounty_url}")
        print(f"  Output dir: {self.output_dir}")

        # shell=False; arguments are passed as a list so quoting is the
        # subprocess module's problem, not ours. Works on Windows / WSL / Linux.
        try:
            result = self._runner(
                [claude_bin, "--print", prompt],
                capture_output=True,
                text=True,
                check=False,
                shell=False,
            )
        except OSError as exc:
            print(f"Phase 0a: failed to launch claude CLI: {exc}", file=sys.stderr)
            return 3

        duration = round(time.time() - start, 2)
        if result.returncode != 0:
            print(
                f"Phase 0a: claude exited with code {result.returncode} after {duration}s",
                file=sys.stderr,
            )
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return result.returncode

        # The Action workflow assumes claude writes the JSON files directly
        # via its Write tool. We verify they were created so the next phase
        # gets a deterministic error if the prompt drifted.
        missing = [
            str(p)
            for p in (self.scope_path, self.extracted_path)
            if not p.is_file()
        ]
        if missing:
            print(
                "Phase 0a: claude did not produce expected outputs: "
                f"{', '.join(missing)}",
                file=sys.stderr,
            )
            return 4

        print(f"Phase 0a: completed in {duration}s")
        print(f"  Scope:     {self.scope_path}")
        print(f"  Extracted: {self.extracted_path}")
        return 0


# ---------------------------------------------------------------------------
# Phase 0b — Workspace verification
# ---------------------------------------------------------------------------


class Phase0bRunner(Phase0RunnerBase):
    """Confirm that ``SPECA_TARGET_WORKSPACE`` is a real git workspace.

    Cloning is *not* our job — that belongs to
    :class:`web.server.services.workspace_manager.WorkspaceManager` (Slice
    H2). The CI workflow does the clone via ``actions/checkout``. By the time
    Phase 0b runs the workspace is expected to exist already, and our only
    contract is to fail loudly when it does not so phases 02c/03/04 don't
    have to.

    We drop a ``.phase0b.json`` breadcrumb so the Web UI can show the
    verified state alongside ``BUG_BOUNTY_SCOPE.json``.
    """

    phase_id: ClassVar[str] = "0b"

    def run(self) -> int:
        workspace = os.environ.get("SPECA_TARGET_WORKSPACE", "").strip()
        if not workspace:
            print(
                "Phase 0b: SPECA_TARGET_WORKSPACE is required but was not set.",
                file=sys.stderr,
            )
            return 1

        workspace_path = Path(workspace)
        if not workspace_path.is_dir():
            print(
                f"Phase 0b: workspace path does not exist or is not a directory: "
                f"{workspace_path}",
                file=sys.stderr,
            )
            return 2

        git_dir = workspace_path / ".git"
        # ``.git`` is usually a directory, but can be a regular file when the
        # workspace was created via ``git worktree`` — accept both shapes.
        if not (git_dir.is_dir() or git_dir.is_file()):
            print(
                f"Phase 0b: workspace is not a git repository (no .git at "
                f"{git_dir})",
                file=sys.stderr,
            )
            return 3

        breadcrumb_path = self.output_dir / ".phase0b.json"
        breadcrumb = {
            "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "workspace_path": str(workspace_path.resolve()),
        }
        breadcrumb_path.write_text(
            json.dumps(breadcrumb, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Phase 0b: verified workspace at {workspace_path}")
        print(f"  Breadcrumb: {breadcrumb_path}")
        return 0


# ---------------------------------------------------------------------------
# Phase 0c — TARGET_INFO.json generation
# ---------------------------------------------------------------------------


class Phase0cRunner(Phase0RunnerBase):
    """Write ``TARGET_INFO.json`` from the workspace's git metadata.

    Reproduces the shell snippet in ``Step 0c`` of the Action workflow. We
    invoke ``git`` via :mod:`subprocess` (``shell=False``) instead of the
    yaml's inline shell so the same code works on Windows / WSL / Linux.

    Env contract:
      * ``SPECA_TARGET_WORKSPACE`` — required; the workspace whose HEAD we
        inspect.
      * ``TARGET_REPO`` — required; the ``owner/repo`` string (passed through
        from the CI input or the Web UI form).
      * ``TARGET_REF`` — optional; the branch/tag/sha the user requested. When
        empty, we resolve the workspace's default branch via
        ``git symbolic-ref refs/remotes/origin/HEAD`` and fall back to
        ``main`` if HEAD isn't symbolic (mirrors the Action's shell logic).
    """

    phase_id: ClassVar[str] = "0c"

    _runner = staticmethod(subprocess.run)

    def _git(self, args: list[str], workspace: Path) -> subprocess.CompletedProcess[str]:
        return self._runner(
            ["git", *args],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )

    def run(self) -> int:
        workspace = os.environ.get("SPECA_TARGET_WORKSPACE", "").strip()
        if not workspace:
            print(
                "Phase 0c: SPECA_TARGET_WORKSPACE is required but was not set.",
                file=sys.stderr,
            )
            return 1
        target_repo = os.environ.get("TARGET_REPO", "").strip()
        if not target_repo:
            print(
                "Phase 0c: TARGET_REPO is required but was not set.",
                file=sys.stderr,
            )
            return 1

        workspace_path = Path(workspace)
        if not workspace_path.is_dir():
            print(
                f"Phase 0c: workspace path does not exist: {workspace_path}",
                file=sys.stderr,
            )
            return 2

        target_ref = os.environ.get("TARGET_REF", "").strip()

        # Resolve the default branch only when the user did not pin a ref.
        # Match the YAML's shell fallback chain: symbolic-ref -> "main".
        if not target_ref:
            default_branch = self._resolve_default_branch(workspace_path)
            ref_label = default_branch
        else:
            ref_label = target_ref

        commit_result = self._git(["rev-parse", "HEAD"], workspace_path)
        if commit_result.returncode != 0:
            print(
                "Phase 0c: `git rev-parse HEAD` failed in "
                f"{workspace_path}: {commit_result.stderr.strip()}",
                file=sys.stderr,
            )
            return 3
        commit = commit_result.stdout.strip()
        if not commit:
            print(
                "Phase 0c: `git rev-parse HEAD` produced no output.",
                file=sys.stderr,
            )
            return 3

        short_result = self._git(["rev-parse", "--short", "HEAD"], workspace_path)
        commit_short = short_result.stdout.strip() if short_result.returncode == 0 else commit[:7]

        info = {
            "target_repo": target_repo,
            "target_ref": ref_label,
            "target_ref_label": ref_label,
            "target_commit": commit,
            "target_commit_short": commit_short,
        }
        target_info_path = self.output_dir / "TARGET_INFO.json"
        target_info_path.write_text(
            json.dumps(info, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Phase 0c: TARGET_INFO.json written to {target_info_path}")
        for k, v in info.items():
            print(f"  {k}: {v}")
        return 0

    def _resolve_default_branch(self, workspace_path: Path) -> str:
        """Best-effort default-branch resolution matching the Action shell."""
        sym = self._git(
            ["symbolic-ref", "refs/remotes/origin/HEAD"], workspace_path
        )
        if sym.returncode == 0 and sym.stdout.strip():
            # Strip the "refs/remotes/origin/" prefix the same way ``sed``
            # does in the workflow.
            return sym.stdout.strip().rsplit("/", 1)[-1]
        return "main"


# ---------------------------------------------------------------------------
# Factory dispatch
# ---------------------------------------------------------------------------


PHASE0_RUNNERS: dict[str, type[Phase0RunnerBase]] = {
    "0a": Phase0aRunner,
    "0b": Phase0bRunner,
    "0c": Phase0cRunner,
}


def is_phase0(phase_id: str) -> bool:
    """Return True if ``phase_id`` is handled by a Phase0 runner."""
    return phase_id in PHASE0_RUNNERS


def get_phase0_runner(phase_id: str, output_dir: Path | str | None = None) -> Phase0RunnerBase:
    """Construct the appropriate Phase 0 runner for ``phase_id``."""
    cls = PHASE0_RUNNERS[phase_id]
    return cls(output_dir=output_dir)

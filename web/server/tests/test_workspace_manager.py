"""Tests for :mod:`web.server.services.workspace_manager`.

The fixtures here build a **real** local git repository inside a pytest
``tmp_path`` and use it as the ``repo_url``. We deliberately avoid the
network so the suite stays hermetic and fast — every code path in
:class:`WorkspaceManager` is reachable against a local clone source.

Two Windows-specific caveats baked into the helpers below:

1. Git's pack files are written read-only on disk, which makes pytest's
   default ``tmp_path`` teardown raise ``PermissionError`` on Windows.
   :func:`_force_remove` flips the read-only bit before retrying.
2. ``git worktree add`` inherits the bare cache's ``core.longpaths``
   setting, so we run the fixture init with longpaths explicitly enabled
   to match production wiring.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from web.server.services.workspace_manager import (
    CloneFailed,
    RefNotFound,
    WorkspaceError,
    WorkspaceExists,
    WorkspaceManager,
    _slug_from_url,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run ``git`` for fixtures with longpaths + identity always set.

    We pin ``user.email`` / ``user.name`` via ``-c`` so the test does not
    depend on the developer's global git config (which a fresh CI runner
    may not have).
    """

    cmd = [
        "git",
        "-c",
        "core.longpaths=true",
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        *args,
    ]
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=True, timeout=120
    )


def _make_local_repo(tmp_path: Path) -> Path:
    """Build a small local git repo with two branches and a tag.

    Layout:

    * ``main`` — single commit adding ``README.md``.
    * ``feature`` — branched off ``main`` with one extra commit on
      ``feature.md``.
    * tag ``v1`` — points at the ``main`` HEAD.

    Returns the repository working directory (which doubles as the
    ``repo_url`` we feed into the manager, since git clone happily
    accepts a local path).
    """

    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=repo)
    (repo / "README.md").write_text("test", encoding="utf-8")
    _git(["add", "."], cwd=repo)
    _git(["commit", "-m", "init"], cwd=repo)
    _git(["tag", "v1"], cwd=repo)
    _git(["checkout", "-b", "feature"], cwd=repo)
    (repo / "feature.md").write_text("feature", encoding="utf-8")
    _git(["add", "."], cwd=repo)
    _git(["commit", "-m", "feature"], cwd=repo)
    _git(["checkout", "main"], cwd=repo)
    return repo


def _force_remove(path: Path) -> None:
    """Recursively delete ``path``, healing read-only bits on Windows.

    pytest's ``tmp_path`` cleanup runs after the test returns, but on
    Windows git's ``pack-*.idx`` files are marked read-only and pytest's
    default cleanup chokes on them. Tests that materialise worktrees
    invoke this in their teardown so the fixture root vanishes cleanly.
    """

    if not path.exists():
        return

    def _onerror(func, p, exc_info):  # noqa: ANN001 — shutil callback signature
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            return
        try:
            func(p)
        except OSError:
            pass

    import shutil

    shutil.rmtree(path, onerror=_onerror)


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    """Return the path of a freshly built local git repo."""

    return _make_local_repo(tmp_path)


@pytest.fixture
def manager(tmp_path: Path) -> WorkspaceManager:
    """A :class:`WorkspaceManager` rooted at an isolated ``tmp_path``.

    Using ``tmp_path`` as the *repo root* means the manager writes to
    ``<tmp_path>/.speca/workspaces/…`` and never touches the real
    repository tree. ``tmp_path`` itself is cleaned up by pytest at the
    end of the test (with read-only-bit healing in
    :func:`_force_remove` if any test needs to do it eagerly).
    """

    return WorkspaceManager(root=tmp_path)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def test_slug_from_url_normalisation() -> None:
    """``_slug_from_url`` collapses URL noise to a single deterministic slug."""

    assert _slug_from_url("https://github.com/owner/repo.git") == _slug_from_url(
        "https://github.com/owner/repo"
    )
    # Different URLs are allowed to produce different slugs at v1; we only
    # require *equal* URLs produce *equal* slugs.
    slug = _slug_from_url("https://github.com/Owner/Repo.git")
    assert slug
    # No collapsed empty runs.
    assert "--" not in slug
    assert not slug.startswith("-") and not slug.endswith("-")


def test_ensure_bare_cache_creates(manager: WorkspaceManager, fixture_repo: Path) -> None:
    """First call clones; second call refreshes the existing cache."""

    bare = manager.ensure_bare_cache(str(fixture_repo))
    assert bare.is_dir()
    assert bare.name.endswith(".git")
    # ``HEAD`` is the bare-repo equivalent of "a checkout happened".
    assert (bare / "HEAD").is_file()

    # Mark a sentinel file to prove the second call did not delete-and-recreate.
    sentinel = bare / "speca-sentinel"
    sentinel.write_text("kept", encoding="utf-8")

    bare_again = manager.ensure_bare_cache(str(fixture_repo))
    assert bare_again == bare
    assert sentinel.is_file(), "ensure_bare_cache must refresh, not re-clone"


def test_create_worktree_default_head(
    manager: WorkspaceManager, fixture_repo: Path
) -> None:
    """``ref=None`` materialises the bare cache's HEAD."""

    wt = manager.create_worktree("run-default", str(fixture_repo))
    try:
        assert wt.is_dir()
        # README is only present on the ``main`` branch (which is HEAD).
        assert (wt / "README.md").is_file()
    finally:
        manager.remove_worktree("run-default")
        _force_remove(wt)


def test_create_worktree_specific_branch(
    manager: WorkspaceManager, fixture_repo: Path
) -> None:
    """A named branch checks out branch-specific files."""

    wt = manager.create_worktree("run-feat", str(fixture_repo), ref="feature")
    try:
        assert (wt / "feature.md").is_file(), "expected feature.md from feature branch"
        # README is on both branches, so it stays present.
        assert (wt / "README.md").is_file()
    finally:
        manager.remove_worktree("run-feat")
        _force_remove(wt)


def test_create_worktree_specific_commit(
    manager: WorkspaceManager, fixture_repo: Path
) -> None:
    """A raw commit SHA is acceptable as a ref (``--detach`` keeps git quiet)."""

    # Resolve the SHA from the fixture (rev-parse main).
    rev = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=fixture_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    sha = rev.stdout.strip()
    assert len(sha) == 40

    wt = manager.create_worktree("run-sha", str(fixture_repo), ref=sha)
    try:
        assert wt.is_dir()
        assert (wt / "README.md").is_file()
    finally:
        manager.remove_worktree("run-sha")
        _force_remove(wt)


def test_create_worktree_duplicate_run_id(
    manager: WorkspaceManager, fixture_repo: Path
) -> None:
    """A second ``create_worktree`` with the same run_id refuses to clobber."""

    wt = manager.create_worktree("run-dupe", str(fixture_repo))
    try:
        with pytest.raises(WorkspaceExists):
            manager.create_worktree("run-dupe", str(fixture_repo))
    finally:
        manager.remove_worktree("run-dupe")
        _force_remove(wt)


def test_remove_worktree_idempotent(manager: WorkspaceManager) -> None:
    """Removing a never-created worktree must not raise."""

    # Nothing under workspaces/ at all yet.
    manager.remove_worktree("does-not-exist")
    # Calling twice in a row stays a no-op.
    manager.remove_worktree("does-not-exist")


def test_remove_worktree_after_create(
    manager: WorkspaceManager, fixture_repo: Path
) -> None:
    """Cleanup actually frees the slot so a follow-up ``create`` works."""

    wt = manager.create_worktree("run-cycle", str(fixture_repo))
    assert wt.is_dir()
    manager.remove_worktree("run-cycle")
    assert not wt.exists(), "worktree directory should be gone after remove"

    # And we can immediately re-create with the same id.
    wt2 = manager.create_worktree("run-cycle", str(fixture_repo))
    try:
        assert wt2.is_dir()
    finally:
        manager.remove_worktree("run-cycle")
        _force_remove(wt2)


def test_ref_not_found(manager: WorkspaceManager, fixture_repo: Path) -> None:
    """An unknown ref raises :class:`RefNotFound`, not a generic clone error."""

    with pytest.raises(RefNotFound):
        manager.create_worktree(
            "run-bogus", str(fixture_repo), ref="this-ref-does-not-exist"
        )

    # The aborted create should not leave a half-built directory behind.
    assert not manager.worktree_path_for("run-bogus").exists()


def test_invalid_repo_url(manager: WorkspaceManager) -> None:
    """Empty / control-character URLs are rejected before any subprocess runs."""

    with pytest.raises(WorkspaceError):
        manager.ensure_bare_cache("")
    with pytest.raises(WorkspaceError):
        manager.ensure_bare_cache("https://example.com/foo;rm -rf /")


def test_clone_failed_for_nonexistent_repo(
    manager: WorkspaceManager, tmp_path: Path
) -> None:
    """``CloneFailed`` is raised when the source repo doesn't exist on disk."""

    missing = tmp_path / "not-a-repo"
    with pytest.raises(CloneFailed):
        manager.ensure_bare_cache(str(missing))


def test_prune_caches_is_noop_in_v1(manager: WorkspaceManager) -> None:
    """v1 contract: ``prune_caches`` exists and returns an empty list."""

    assert manager.prune_caches() == []
    assert manager.prune_caches(max_total_gb=1.0) == []


def test_bare_path_for_is_deterministic(manager: WorkspaceManager) -> None:
    """Equal URLs always resolve to the same bare path (idempotency)."""

    url = "https://github.com/octocat/Hello-World.git"
    assert manager.bare_path_for(url) == manager.bare_path_for(url)
    # Slug is deterministic across instances too.
    other = WorkspaceManager(root=manager.workspaces_dir.parent.parent)
    assert other.bare_path_for(url) == manager.bare_path_for(url)

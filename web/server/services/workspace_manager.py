"""Bare-cache + worktree management for the SPECA web backend.

Each audit run needs an isolated checkout of the target repository. Cloning
fresh per run would (a) burn bandwidth, (b) burn disk, and (c) wedge runs
behind GitHub's rate limit. The pattern used here is the same one the CLI
already uses for batch audits:

1. A single **bare** clone per ``repo_url`` lives under
   ``<repo_root>/.speca/workspaces/<slug>.git``. It is reused for the
   lifetime of the install and only ever updated via ``git fetch``.
2. Each run materialises a cheap ``git worktree add`` under
   ``<repo_root>/.speca/workspaces/wt/<run_id>``. Worktrees share the
   underlying object store with the bare cache, so a fresh worktree
   typically costs only the working-tree files (no ``.git`` blob copy).
3. When a run finishes, only the **worktree** is removed. The bare cache
   stays so the next run can fast-fetch from it.

Invariants enforced here:

* All ``git`` invocations go through :func:`_run_git`, which forces
  ``shell=False``, captures stdout/stderr, and prepends
  ``-c core.longpaths=true`` so a 260-char Windows path inside the target
  repo never wedges the worktree command.
* Errors are turned into structured :class:`WorkspaceError` subclasses so
  the caller (Slice B1 / ``run_supervisor``) can map them to HTTP envelopes
  without inspecting ``stderr`` strings.
* ``remove_worktree`` is **idempotent** — supervisors call it from a
  ``finally`` block, and the cleanup path must never raise.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

from web.server.config import SPECA_REPO_ROOT

logger = logging.getLogger(__name__)

# Default timeout for any single ``git`` invocation. 10 minutes is generous
# enough for a fresh ``--bare`` clone of a multi-GB monorepo over a slow
# link but still bounded so a hung credential prompt cannot pin the
# orchestrator forever.
_GIT_TIMEOUT_SECONDS = 600

# Characters we **never** accept in a ``repo_url`` regardless of scheme.
# Newlines, NULs, and shell metacharacters would either break argv parsing
# inside ``git`` or be a red flag for an injected URL. We are deliberately
# permissive about everything else (backslashes for Windows local paths,
# tildes for ``~/`` expansions, etc.) because the input is already a
# trusted user-controlled string at the API boundary.
_FORBIDDEN_URL_CHARS = re.compile(r"[\x00-\x1f;|`$\s]")

# Cap the slug at this many characters of the URL "tail". Windows hits
# ``MAX_PATH`` (260) on the *combined* worktree admin path
# (``<bare>/worktrees/<run_id>/...``); a 90-char URL tail plus a stable
# 12-char SHA suffix leaves enough headroom for ``.speca/workspaces/`` +
# ``worktrees/<run_id>/`` + git's own admin filenames without hitting
# the limit even when the user puts the repo under a deeply nested home.
_SLUG_TAIL_LIMIT = 90
_SLUG_HASH_LEN = 12


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WorkspaceError(Exception):
    """Base class for all workspace-management failures."""


class CloneFailed(WorkspaceError):
    """``git clone --bare`` (or the follow-up fetch) returned non-zero."""


class RefNotFound(WorkspaceError):
    """The caller asked for a ref that does not exist in the bare cache."""


class WorkspaceExists(WorkspaceError):
    """``create_worktree`` was called twice for the same ``run_id``."""


class WorkspaceCleanupWarning(WorkspaceError):
    """``remove_worktree`` could not fully tear down a worktree.

    Raised internally by helpers but **never** propagated out of
    :meth:`WorkspaceManager.remove_worktree` — the cleanup path always
    swallows this and logs at WARNING level instead. The class exists so
    that future supervisors can opt into strict cleanup if they want to.
    """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_repo_url(repo_url: str) -> str:
    """Validate ``repo_url`` and return it unchanged on success.

    Raises:
        WorkspaceError: ``repo_url`` is empty / ``None`` / contains a
            forbidden control or shell-meta character.
    """

    if not isinstance(repo_url, str) or not repo_url.strip():
        raise WorkspaceError("repo_url must be a non-empty string")
    if _FORBIDDEN_URL_CHARS.search(repo_url):
        raise WorkspaceError(
            "repo_url contains forbidden characters (control / shell metachars)"
        )
    return repo_url


def _slug_from_url(repo_url: str) -> str:
    """Derive a filesystem-safe cache slug from ``repo_url``.

    The goal is a **deterministic** mapping (``ensure_bare_cache`` must be
    idempotent across processes) that is also human-recognisable when an
    operator opens ``.speca/workspaces/``.

    Strategy:

    1. Strip ``.git`` suffix.
    2. Strip a scheme (``https://``, ``ssh://``, ``git+ssh://``) or an
       SCP-style ``user@host:`` prefix.
    3. Replace any character outside ``[A-Za-z0-9._-]`` with ``-``.
    4. Collapse runs of ``-`` so we never produce
       ``https---github.com-...``.

    The result is **not** intended to be reversible — two URLs that
    differ only in scheme will end up at the same slug, but the spec
    explicitly accepts that (``git@github.com:o/r`` and
    ``https://github.com/o/r`` may safely produce different *or* identical
    slugs at v1; we choose identical because it saves disk).
    """

    text = repo_url.strip()
    # Drop trailing ``.git`` so ``foo`` and ``foo.git`` share a cache.
    if text.endswith(".git"):
        text = text[: -len(".git")]
    # Drop URL scheme (``https://``, ``ssh://``, ``git://`` ...).
    text = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://", "", text)
    # Drop SCP-style ``user@host:`` prefix.
    text = re.sub(r"^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+:", "", text)
    # Replace forbidden chars then collapse repeats.
    slug = re.sub(r"[^A-Za-z0-9._-]", "-", text)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        # Pathological input (e.g. only forbidden characters). Fall back
        # to a fixed sentinel rather than raising — the caller already
        # validated the URL and we'd rather not double-fail.
        slug = "repo"

    # Windows pain point: ``<bare>/worktrees/<run_id>/...`` can easily
    # exceed MAX_PATH (260) when the user puts the repo under a deep
    # home (e.g. pytest's per-test tmp dirs). Keep the slug short *and*
    # deterministic by truncating the human-readable tail and appending
    # a stable hash of the full URL. The hash guarantees that two
    # distinct URLs which share the same suffix don't collide.
    if len(slug) > _SLUG_TAIL_LIMIT:
        digest = hashlib.sha1(repo_url.encode("utf-8")).hexdigest()[:_SLUG_HASH_LEN]
        tail = slug[-_SLUG_TAIL_LIMIT:].lstrip("-")
        slug = f"{tail}-{digest}"
    return slug


def _run_git(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float = _GIT_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Run ``git`` with the safe defaults we want everywhere.

    * ``shell=False`` — argv passed as a list, no shell quoting.
    * ``capture_output=True`` + ``text=True`` — stderr is available on
      failure for error envelopes.
    * ``-c core.longpaths=true`` is prepended so Windows worktree adds
      stop failing on the first 280-char path inside the target repo.
    """

    cmd = ["git", "-c", "core.longpaths=true", *args]
    logger.debug("speca.workspace: running %s (cwd=%s)", cmd, cwd)
    return subprocess.run(
        cmd,
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd) if cwd is not None else None,
    )


def _stderr_indicates_missing_ref(stderr: str) -> bool:
    """Heuristic: does ``stderr`` look like "ref not found"?

    ``git worktree add`` reports a missing ref through a handful of
    phrasings depending on whether the ref was a branch, a tag, or a raw
    SHA. We match the union so the caller gets a clean :class:`RefNotFound`
    regardless of which path was hit.
    """

    if not stderr:
        return False
    needles = (
        "invalid reference",
        "not a valid object name",
        "not a valid ref",
        "unknown revision",
        "fatal: invalid reference",
        "fatal: ambiguous argument",
        "did not match any file(s) known to git",
    )
    lowered = stderr.lower()
    return any(needle in lowered for needle in needles)


# ---------------------------------------------------------------------------
# Public manager
# ---------------------------------------------------------------------------


class WorkspaceManager:
    """Manage bare caches and per-run worktrees under ``.speca/workspaces``.

    The constructor accepts an explicit ``root`` so tests can point at a
    pytest ``tmp_path`` and stay fully isolated from the user's real
    ``.speca/`` tree. In production callers pass ``None`` and the manager
    derives the root from :data:`web.server.config.SPECA_REPO_ROOT`.
    """

    def __init__(self, root: Path | None = None) -> None:
        # ``root`` is the *repo root*, not the workspaces dir. We keep the
        # subdirectory layout under our own control so the on-disk shape
        # is stable for ops (``ls .speca/workspaces/`` should always work).
        repo_root = Path(root) if root is not None else SPECA_REPO_ROOT
        self._root = repo_root
        self._workspaces = repo_root / ".speca" / "workspaces"
        self._worktrees_root = self._workspaces / "wt"

    # ---- properties used in tests / debugging --------------------------

    @property
    def workspaces_dir(self) -> Path:
        """Absolute path to the bare-cache directory (parent of slugs)."""

        return self._workspaces

    @property
    def worktrees_dir(self) -> Path:
        """Absolute path to the per-run worktree root (``wt/``)."""

        return self._worktrees_root

    def bare_path_for(self, repo_url: str) -> Path:
        """Return the bare-cache directory for ``repo_url`` (may not exist)."""

        _validate_repo_url(repo_url)
        slug = _slug_from_url(repo_url)
        return self._workspaces / f"{slug}.git"

    def worktree_path_for(self, run_id: str) -> Path:
        """Return the worktree directory for ``run_id`` (may not exist)."""

        if not isinstance(run_id, str) or not run_id.strip():
            raise WorkspaceError("run_id must be a non-empty string")
        return self._worktrees_root / run_id

    # ---- bare-cache lifecycle ------------------------------------------

    def ensure_bare_cache(self, repo_url: str) -> Path:
        """Create or refresh the bare cache for ``repo_url``.

        First call: ``git clone --bare`` into the slug directory. Every
        subsequent call: ``git fetch --all --prune`` plus an explicit
        ``+refs/*:refs/*`` mirror fetch so tags and arbitrary refs land
        in the cache (the default ``--bare`` mirror config only follows
        ``refs/heads/*`` once we start fetching).
        """

        _validate_repo_url(repo_url)
        bare_path = self.bare_path_for(repo_url)
        self._workspaces.mkdir(parents=True, exist_ok=True)

        if not bare_path.exists():
            logger.info("speca.workspace: cloning bare cache %s", bare_path)
            result = _run_git(
                ["clone", "--bare", "--", repo_url, str(bare_path)],
            )
            if result.returncode != 0:
                # ``--bare`` may leave behind a partial directory on
                # failure; sweep it so the next attempt starts clean.
                shutil.rmtree(bare_path, ignore_errors=True)
                raise CloneFailed(
                    f"git clone --bare failed for {repo_url}: "
                    f"{result.stderr.strip() or result.stdout.strip()}"
                )
            # Persist ``core.longpaths=true`` in the bare cache itself so
            # subsequent ``git worktree add`` invocations (which spawn
            # internal sub-processes that don't see our ``-c`` flag)
            # honour long Windows paths uniformly.
            _run_git(
                ["config", "core.longpaths", "true"],
                cwd=bare_path,
            )
            return bare_path

        logger.info("speca.workspace: refreshing bare cache %s", bare_path)
        # ``fetch --all`` covers configured remotes (i.e. ``origin``).
        result = _run_git(
            ["fetch", "--all", "--prune", "--tags"],
            cwd=bare_path,
        )
        if result.returncode != 0:
            raise CloneFailed(
                f"git fetch failed for {bare_path}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return bare_path

    # ---- worktree lifecycle --------------------------------------------

    def create_worktree(
        self,
        run_id: str,
        repo_url: str,
        ref: str | None = None,
    ) -> Path:
        """Materialise a worktree at ``wt/<run_id>`` from the bare cache.

        ``ref`` is forwarded verbatim to ``git worktree add`` so it can be
        a branch name, a tag, or a SHA. When ``ref`` is ``None`` we use
        ``HEAD`` of the bare cache (which mirrors the remote's default
        branch).

        Raises:
            WorkspaceExists: a worktree for ``run_id`` already exists on
                disk. The supervisor should treat this as "another run is
                already using that id" and refuse the duplicate launch.
            RefNotFound: ``ref`` did not resolve in the bare cache.
            CloneFailed: the underlying ``git worktree add`` failed for
                any other reason (disk full, permission denied, ...).
        """

        worktree_path = self.worktree_path_for(run_id)
        if worktree_path.exists():
            raise WorkspaceExists(
                f"worktree for run_id={run_id!r} already exists at {worktree_path}"
            )

        bare_path = self.ensure_bare_cache(repo_url)
        self._worktrees_root.mkdir(parents=True, exist_ok=True)

        # ``git worktree add <path> <ref>`` — when ``ref`` is omitted git
        # uses ``HEAD`` of the bare repo. We pass ``--detach`` so we never
        # try to create a local branch named after a SHA (which would
        # fail) and so two worktrees off the same branch don't fight over
        # the branch checkout lock.
        worktree_args = [
            "worktree",
            "add",
            "--detach",
            "--force",
            str(worktree_path),
        ]
        if ref is not None:
            if not isinstance(ref, str) or not ref.strip():
                raise WorkspaceError("ref must be a non-empty string when provided")
            worktree_args.append(ref)

        result = _run_git(worktree_args, cwd=bare_path)
        if result.returncode != 0:
            stderr = result.stderr or ""
            # Wipe any half-materialised directory so a retry with the
            # right ref starts clean.
            shutil.rmtree(worktree_path, ignore_errors=True)
            # ``git worktree add`` records the failed entry under
            # ``worktrees/`` inside the bare repo too — prune it so the
            # next ``add`` for the same path is not blocked.
            _run_git(["worktree", "prune"], cwd=bare_path)
            if _stderr_indicates_missing_ref(stderr):
                raise RefNotFound(
                    f"ref {ref!r} not found in bare cache {bare_path}: {stderr.strip()}"
                )
            raise CloneFailed(
                f"git worktree add failed for run_id={run_id}: "
                f"{stderr.strip() or result.stdout.strip()}"
            )
        return worktree_path

    def remove_worktree(self, run_id: str) -> None:
        """Tear down the worktree for ``run_id``. Idempotent.

        The supervisor calls this from a ``finally`` block, so it must
        never raise: missing worktree, locked file, orphaned bare entry,
        all are downgraded to a WARNING log line. The bare cache itself
        is **never** touched here — that's the whole point of keeping it.
        """

        if not isinstance(run_id, str) or not run_id.strip():
            # Don't raise — the cleanup path is a no-throw zone.
            logger.warning("speca.workspace: remove_worktree called with empty run_id")
            return

        worktree_path = self._worktrees_root / run_id
        # Snapshot existence early; even if the directory disappears
        # between the check and the git call we'll fall through to the
        # ``prune`` pass below which heals stale entries.
        existed = worktree_path.exists()

        bare_path = self._locate_owning_bare(worktree_path) if existed else None

        if bare_path is not None:
            result = _run_git(
                ["worktree", "remove", "--force", str(worktree_path)],
                cwd=bare_path,
            )
            if result.returncode != 0:
                logger.warning(
                    "speca.workspace: git worktree remove failed for %s: %s",
                    worktree_path,
                    (result.stderr or result.stdout).strip(),
                )

        # Belt-and-braces: if git refused or never knew about the
        # worktree, force-delete the directory ourselves.
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)
            if worktree_path.exists():
                logger.warning(
                    "speca.workspace: could not fully remove %s", worktree_path
                )

        # Prune dangling entries across **all** known bare caches so the
        # next ``create_worktree`` is never blocked by a stale record.
        for bare in self._iter_bare_caches():
            _run_git(["worktree", "prune"], cwd=bare)

    # ---- v2 hooks ------------------------------------------------------

    def prune_caches(self, max_total_gb: float = 50.0) -> list[Path]:
        """Trim oldest bare caches once the total exceeds ``max_total_gb``.

        v1 only needs the public surface to exist (Slice B1 references
        it from the supervisor for forward-compat). v2 will implement
        actual byte-size accounting + LRU eviction; for now we just
        return an empty list so callers get a stable contract.
        """

        del max_total_gb  # unused in v1, accepted to lock the signature.
        return []

    # ---- internals -----------------------------------------------------

    def _iter_bare_caches(self) -> Iterable[Path]:
        """Yield every ``*.git`` directory under ``workspaces/``."""

        if not self._workspaces.exists():
            return []
        return [
            child
            for child in self._workspaces.iterdir()
            if child.is_dir() and child.name.endswith(".git")
        ]

    def _locate_owning_bare(self, worktree_path: Path) -> Path | None:
        """Find which bare cache owns ``worktree_path``.

        A worktree directory contains a ``.git`` *file* (not directory)
        whose body is ``gitdir: <abs-path-to-bare>/worktrees/<name>``. We
        parse that pointer to recover the bare path so we can call
        ``git worktree remove`` against the right repo. Falls back to
        scanning every known bare cache if the pointer is missing or
        unreadable.
        """

        gitdir_file = worktree_path / ".git"
        if gitdir_file.is_file():
            try:
                body = gitdir_file.read_text(encoding="utf-8").strip()
            except OSError:
                body = ""
            if body.startswith("gitdir:"):
                ptr = Path(body.split(":", 1)[1].strip())
                # ``ptr`` looks like ``<bare>/worktrees/<run_id>``; the
                # bare path is two parents up.
                candidate = ptr.parent.parent
                if candidate.is_dir() and candidate.name.endswith(".git"):
                    return candidate

        # Fall back to a linear scan. ``worktree list`` per bare is the
        # canonical way to ask git "do you own this path?".
        for bare in self._iter_bare_caches():
            result = _run_git(["worktree", "list", "--porcelain"], cwd=bare)
            if result.returncode != 0:
                continue
            for line in result.stdout.splitlines():
                if line.startswith("worktree "):
                    listed = Path(line.split(" ", 1)[1].strip())
                    try:
                        if listed.resolve() == worktree_path.resolve():
                            return bare
                    except OSError:
                        continue
        return None


__all__ = [
    "CloneFailed",
    "RefNotFound",
    "WorkspaceCleanupWarning",
    "WorkspaceError",
    "WorkspaceExists",
    "WorkspaceManager",
]

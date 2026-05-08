"""publish_hf.py — push a built dataset directory to a HuggingFace dataset
repo on the `main` branch (no revision tagging).

Inputs:
    --src    <out-dir>/<domain>/   (created by build_derived.py)
    --repo   NyxFoundation/<domain>-audit-findings

The script:
    1. Reads `manifest.json` from --src.
    2. Renders the dataset card from
       `scripts/datasets/templates/README.md.j2` using the manifest.
    3. Stages parquet + README in a temp dir (the source dir is read-only;
       no artifact contamination).
    4. Creates the dataset repo if missing (`exist_ok=True`).
    5. Uploads via `HfApi.upload_folder(revision="main", delete_patterns=["data/*"])`
       so stale data files are pruned.

Authentication: `HF_TOKEN` env var (or any other source the
`huggingface_hub` token resolver understands, e.g. `huggingface-cli login`).

`--dry-run` skips network calls and writes the rendered README to a
temp path so the source directory stays untouched.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_TEMPLATE = "README.md.j2"

# HF repo ids: <org-or-user>/<name>, alnum + `_` + `-` + `.` per HF rules.
REPO_RE = re.compile(r"^[A-Za-z0-9_-]+/[A-Za-z0-9._-]+$")


def size_category(n_rows: int) -> str:
    """Map row count to one of HF's canonical `size_categories` buckets.

    Per https://huggingface.co/docs/hub/datasets-cards (size_categories
    enum): n<1K, 1K<n<10K, 10K<n<100K, 100K<n<1M, 1M<n<10M, 10M<n<100M,
    100M<n<1B, n>1B.
    """
    if n_rows < 1_000:
        return "n<1K"
    if n_rows < 10_000:
        return "1K<n<10K"
    if n_rows < 100_000:
        return "10K<n<100K"
    if n_rows < 1_000_000:
        return "100K<n<1M"
    if n_rows < 10_000_000:
        return "1M<n<10M"
    if n_rows < 100_000_000:
        return "10M<n<100M"
    if n_rows < 1_000_000_000:
        return "100M<n<1B"
    return "n>1B"


def render_card(manifest: dict, repo_id: str, template_name: str = DEFAULT_TEMPLATE) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(default=False),
        trim_blocks=False,
        lstrip_blocks=False,
    )
    tmpl = env.get_template(template_name)
    return tmpl.render(
        domain=manifest["domain"],
        n_rows=manifest["n_rows"],
        parquet_bytes=manifest["parquet_bytes"],
        scraped_at=manifest["scraped_at"],
        speca_commit=manifest.get("speca_commit") or "unknown",
        rows_by_platform=manifest.get("rows_by_platform", {}),
        rows_by_severity=manifest.get("rows_by_severity", {}),
        size_category=size_category(manifest["n_rows"]),
        repo_id=repo_id,
    )


def _stage(src: Path, manifest: dict, card: str) -> tempfile.TemporaryDirectory:
    """Copy the parquet + write the rendered README into a temp dir whose
    layout mirrors the HF repo root. Returns the TemporaryDirectory so the
    caller can use it via `with`.
    """
    parquet_relative = manifest.get("parquet_path") or "data/train.parquet"
    parquet_src = src / parquet_relative
    if not parquet_src.exists():
        sys.exit(f"parquet not found at {parquet_src} (manifest.parquet_path={parquet_relative!r})")

    td = tempfile.TemporaryDirectory(prefix="speca-publish-hf-")
    staging = Path(td.name)
    (staging / Path(parquet_relative).parent).mkdir(parents=True, exist_ok=True)
    shutil.copy2(parquet_src, staging / parquet_relative)
    (staging / "README.md").write_text(card)
    return td


def push(staging: Path, repo_id: str, token: str, commit_message: str) -> str:
    from huggingface_hub import HfApi
    from huggingface_hub.utils import HfHubHTTPError

    api = HfApi(token=token)
    try:
        api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
    except HfHubHTTPError as e:
        # 401/403 → token / scope problem; 404 → org missing.
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status in (401, 403):
            sys.exit(f"HF auth failed (HTTP {status}) creating {repo_id}: token lacks write scope on the org?")
        if status == 404:
            sys.exit(f"HF org/user not found (HTTP 404) creating {repo_id}: does the org exist and is the token valid?")
        raise

    try:
        commit_info = api.upload_folder(
            folder_path=str(staging),
            repo_id=repo_id,
            repo_type="dataset",
            revision="main",
            commit_message=commit_message,
            # Prune stale data files (e.g. an earlier `data/train-old.parquet`)
            # so what HF serves matches what we just built.
            delete_patterns=["data/*"],
        )
    except HfHubHTTPError as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status in (401, 403):
            sys.exit(f"HF auth failed (HTTP {status}) uploading to {repo_id}: token lacks write scope?")
        raise
    return getattr(commit_info, "commit_url", "") or ""


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--src", required=True,
                   help="Path to <out-dir>/<domain>/ produced by build_derived.py.")
    p.add_argument("--repo", required=True,
                   help="HF dataset repo id (e.g. NyxFoundation/defi-audit-findings).")
    p.add_argument("--require-org", default="NyxFoundation",
                   help="Reject --repo not under this org. Use '' to allow any.")
    p.add_argument("--commit-message", default="",
                   help="Commit message; default = 'Update <domain> dataset @ <scraped_at>'.")
    p.add_argument("--dry-run", action="store_true",
                   help="Render the README and stage files; skip the network push.")
    p.add_argument("--token", default="",
                   help="HF token; default = $HF_TOKEN or huggingface_hub default.")
    args = p.parse_args()

    src = Path(args.src)
    manifest_path = src / "manifest.json"
    if not manifest_path.exists():
        sys.exit(f"manifest.json not found in {src}")
    manifest = json.loads(manifest_path.read_text())

    if not REPO_RE.fullmatch(args.repo):
        sys.exit(f"--repo must match {REPO_RE.pattern!r}; got {args.repo!r}")
    if args.require_org:
        org = args.repo.split("/", 1)[0]
        if org != args.require_org:
            sys.exit(
                f"--repo {args.repo} not under required org {args.require_org!r}. "
                f"Pass --require-org '' to allow other orgs."
            )

    card = render_card(manifest, args.repo)
    print(f"rendered README.md ({len(card)} chars)")

    commit_message = (
        args.commit_message
        or f"Update {manifest['domain']} dataset @ {manifest['scraped_at']}"
    )

    td = _stage(src, manifest, card)
    try:
        staging = Path(td.name)
        if args.dry_run:
            print("[dry-run] would push:")
            for p in sorted(staging.rglob("*")):
                if p.is_file():
                    print(f"  - {p.relative_to(staging)} ({p.stat().st_size} bytes)")
            print(f"  to repo: {args.repo} (revision: main)")
            print(f"  commit message: {commit_message!r}")
            return 0

        token = args.token or os.environ.get("HF_TOKEN", "")
        if not token:
            sys.exit("no HF token: set --token or $HF_TOKEN, or run `huggingface-cli login`")

        commit_url = push(staging, args.repo, token, commit_message)
        print(f"pushed to https://huggingface.co/datasets/{args.repo} (revision main)")
        if commit_url:
            print(f"  commit: {commit_url}")
    finally:
        td.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

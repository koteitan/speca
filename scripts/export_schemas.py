#!/usr/bin/env python3
"""Export Pydantic models from `orchestrator.schemas` as JSON Schema files.

Used by `speca-cli` (and any other tool) to validate `TARGET_INFO.json`,
`BUG_BOUNTY_SCOPE.json`, and the per-phase PARTIAL outputs **without** running
Python — the published JSON Schemas are the language-neutral data contract.

Usage:

    python scripts/export_schemas.py              # write all schemas to ./schemas/
    python scripts/export_schemas.py --out-dir X  # write to X/ instead
    python scripts/export_schemas.py --check      # CI: fail when on-disk schemas differ
    python scripts/export_schemas.py --list       # print model names that would be exported
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "schemas"
SOURCE_MODULE = "orchestrator.schemas"

# Make `orchestrator` importable when invoked from the repo root, mirroring
# the pattern in `scripts/run_phase.py`.
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _import_pydantic_basemodel():
    try:
        from pydantic import BaseModel
    except ImportError as exc:  # pragma: no cover - env-dependent
        sys.stderr.write(
            "pydantic is required (install with `uv sync` or `pip install pydantic`)\n"
        )
        raise SystemExit(1) from exc
    return BaseModel


def collect_models(module_name: str) -> list[type]:
    """Return all BaseModel subclasses defined directly in ``module_name``."""
    BaseModel = _import_pydantic_basemodel()
    module = importlib.import_module(module_name)
    models: list[type] = []
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, BaseModel)
            and obj is not BaseModel
            and obj.__module__ == module_name  # exclude re-exports
        ):
            models.append(obj)
    models.sort(key=lambda c: c.__name__)
    return models


def render_schema(model: type) -> dict:
    """Render a stable JSON Schema dict for one model."""
    return model.model_json_schema(mode="serialization")


def serialize_schema(schema: dict) -> str:
    """Stable, line-stable serialization for diffable check-mode output."""
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_schema(model: type, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{model.__name__}.schema.json"
    path.write_text(serialize_schema(render_schema(model)), encoding="utf-8")
    return path


def _short(path: Path) -> str:
    """Pretty-print a path relative to REPO_ROOT when possible, absolute otherwise."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def check_in_sync(models: list[type], out_dir: Path) -> list[str]:
    """Return a list of mismatch descriptions (empty list = in sync)."""
    diffs: list[str] = []
    if not out_dir.exists():
        diffs.append(f"missing output directory: {_short(out_dir)}")
        return diffs

    expected_files: set[str] = set()
    for model in models:
        expected_files.add(f"{model.__name__}.schema.json")
        path = out_dir / f"{model.__name__}.schema.json"
        generated = serialize_schema(render_schema(model))
        if not path.exists():
            diffs.append(f"missing: {_short(path)}")
            continue
        existing = path.read_text(encoding="utf-8")
        if existing != generated:
            diffs.append(f"stale:   {_short(path)}")

    # Also surface schemas that exist on disk but are no longer generated
    for path in sorted(out_dir.glob("*.schema.json")):
        if path.name not in expected_files:
            diffs.append(f"orphan:  {_short(path)}")
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory to write *.schema.json into (default: ./schemas/)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when on-disk schemas are missing/stale/orphan",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print model names that would be exported, then exit",
    )
    args = parser.parse_args()

    models = collect_models(SOURCE_MODULE)

    if args.list:
        for m in models:
            print(m.__name__)
        return 0

    if args.check:
        diffs = check_in_sync(models, args.out_dir)
        if diffs:
            sys.stderr.write(
                "schemas/ out of sync. Re-run `python scripts/export_schemas.py`:\n"
            )
            for d in diffs:
                sys.stderr.write(f"  {d}\n")
            return 1
        sys.stdout.write(
            f"OK: {len(models)} schemas in sync at {_short(args.out_dir)}/\n"
        )
        return 0

    written = [write_schema(m, args.out_dir) for m in models]
    sys.stderr.write(
        f"Wrote {len(written)} schemas to {_short(args.out_dir)}/\n"
    )
    for p in written:
        sys.stderr.write(f"  {p.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Run a generic static analysis baseline runner.

This runner expects an external command to produce predictions per sample.
The command must write a JSON file at {output_path} with:
  - predicted_vulnerable: bool (required)
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.bench_utils import (
    extract_code,
    extract_id,
    guess_extension,
    iter_jsonl,
    sanitize_filename,
    write_jsonl,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT_DIR / "benchmarks" / "data" / "primevul" / "primevul_test_paired.jsonl"
DEFAULT_RESULTS = ROOT_DIR / "benchmarks" / "results" / "static_baseline.jsonl"
DEFAULT_TMP = ROOT_DIR / "benchmarks" / "tmp" / "static_baseline"
DEFAULT_METADATA = ROOT_DIR / "benchmarks" / "results" / "primevul" / "static_baseline_metadata.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run static baseline benchmark runner.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--tmp-dir", type=Path, default=DEFAULT_TMP)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--tool-name", type=str, default="static_baseline")
    parser.add_argument(
        "--command",
        default="",
        help=(
            "Command template to execute per sample. Available placeholders: "
            "{code_path}, {output_path}, {case_id}"
        ),
    )
    parser.add_argument("--version-command", default="", help="Command to get tool version")
    parser.add_argument("--timeout", type=int, default=0, help="Per-sample timeout in seconds (0 = no timeout)")
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Execute the command template via the shell.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit number of samples (0 = no limit)")
    return parser.parse_args()


def run_command(template: str, code_path: Path, output_path: Path, case_id: str, use_shell: bool, timeout: int) -> tuple[int, str]:
    formatted = template.format(code_path=code_path, output_path=output_path, case_id=case_id)
    try:
        if use_shell:
            result = subprocess.run(formatted, shell=True, capture_output=True, text=True, timeout=timeout or None)
        else:
            result = subprocess.run(shlex.split(formatted), capture_output=True, text=True, timeout=timeout or None)
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    stderr = result.stderr.strip()
    return result.returncode, stderr


def load_prediction(path: Path) -> tuple[bool | None, str | None]:
    if not path.exists():
        return None, "missing_prediction_output"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "prediction_json_parse_failed"

    prediction = data.get("predicted_vulnerable")
    if isinstance(prediction, bool):
        return prediction, None
    if isinstance(prediction, (int, float)):
        return bool(prediction), None
    if isinstance(prediction, str):
        lowered = prediction.strip().lower()
        if lowered in {"true", "1", "yes", "vulnerable"}:
            return True, None
        if lowered in {"false", "0", "no", "clean", "non-vulnerable"}:
            return False, None
    return None, "prediction_missing_or_invalid"


def resolve_version(command: str) -> str | None:
    if not command:
        return None
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
    except Exception:
        return None
    output = (result.stdout or result.stderr).strip()
    return output or None


def main() -> int:
    args = parse_args()
    if not args.dataset.exists():
        print(f"Dataset not found: {args.dataset}", file=sys.stderr)
        return 1

    args.tmp_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for idx, record in enumerate(iter_jsonl(args.dataset)):
        if args.limit and idx >= args.limit:
            break

        case_id = extract_id(record, idx)
        code = extract_code(record)
        if not code:
            results.append(
                {
                    "id": case_id,
                    "predicted_vulnerable": None,
                    "error": "missing_code",
                }
            )
            continue

        ext = guess_extension(record)
        safe_id = sanitize_filename(case_id)
        code_path = args.tmp_dir / f"{safe_id}.{ext}"
        code_path.write_text(code, encoding="utf-8", errors="ignore")

        output_path = args.tmp_dir / f"{safe_id}.prediction.json"

        if args.command:
            return_code, stderr = run_command(args.command, code_path, output_path, case_id, args.shell, args.timeout)
            prediction, error = load_prediction(output_path)
            if error:
                results.append(
                    {
                        "id": case_id,
                        "predicted_vulnerable": None,
                        "error": error,
                        "exit_code": return_code,
                        "stderr": stderr,
                    }
                )
            else:
                results.append(
                    {
                        "id": case_id,
                        "predicted_vulnerable": prediction,
                        "exit_code": return_code,
                    }
                )
        else:
            results.append(
                {
                    "id": case_id,
                    "predicted_vulnerable": None,
                    "error": "runner_not_configured",
                }
            )

    write_jsonl(args.output, results)
    metadata = {
        "tool": args.tool_name,
        "dataset": str(args.dataset),
        "output": str(args.output),
        "command": args.command,
        "version": resolve_version(args.version_command),
        "timeout_sec": args.timeout,
        "limit": args.limit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} static baseline results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate a Markdown report from benchmark metrics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = ROOT_DIR / "benchmarks" / "results" / "metrics.json"
DEFAULT_REPORT = ROOT_DIR / "benchmarks" / "results" / "report.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate benchmark report.")
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def main() -> int:
    args = parse_args()
    if not args.metrics.exists():
        print(f"Metrics file not found: {args.metrics}")
        return 1

    data = json.loads(args.metrics.read_text(encoding="utf-8"))
    dataset = data.get("dataset", {})
    tools = data.get("tools", {})

    lines = []
    lines.append("# Benchmark Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## Dataset")
    lines.append("")
    lines.append(f"- Path: {dataset.get('path', 'unknown')}")
    lines.append(f"- Ground-truth samples: {dataset.get('ground_truth_count', 0)}")
    lines.append("")
    lines.append("## Tool Metrics")
    lines.append("")
    lines.append("| Tool | Precision | Recall | F1 | Coverage | TP | FP | TN | FN | Errors |")
    lines.append("| ---- | --------- | ------ | -- | -------- | -- | -- | -- | -- | ------ |")

    for tool, metrics in tools.items():
        if metrics.get("status") != "ok":
            lines.append(f"| {tool} | n/a | n/a | n/a | 0.000 | 0 | 0 | 0 | 0 | 0 |")
            continue
        lines.append(
            "| {tool} | {precision} | {recall} | {f1} | {coverage} | {tp} | {fp} | {tn} | {fn} | {errors} |".format(
                tool=tool,
                precision=format_metric(metrics.get("precision")),
                recall=format_metric(metrics.get("recall")),
                f1=format_metric(metrics.get("f1")),
                coverage=format_metric(metrics.get("coverage")),
                tp=metrics.get("tp", 0),
                fp=metrics.get("fp", 0),
                tn=metrics.get("tn", 0),
                fn=metrics.get("fn", 0),
                errors=metrics.get("error_count", 0),
            )
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for tool, metrics in tools.items():
        if metrics.get("status") == "missing_results":
            lines.append(f"- {tool}: results missing.")
            continue
        if metrics.get("coverage", 0) == 0:
            lines.append(f"- {tool}: no scored samples (check runner configuration).")
            continue

        skipped_pred = metrics.get("skipped_missing_pred", 0)
        skipped_gt = metrics.get("skipped_missing_gt", 0)
        if skipped_pred or skipped_gt:
            lines.append(
                f"- {tool}: skipped {skipped_pred} samples without predictions and {skipped_gt} samples missing ground truth."
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

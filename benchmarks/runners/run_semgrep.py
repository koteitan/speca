#!/usr/bin/env python3
"""Runner for Semgrep against benchmark datasets."""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "benchmarks" / "data"
RESULTS_DIR = ROOT_DIR / "benchmarks" / "results"
METADATA_PATH = RESULTS_DIR / "primevul" / "semgrep_metadata.json"

def resolve_version() -> str | None:
    try:
        result = subprocess.run(["semgrep", "--version"], capture_output=True, text=True)
    except Exception:
        return None
    output = (result.stdout or result.stderr).strip()
    return output or None


def run_semgrep_on_primevul(timeout: int = 0):
    """Run Semgrep on the PrimeVul dataset."""
    print("--> Running Semgrep on PrimeVul...")
    dataset_path = DATA_DIR / "primevul" / "primevul_test_paired.jsonl"
    output_path = RESULTS_DIR / "primevul" / "semgrep_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    with open(dataset_path, "r") as f:
        for line in f:
            sample = json.loads(line)
            func_id = sample.get("func_hash")
            code = sample.get("func")

            # Create a temporary file to scan
            temp_file = Path(f"/tmp/{func_id}.c")
            temp_file.write_text(code)

            # Run Semgrep
            # Using a generic ruleset for broad coverage. This can be customized.
            try:
                process = subprocess.run(
                    ["semgrep", "--config", "p/c-audit", "--json", str(temp_file)],
                    capture_output=True,
                    text=True,
                    timeout=timeout or None,
                )
            except subprocess.TimeoutExpired:
                results.append({
                    "func_id": func_id,
                    "semgrep_findings": [],
                    "error": "timeout",
                })
                temp_file.unlink()
                continue
            
            semgrep_output = json.loads(process.stdout) if process.stdout else {}
            results.append({
                "func_id": func_id,
                "semgrep_findings": semgrep_output.get("results", []),
            })

            temp_file.unlink()

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    metadata = {
        "tool": "semgrep",
        "dataset": str(dataset_path),
        "output": str(output_path),
        "config": "p/c-audit",
        "version": resolve_version(),
        "timeout_sec": timeout,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"    Semgrep results saved to {output_path}")

def main():
    """Main function to run all benchmarks."""
    parser = argparse.ArgumentParser(description="Run Semgrep benchmark runner.")
    parser.add_argument("--timeout", type=int, default=0, help="Per-sample timeout in seconds (0 = no timeout)")
    args = parser.parse_args()
    run_semgrep_on_primevul(timeout=args.timeout)
    # Add other dataset runners here

if __name__ == "__main__":
    main()

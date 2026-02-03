#!/usr/bin/env python3
"""Evaluates and compares the results of different tools."""

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT_DIR / "benchmarks" / "results"
DATA_DIR = ROOT_DIR / "benchmarks" / "data"
EVALUATION_OUTPUT_PATH = RESULTS_DIR / "evaluation_summary.json"

def load_jsonl(path: Path) -> list:
    """Load a .jsonl file."""
    data = []
    with open(path, "r") as f:
        for line in f:
            data.append(json.loads(line))
    return data

def evaluate_primevul():
    """Evaluate tool performance on the PrimeVul dataset."""
    print("--> Evaluating results for PrimeVul...")
    ground_truth_data = load_jsonl(DATA_DIR / "primevul" / "primevul_test_paired.jsonl")
    semgrep_results_path = RESULTS_DIR / "primevul" / "semgrep_results.json"
    codeql_results_path = RESULTS_DIR / "primevul" / "codeql_results.jsonl"
    # Placeholder for security-agent results
    # security_agent_results_path = RESULTS_DIR / "primevul" / "security_agent_results.json"

    # Create a map of func_id to ground truth label
    ground_truth_map = {sample["func_hash"]: sample["vul_type"] != "clean" for sample in ground_truth_data}

    # --- Evaluate Semgrep ---
    tp_semgrep, fp_semgrep, fn_semgrep = 0, 0, 0
    if semgrep_results_path.exists():
        semgrep_results = json.loads(semgrep_results_path.read_text())
        semgrep_findings_map = {res["func_id"]: len(res["semgrep_findings"]) > 0 for res in semgrep_results}

        for func_id, is_vulnerable in ground_truth_map.items():
            found_by_semgrep = semgrep_findings_map.get(func_id, False)
            if is_vulnerable and found_by_semgrep:
                tp_semgrep += 1
            elif not is_vulnerable and found_by_semgrep:
                fp_semgrep += 1
            elif is_vulnerable and not found_by_semgrep:
                fn_semgrep += 1
    
    precision_semgrep = tp_semgrep / (tp_semgrep + fp_semgrep) if (tp_semgrep + fp_semgrep) > 0 else 0
    recall_semgrep = tp_semgrep / (tp_semgrep + fn_semgrep) if (tp_semgrep + fn_semgrep) > 0 else 0
    f1_semgrep = 2 * (precision_semgrep * recall_semgrep) / (precision_semgrep + recall_semgrep) if (precision_semgrep + recall_semgrep) > 0 else 0

    # --- Evaluate CodeQL ---
    tp_codeql, fp_codeql, fn_codeql = 0, 0, 0
    if codeql_results_path.exists():
        codeql_results = load_jsonl(codeql_results_path)
        codeql_findings_map = {}
        for res in codeql_results:
            func_id = res.get("id") or res.get("func_id")
            if func_id is None:
                continue
            prediction = res.get("predicted_vulnerable")
            codeql_findings_map[func_id] = bool(prediction)

        for func_id, is_vulnerable in ground_truth_map.items():
            found_by_codeql = codeql_findings_map.get(func_id, False)
            if is_vulnerable and found_by_codeql:
                tp_codeql += 1
            elif not is_vulnerable and found_by_codeql:
                fp_codeql += 1
            elif is_vulnerable and not found_by_codeql:
                fn_codeql += 1

    precision_codeql = tp_codeql / (tp_codeql + fp_codeql) if (tp_codeql + fp_codeql) > 0 else 0
    recall_codeql = tp_codeql / (tp_codeql + fn_codeql) if (tp_codeql + fn_codeql) > 0 else 0
    f1_codeql = 2 * (precision_codeql * recall_codeql) / (precision_codeql + recall_codeql) if (precision_codeql + recall_codeql) > 0 else 0

    # --- Evaluate Security Agent (Placeholder) ---
    # This part should be implemented once the security-agent runner is complete
    precision_agent, recall_agent, f1_agent = 0.0, 0.0, 0.0 # Placeholder values

    # --- Summary ---
    summary = {
        "primevul": {
            "semgrep": {
                "precision": precision_semgrep,
                "recall": recall_semgrep,
                "f1_score": f1_semgrep,
                "tp": tp_semgrep,
                "fp": fp_semgrep,
                "fn": fn_semgrep,
            },
            "codeql": {
                "precision": precision_codeql,
                "recall": recall_codeql,
                "f1_score": f1_codeql,
                "tp": tp_codeql,
                "fp": fp_codeql,
                "fn": fn_codeql,
            },
            "security_agent": {
                "precision": precision_agent, # Placeholder
                "recall": recall_agent,       # Placeholder
                "f1_score": f1_agent,         # Placeholder
            },
        }
    }

    print(f"    Evaluation summary saved to {EVALUATION_OUTPUT_PATH}")
    with open(EVALUATION_OUTPUT_PATH, "w") as f:
        json.dump(summary, f, indent=2)

def main():
    """Main evaluation function."""
    evaluate_primevul()

if __name__ == "__main__":
    main()

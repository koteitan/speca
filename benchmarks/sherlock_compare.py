#!/usr/bin/env python3
"""Compare audit map findings against Sherlock CSV dataset with 3-stage matching."""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import subprocess
import random
from math import comb
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from benchmarks.bench_utils import normalize_bool

ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass
class Issue:
    issue_id: str
    title: str
    description: str
    text: str
    normalized: str
    tokens: set[str]


@dataclass
class AuditItem:
    item_id: str
    description: str
    snippet: str
    file: str
    line: str
    text: str
    normalized: str
    tokens: set[str]


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9_]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def tokenize(text: str) -> set[str]:
    if not text:
        return set()
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_csv_issues(path: Path) -> list[Issue]:
    issues: list[Issue] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            title = (row.get("title") or "").strip()
            description = (row.get("description") or "").strip()
            issue_id = str(row.get("number") or "").strip()
            text = f"{title}\n{description}".strip()
            normalized = normalize_text(text)
            tokens = tokenize(text)
            issues.append(Issue(issue_id, title, description, text, normalized, tokens))
    return issues


def build_audit_text(raw: dict) -> tuple[str, str, str, str, str]:
    item_id = str(raw.get("id") or raw.get("check_id") or "")
    description = str(raw.get("description") or raw.get("summary") or "")
    snippet = str(raw.get("snippet") or "")
    file = str(raw.get("file") or "")
    line = str(raw.get("line") or "")

    code_scope = raw.get("code_scope") if isinstance(raw.get("code_scope"), dict) else {}
    scope_desc = str(code_scope.get("description") or "")

    text_parts = [description, scope_desc, snippet, file, line]
    text = "\n".join(part for part in text_parts if part).strip()
    return item_id, description, snippet, file, line if line else "", text


def extract_audit_items(files: Iterable[Path]) -> list[AuditItem]:
    items: list[AuditItem] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        raw_items: list[dict] = []
        if isinstance(payload, dict) and isinstance(payload.get("audit_items"), list):
            raw_items = [item for item in payload.get("audit_items") if isinstance(item, dict)]
        elif isinstance(payload, list):
            raw_items = [item for item in payload if isinstance(item, dict)]

        if not raw_items:
            continue

        for raw in raw_items:
            item_id, description, snippet, file, line, text = build_audit_text(raw)
            normalized = normalize_text(text)
            tokens = tokenize(text)
            items.append(AuditItem(item_id, description, snippet, file, line, text, normalized, tokens))
    return items


def select_top_candidates(audit_item: AuditItem, issues: list[Issue], top_k: int) -> list[Issue]:
    scored: list[tuple[float, Issue]] = []
    for issue in issues:
        score = jaccard(audit_item.tokens, issue.tokens)
        scored.append((score, issue))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [issue for score, issue in scored[:top_k] if score > 0.0]


def call_claude(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "--output-format", "json", "-p", prompt],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def extract_json_from_text(text: str) -> dict | None:
    if not text:
        return None
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list) and payload:
            return payload[0] if isinstance(payload[0], dict) else None
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from Claude wrapper
    try:
        wrapper = json.loads(text)
        if isinstance(wrapper, dict) and "content" in wrapper:
            content = wrapper.get("content")
            if isinstance(content, list):
                combined = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            else:
                combined = str(content)
            match = re.search(r"\{.*\}", combined, flags=re.DOTALL)
            if match:
                return json.loads(match.group(0))
    except Exception:
        return None

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def llm_match(audit_item: AuditItem, candidates: list[Issue]) -> tuple[bool, str | None, float]:
    if not candidates:
        return False, None, 0.0

    candidate_block = []
    for idx, issue in enumerate(candidates):
        candidate_block.append(
            f"[{idx}] ID={issue.issue_id}\nTitle: {issue.title}\nDescription: {issue.description}\n"
        )

    prompt = (
        "You are matching security findings. Decide if the audit finding matches any candidate issue."
        " Respond with JSON only: {\"match\": true|false, \"candidate_index\": number|null, \"confidence\": 0-1}.\n\n"
        "Audit finding:\n"
        f"{audit_item.text}\n\n"
        "Candidates:\n"
        + "\n".join(candidate_block)
        + "\n"
    )

    raw = call_claude(prompt)
    payload = extract_json_from_text(raw) or {}
    match = bool(payload.get("match"))
    idx = payload.get("candidate_index")
    confidence = payload.get("confidence")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    if match and isinstance(idx, int) and 0 <= idx < len(candidates):
        return True, candidates[idx].issue_id, confidence
    return False, None, confidence


def parse_branches(value: str) -> list[str]:
    parts = [item.strip() for item in value.split(",")]
    return [p for p in parts if p]


def sanitize_branch(branch: str) -> str:
    return branch.replace("/", "__")


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = 0.0
    for i in range(k + 1):
        tail += comb(n, i) * (0.5**n)
    p = 2 * tail
    return min(p, 1.0)


def effect_size_cliffs_delta(b: int, c: int, n: int) -> tuple[float, str]:
    if n == 0:
        return 0.0, "none"
    delta = (b - c) / n
    magnitude = abs(delta)
    if magnitude < 0.147:
        label = "negligible"
    elif magnitude < 0.33:
        label = "small"
    elif magnitude < 0.474:
        label = "medium"
    else:
        label = "large"
    return delta, label


def bootstrap_rate(values: list[bool], samples: int, seed: int, ci_level: float) -> dict:
    if not values:
        return {"mean": 0.0, "ci": [0.0, 0.0]}
    rng = random.Random(seed)
    rates = []
    for _ in range(samples):
        sampled = [values[rng.randrange(len(values))] for _ in range(len(values))]
        rates.append(sum(1 for v in sampled if v) / len(sampled))
    rates.sort()
    ci_low = (1 - ci_level) / 2
    ci_high = 1 - ci_low
    low_idx = int(ci_low * (len(rates) - 1))
    high_idx = int(ci_high * (len(rates) - 1))
    return {"mean": sum(rates) / len(rates), "ci": [rates[low_idx], rates[high_idx]]}


def extract_human_label(record: dict) -> bool | None:
    for key in (
        "label",
        "is_valid_bug",
        "is_bug",
        "is_true_positive",
        "valid",
        "bug",
        "verdict",
    ):
        if key in record:
            value = normalize_bool(record.get(key))
            if value is not None:
                return value
    return None


def match_branch(
    branch: str,
    issues: list[Issue],
    results_dir: Path,
    use_llm: bool,
    llm_max: int,
    stage1_threshold: float,
    stage2_threshold: float,
) -> tuple[dict, list[AuditItem]]:
    sanitized = sanitize_branch(branch)
    branch_dir = results_dir / sanitized
    files = sorted(branch_dir.glob("03_*.json"))
    audit_items = extract_audit_items(files)

    matches: dict[str, dict] = {}
    stage_counts = {"stage1": 0, "stage2": 0, "stage3": 0}
    llm_calls = 0

    for item in audit_items:
        best_score = 0.0
        best_issue = None
        for issue in issues:
            score = similarity(item.normalized, issue.normalized)
            if score > best_score:
                best_score = score
                best_issue = issue
        if best_issue and best_score >= stage1_threshold:
            matches[item.item_id] = {
                "stage": "stage1",
                "issue_id": best_issue.issue_id,
                "score": best_score,
            }
            stage_counts["stage1"] += 1

    for item in audit_items:
        if item.item_id in matches:
            continue
        best_score = 0.0
        best_issue = None
        for issue in issues:
            overlap = len(item.tokens & issue.tokens)
            score = jaccard(item.tokens, issue.tokens)
            if score > best_score and overlap >= 3:
                best_score = score
                best_issue = issue
        if best_issue and best_score >= stage2_threshold:
            matches[item.item_id] = {
                "stage": "stage2",
                "issue_id": best_issue.issue_id,
                "score": best_score,
            }
            stage_counts["stage2"] += 1

    if use_llm:
        for item in audit_items:
            if item.item_id in matches:
                continue
            if llm_calls >= llm_max:
                break
            candidates = select_top_candidates(item, issues, top_k=5)
            if not candidates:
                continue
            llm_calls += 1
            matched, issue_id, confidence = llm_match(item, candidates)
            if matched and issue_id:
                matches[item.item_id] = {
                    "stage": "stage3",
                    "issue_id": issue_id,
                    "score": confidence,
                }
                stage_counts["stage3"] += 1

    total = len(audit_items)
    matched_total = len(matches)
    new_total = total - matched_total
    overlap_rate = matched_total / total if total else 0.0
    new_rate = new_total / total if total else 0.0

    detail = {
        "branch": branch,
        "sanitized_branch": sanitized,
        "items_total": total,
        "matched_total": matched_total,
        "new_total": new_total,
        "overlap_rate": overlap_rate,
        "new_rate": new_rate,
        "stage_counts": stage_counts,
        "llm_used": use_llm,
        "llm_calls": llm_calls,
        "matches": matches,
    }

    detail_path = results_dir / f"evaluation_{sanitized}.json"
    detail_path.write_text(json.dumps(detail, indent=2), encoding="utf-8")
    return detail, audit_items


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Sherlock dataset vs audit map outputs")
    parser.add_argument("--branches", required=True, help="Comma-separated branch names")
    parser.add_argument(
        "--csv",
        default=str(
            ROOT_DIR
            / "benchmarks"
            / "dataset"
            / "sherlock_ethereum_audit_contest"
            / "sherlock_contest_1140_issues_1766639267091.csv"
        ),
    )
    parser.add_argument(
        "--results-dir",
        default=str(ROOT_DIR / "benchmarks" / "results" / "sherlock_ethereum_audit_contest"),
    )
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--llm-max", type=int, default=200)
    parser.add_argument("--stage1-threshold", type=float, default=0.88)
    parser.add_argument("--stage2-threshold", type=float, default=0.25)
    parser.add_argument("--baseline-results", type=str, default="", help="Baseline results dir with evaluation_*.json")
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=42)
    parser.add_argument("--ci-level", type=float, default=0.95)
    parser.add_argument("--human-scope", type=str, default="new_only", choices=["new_only", "all"])
    parser.add_argument("--human-sample-size", type=int, default=0)
    parser.add_argument(
        "--human-sample-out",
        type=str,
        default="",
        help="Output path for human evaluation sample JSONL",
    )
    parser.add_argument("--human-labels", type=str, default="", help="Human labels JSONL path")
    parser.add_argument("--human-labels-report", type=str, default="", help="Validation report output path (JSON)")
    parser.add_argument("--metadata", type=str, default="", help="Run metadata JSON to include in summary")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    issues = load_csv_issues(Path(args.csv))
    issue_map = {issue.issue_id: issue for issue in issues}

    summary = {
        "dataset": {
            "path": str(args.csv),
            "issues": len(issues),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "branches": {},
    }
    if args.metadata:
        metadata_path = Path(args.metadata)
        if metadata_path.exists():
            try:
                summary["run_metadata"] = json.loads(metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                summary["run_metadata"] = {"error": "invalid_json", "path": str(metadata_path)}

    baseline_dir = Path(args.baseline_results) if args.baseline_results else None
    human_candidates: list[dict] = []
    human_lookup: dict[tuple[str, str], dict] = {}

    for branch in parse_branches(args.branches):
        detail, audit_items = match_branch(
            branch,
            issues,
            results_dir,
            args.use_llm,
            args.llm_max,
            args.stage1_threshold,
            args.stage2_threshold,
        )
        matched_flags = [item.item_id in detail["matches"] for item in audit_items]
        overlap_ci = bootstrap_rate(
            matched_flags,
            samples=args.bootstrap_samples,
            seed=args.bootstrap_seed,
            ci_level=args.ci_level,
        )
        new_ci = bootstrap_rate(
            [not flag for flag in matched_flags],
            samples=args.bootstrap_samples,
            seed=args.bootstrap_seed,
            ci_level=args.ci_level,
        )

        baseline_stats = {}
        if baseline_dir:
            baseline_path = baseline_dir / f"evaluation_{detail['sanitized_branch']}.json"
            if baseline_path.exists():
                baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
                baseline_matches = baseline.get("matches", {})
                b = c = 0
                n = 0
                for item in audit_items:
                    current_matched = item.item_id in detail["matches"]
                    baseline_matched = item.item_id in baseline_matches
                    n += 1
                    if current_matched and not baseline_matched:
                        b += 1
                    elif not current_matched and baseline_matched:
                        c += 1
                p_value = mcnemar_exact(b, c)
                delta, magnitude = effect_size_cliffs_delta(b, c, n)
                baseline_stats = {
                    "baseline_path": str(baseline_path),
                    "n": n,
                    "discordant": {"current_only_matched": b, "baseline_only_matched": c},
                    "mcnemar_p": p_value,
                    "effect_size": {"cliffs_delta": delta, "magnitude": magnitude},
                }

        summary["branches"][branch] = {
            "items_total": detail["items_total"],
            "matched_total": detail["matched_total"],
            "new_total": detail["new_total"],
            "overlap_rate": detail["overlap_rate"],
            "new_rate": detail["new_rate"],
            "overlap_rate_ci": overlap_ci,
            "new_rate_ci": new_ci,
            "stage_counts": detail["stage_counts"],
            "llm_used": detail["llm_used"],
            "llm_calls": detail["llm_calls"],
        }
        if baseline_stats:
            summary["branches"][branch]["baseline_comparison"] = baseline_stats

        for item in audit_items:
            matched = item.item_id in detail["matches"]
            if args.human_scope == "new_only" and matched:
                continue
            issue_id = detail["matches"].get(item.item_id, {}).get("issue_id")
            issue = issue_map.get(issue_id) if issue_id else None
            record = {
                "branch": branch,
                "item_id": item.item_id,
                "matched": matched,
                "stage": detail["matches"].get(item.item_id, {}).get("stage") if matched else None,
                "issue_id": issue_id,
                "issue_title": issue.title if issue else None,
                "issue_description": issue.description if issue else None,
                "description": item.description,
                "snippet": item.snippet,
                "file": item.file,
                "line": item.line,
                "text": item.text,
            }
            human_candidates.append(record)
            human_lookup[(branch, item.item_id)] = record

    summary_path = results_dir / "evaluation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if args.human_sample_size > 0 and human_candidates:
        rng = random.Random(args.bootstrap_seed)
        sample_size = min(args.human_sample_size, len(human_candidates))
        sampled = rng.sample(human_candidates, k=sample_size)
        out_path = Path(args.human_sample_out) if args.human_sample_out else results_dir / "human_eval_sample.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as handle:
            for record in sampled:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    if args.human_labels:
        labels_path = Path(args.human_labels)
        if labels_path.exists():
            labeled = 0
            positives = 0
            labels = []
            invalid = []
            for line in labels_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    invalid.append({"reason": "invalid_json"})
                    continue
                branch = record.get("branch")
                item_id = record.get("item_id")
                if not branch or not item_id:
                    invalid.append({"reason": "missing_branch_or_item_id", "record": record})
                    continue
                label = extract_human_label(record)
                if label is None:
                    invalid.append({"reason": "missing_or_invalid_label", "record": record})
                    continue
                if (branch, item_id) not in human_lookup:
                    invalid.append({"reason": "unknown_item_id", "record": record})
                    continue
                labeled += 1
                if label:
                    positives += 1
                labels.append(label)
            human_stats = {
                "scope": args.human_scope,
                "labeled_total": labeled,
                "true_bug": positives,
                "precision": positives / labeled if labeled else 0.0,
                "precision_ci": bootstrap_rate(labels, args.bootstrap_samples, args.bootstrap_seed, args.ci_level),
                "bootstrap": {
                    "samples": args.bootstrap_samples,
                    "ci_level": args.ci_level,
                    "seed": args.bootstrap_seed,
                },
                "invalid_label_rows": len(invalid),
            }
            summary["human_eval"] = human_stats
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            if args.human_labels_report:
                report_path = Path(args.human_labels_report)
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report = {
                    "labels_path": str(labels_path),
                    "invalid_count": len(invalid),
                    "invalid_samples": invalid[:50],
                }
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

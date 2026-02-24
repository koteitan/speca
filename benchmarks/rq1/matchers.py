#!/usr/bin/env python3
"""RQ1 matching logic (stage1/2/3)."""

from __future__ import annotations

import difflib
import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


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
    classification: str | None = None


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
    import csv

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


def build_audit_text(raw: dict) -> tuple[str, str, str, str, str, str, str]:
    """Extract fields from a Phase 03 audit item.

    Phase 03 schema: property_id, classification, code_path, proof_trace, attack_scenario, checklist_id
    code_path format: "file.go::func::L10-20"
    """
    item_id = str(raw.get("property_id") or "")
    description = str(raw.get("proof_trace") or "")
    snippet = str(raw.get("attack_scenario") or "")
    classification = str(raw.get("classification") or "")

    code_path = str(raw.get("code_path") or "")
    parts = code_path.split("::")
    file = parts[0] if parts else ""
    line = parts[-1] if len(parts) > 1 else ""

    text_parts = [description, snippet, file, line]
    text = "\n".join(part for part in text_parts if part).strip()
    return item_id, description, snippet, file, line, text, classification


def is_selected_audit_item(
    raw: dict,
    classification_filter: set[str] | None,
) -> bool:
    if classification_filter is None:
        return True
    value = raw.get("classification")
    if isinstance(value, str) and value.strip().lower() in classification_filter:
        return True
    return False


def extract_audit_items(
    files: Iterable[Path],
    classification_filter: set[str] | None = None,
) -> list[AuditItem]:
    items: list[AuditItem] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        raw_items: list[dict] = []
        if isinstance(payload, dict) and isinstance(payload.get("audit_items"), list):
            raw_items = [item for item in payload["audit_items"] if isinstance(item, dict)]

        if not raw_items:
            continue

        for raw in raw_items:
            if not is_selected_audit_item(raw, classification_filter):
                continue
            item_id, description, snippet, file, line, text, classification = build_audit_text(raw)
            normalized = normalize_text(text)
            tokens = tokenize(text)
            items.append(
                AuditItem(
                    item_id, description, snippet, file, line,
                    text, normalized, tokens, classification=classification,
                )
            )
    return items


def call_llm(prompt: str) -> str:
    command_override = os.environ.get("LLM_COMMAND")
    if command_override:
        base = shlex.split(command_override)
        command = base + [prompt]
    else:
        provider = os.environ.get("LLM_PROVIDER", "claude").strip().lower()
        if provider == "codex":
            command = [
                "codex",
                "exec",
                "--sandbox",
                "read-only",
                "--ask-for-approval",
                "never",
                prompt,
            ]
        else:
            command = ["claude", "--output-format", "json", "-p", prompt]

    result = subprocess.run(
        command,
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


def _truncate_description(description: str, max_chars: int = 300) -> str:
    if len(description) <= max_chars:
        return description
    return description[:max_chars].rstrip() + "..."


def llm_match(audit_item: AuditItem, candidates: list[Issue], llm_id: str) -> tuple[bool, str | None, float]:
    if not candidates:
        return False, None, 0.0

    candidate_block = []
    for idx, issue in enumerate(candidates):
        truncated = _truncate_description(issue.description)
        candidate_block.append(
            f"[{idx}] ID={issue.issue_id}\nTitle: {issue.title}\nDescription: {truncated}\n"
        )

    prompt = (
        "You are matching an automated code-analysis finding against human-written bug reports.\n\n"
        "The AUDIT FINDING below was produced by an automated security analyzer. "
        "It contains file paths, proof traces, and attack scenarios extracted from static analysis.\n\n"
        "The CANDIDATE ISSUES below are human-written bug reports from a security contest. "
        "They use natural language, markdown, PoC code, and root-cause analysis.\n\n"
        "Two items MATCH if they describe the SAME underlying vulnerability or root cause, even if "
        "the wording is completely different. Key signals:\n"
        "- Same code file or function is implicated\n"
        "- Same vulnerability mechanism (e.g., missing validation, race condition, overflow)\n"
        "- Same security impact or exploit path\n\n"
        "Respond with JSON only: "
        '{"match": true|false, "candidate_index": number|null, "confidence": 0.0-1.0}\n\n'
        "AUDIT FINDING:\n"
        f"{audit_item.text}\n\n"
        f"CANDIDATE ISSUES ({len(candidates)} total):\n"
        + "\n".join(candidate_block)
        + "\n"
    )

    print(f"[rq1] {llm_id}: llm_match start (candidates={len(candidates)})")
    raw = call_llm(prompt)
    print(f"[rq1] {llm_id}: llm_match done (bytes={len(raw) if raw else 0})")
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


def _rank_candidates_by_jaccard(
    audit_item: AuditItem,
    issues: list[Issue],
    max_candidates: int = 50,
) -> list[Issue]:
    if len(issues) <= max_candidates:
        return list(issues)
    scored = []
    for issue in issues:
        score = jaccard(audit_item.tokens, issue.tokens)
        scored.append((score, issue))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [issue for _, issue in scored[:max_candidates]]


def match_items(
    audit_items: list[AuditItem],
    issues: list[Issue],
    use_llm: bool,
    llm_max: int,
    stage1_threshold: float,
    stage2_threshold: float,
) -> tuple[dict[str, dict], dict, int]:
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
            candidates = _rank_candidates_by_jaccard(item, issues)
            if not candidates:
                continue
            llm_calls += 1
            llm_id = item.item_id or f"item_{llm_calls}"
            matched, issue_id, confidence = llm_match(item, candidates, llm_id)
            if matched and issue_id:
                matches[item.item_id] = {
                    "stage": "stage3",
                    "issue_id": issue_id,
                    "score": confidence,
                }
                stage_counts["stage3"] += 1

    return matches, stage_counts, llm_calls

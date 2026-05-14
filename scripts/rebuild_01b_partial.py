"""Rebuild 01b PARTIAL JSON files from existing .mmd outputs.

Workaround for Phase 01b runner bug where worker results are recorded as 'empty'
because the worker's text response doesn't include a ```json``` code block, so
runner._parse_results_from_log returns []. Meanwhile the .mmd files are actually
written to disk successfully.

This script scans graphs/batch_*/{spec_id}/SG-*.mmd and builds Phase01bPartial
JSON manifests so 01e can pick them up.
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

if len(sys.argv) < 2:
    print("usage: rebuild_01b_partial.py <output_dir>", file=sys.stderr)
    sys.exit(2)

out_root = Path(sys.argv[1])
graphs_dir = out_root / "graphs"
state_file = out_root / "01a_STATE.json"

with open(state_file, encoding="utf-8") as f:
    state = json.load(f)

slug_to_url: dict[str, dict[str, str]] = {}
for spec in state["found_specs"]:
    url = spec["url"]
    title = spec.get("title", "")
    base = url.rstrip("/").rsplit("/", 1)[-1]
    base = re.sub(r"\.(mediawiki|md|html|txt)$", "", base, flags=re.I)
    slug_candidates = {
        base.lower(),
        base.lower().replace("_", "-"),
        f"litecoin-{base.lower()}",
    }
    for cand in slug_candidates:
        slug_to_url.setdefault(cand, {"url": url, "title": title})

specs_by_id: dict[str, dict] = {}
for batch_dir in sorted(graphs_dir.iterdir()):
    if not batch_dir.is_dir():
        continue
    for spec_dir in batch_dir.iterdir():
        if not spec_dir.is_dir():
            continue
        spec_id = spec_dir.name
        mmd_files = sorted(spec_dir.glob("SG-*.mmd"))
        if not mmd_files:
            continue
        meta = slug_to_url.get(spec_id.lower(), {"url": f"unknown://{spec_id}", "title": spec_id})
        sub_graphs = []
        for mf in mmd_files:
            m = re.match(r"(SG-\d+)_(.+)\.mmd$", mf.name)
            if not m:
                continue
            sg_id, sg_name = m.group(1), m.group(2).replace("_", " ")
            try:
                content = mf.read_text(encoding="utf-8")
            except Exception:
                content = ""
            invariants = re.findall(r"INV:\s*([^\n]+)", content)
            sub_graphs.append({
                "id": sg_id,
                "name": sg_name,
                "mermaid_file": str(mf.resolve().relative_to(Path.cwd())).replace("\\", "/"),
                "program_graph": {"nodes": [], "initial": "", "final": [], "actions": [], "edges": []},
                "invariants": invariants,
            })
        specs_by_id.setdefault(spec_id, {
            "source_url": meta["url"],
            "title": meta["title"] or spec_id,
            "sub_graphs": [],
        })
        existing_ids = {sg["id"] for sg in specs_by_id[spec_id]["sub_graphs"]}
        for sg in sub_graphs:
            if sg["id"] not in existing_ids:
                specs_by_id[spec_id]["sub_graphs"].append(sg)

# Remove any pre-existing rebuilt file
old = out_root / "01b_PARTIAL_W0B0_rebuilt.json"
old.unlink(missing_ok=True)
for old in out_root.glob("01b_PARTIAL_W*B*_rebuilt*.json"):
    old.unlink()

# Write one PARTIAL per spec (matches design: batch_size=1, file_path per spec)
total_subgraphs = 0
for idx, (spec_id, spec_data) in enumerate(specs_by_id.items()):
    if not spec_data["sub_graphs"]:
        continue
    partial = {
        "specs": [spec_data],
        "metadata": {
            "rebuilt_from_disk": True,
            "rebuild_script": "scripts/rebuild_01b_partial.py",
            "spec_id": spec_id,
        },
    }
    out_path = out_root / f"01b_PARTIAL_W0B{idx}_rebuilt.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(partial, f, indent=2, ensure_ascii=False)
    total_subgraphs += len(spec_data["sub_graphs"])

print(f"wrote {len(specs_by_id)} 01b_PARTIAL files to {out_root}")
print(f"  total subgraphs: {total_subgraphs}")

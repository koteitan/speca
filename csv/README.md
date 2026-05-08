# `csv/` — legacy snapshot of audit-finding corpora

Going forward, **the canonical home for SPECA's curated audit-finding
datasets is HuggingFace**: a single repo with one config per domain.

| Dataset | URL |
|---|---|
| SPECA Vulnerability Reports (multi-config) | https://huggingface.co/datasets/NyxFoundation/vulnerability-reports |

Pick a domain at load time. Use the loader helper rather than reading
these CSVs directly:

```python
from scripts.datasets.load import load_findings

df = load_findings(domain="defi")          # default repo + config
```

Or directly via `datasets`:

```python
from datasets import load_dataset

ds = load_dataset("NyxFoundation/vulnerability-reports", "defi", split="train")
```

The pipeline that produces the HF dataset lives at
[`scripts/datasets/`](../scripts/datasets/) — see its README for the
operator workflow.

## What's still in this directory

The CSVs in `csv/` predate the HF migration and are kept until the
follow-up history-rewrite issue runs. They are **not** the canonical
source any more; treat them as historical artifacts.

| File | Successor on HF |
|---|---|
| `similar_audit_findings.csv` | `NyxFoundation/vulnerability-reports`, config `defi` (full corpus, deduped, schema-normalized) |
| `defi_all_high_medium.csv`, `code4rena_high_medium.csv`, `sherlock_high_medium.csv` | filter the `defi` config to `severity in {High, Medium}` |
| `past_defi_patterns*.csv` | derived views — will move to a dedicated config in a follow-up |
| `chainlink_v2_audit_patterns.csv` | task-specific filter; not migrated yet |
| `audit_findings_db.csv` | hand-curated mini-DB; not migrated yet |
| `solodit_checklist.csv` | upstream Solodit checklist; may become its own config later |

If you intentionally need to update one of these in place (rare;
prefer republishing via the HF pipeline), use `git add -f <path>` —
otherwise the `.gitignore` rule introduced with the HF migration will
silently ignore the change.

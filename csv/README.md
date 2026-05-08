# `csv/` — legacy snapshot of audit-finding corpora

Going forward, **the canonical home for SPECA's curated audit-finding
datasets is HuggingFace**, under the `NyxFoundation` org:

| Dataset | URL |
|---|---|
| DeFi audit findings | https://huggingface.co/datasets/NyxFoundation/defi-audit-findings |

Use the loader helper rather than reading these CSVs directly:

```python
from scripts.datasets.load import load_findings

df = load_findings(domain="defi")          # default: pulls from HF
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
| `similar_audit_findings.csv` | `NyxFoundation/defi-audit-findings` (full corpus, deduped, schema-normalized) |
| `defi_all_high_medium.csv`, `code4rena_high_medium.csv`, `sherlock_high_medium.csv` | filter `domain == "defi"` + severity in {High, Medium} on the same dataset |
| `past_defi_patterns*.csv` | derived views — will move to a dedicated dataset in a follow-up |
| `chainlink_v2_audit_patterns.csv` | task-specific filter; not migrated yet |
| `audit_findings_db.csv` | hand-curated mini-DB; not migrated yet |
| `solodit_checklist.csv` | upstream Solodit checklist; not migrated yet |

If you intentionally need to update one of these in place (rare;
prefer republishing via the HF pipeline), use `git add -f <path>` —
otherwise the `.gitignore` rule introduced with the HF migration will
silently ignore the change.

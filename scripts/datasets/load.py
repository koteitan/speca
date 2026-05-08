"""load.py — single entry point for SPECA audit-finding corpora hosted on
HuggingFace under the `NyxFoundation` org.

Consumers should prefer this helper over reading CSVs directly. The
canonical source of truth is HF; CSVs are scratch artifacts.

Example:
    from scripts.datasets.load import load_findings

    # Pulls NyxFoundation/defi-audit-findings (cached locally after first run).
    df = load_findings(domain="defi")
    print(df.columns.tolist())
    # ['id', 'source_platform', 'contest', 'issue_id', 'severity',
    #  'title', 'description', 'source_url', 'domain', 'scraped_at',
    #  'source']
    # NOTE: the published parquet ships only `source_platform`. `source` is
    # a *client-side* alias added by this loader (see add_compat_aliases),
    # purely so older consumers that still reference `row['source']` keep
    # working without code changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

DEFAULT_REPO_TEMPLATE = "NyxFoundation/{domain}-audit-findings"


def load_findings(
    domain: str = "defi",
    *,
    repo_id: str | None = None,
    split: str = "train",
    local_parquet: str | Path | None = None,
    revision: str = "main",
    add_compat_aliases: bool = True,
) -> "pd.DataFrame":
    """Load a SPECA audit-findings dataset.

    Resolution:
        1. If `local_parquet` is given, read it directly. Useful for tests
           and offline development against a freshly-built artifact.
        2. Otherwise, fetch from HF via `datasets.load_dataset`, using
           `repo_id` (default: `NyxFoundation/<domain>-audit-findings`).

    `add_compat_aliases=True` adds a `source` column as a copy of
    `source_platform`, since pre-migration consumers reference the
    former name.
    """
    import pandas as pd

    if local_parquet is not None:
        df = pd.read_parquet(str(local_parquet))
    else:
        from datasets import load_dataset

        rid = repo_id or DEFAULT_REPO_TEMPLATE.format(domain=domain)
        ds = load_dataset(rid, split=split, revision=revision)
        df = ds.to_pandas()

    if add_compat_aliases and "source_platform" in df.columns and "source" not in df.columns:
        df["source"] = df["source_platform"]

    return df

"""classify_stride_cwe.py — enrich the ethereum train.parquet with STRIDE and
CWE-Top-25 (2024) classifications using the Anthropic Batch API (Haiku model).

Usage:
    python -m scripts.datasets.classify_stride_cwe \\
        [--in  dist/datasets/ethereum/train.parquet] \\
        [--out dist/datasets/ethereum/train.classified.parquet] \\
        [--batch-size 1000] \\
        [--dry-run]

New columns added (downstream of build_derived; build_derived itself is NOT
modified):
    stride      str  one of STRIDE_VALUES
    cwe_top25   str  one of CWE_TOP25_IDS or "N/A"

Environment:
    ANTHROPIC_API_KEY  required unless --dry-run is passed
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STRIDE_VALUES = frozenset(
    [
        "Spoofing",
        "Tampering",
        "Repudiation",
        "Information Disclosure",
        "Denial of Service",
        "Elevation of Privilege",
        "Other",
    ]
)

CWE_TOP25_IDS = frozenset(
    [
        "CWE-79",
        "CWE-787",
        "CWE-89",
        "CWE-352",
        "CWE-22",
        "CWE-125",
        "CWE-78",
        "CWE-416",
        "CWE-862",
        "CWE-434",
        "CWE-94",
        "CWE-20",
        "CWE-77",
        "CWE-287",
        "CWE-269",
        "CWE-502",
        "CWE-200",
        "CWE-863",
        "CWE-918",
        "CWE-119",
        "CWE-476",
        "CWE-798",
        "CWE-190",
        "CWE-400",
        "CWE-306",
    ]
)

MODEL_ID = "claude-haiku-4-5-20251001"
DESCRIPTION_MAX_CHARS = 2000
DEFAULT_POLL_INTERVAL_S = 15
DEFAULT_TIMEOUT_S = 90 * 60  # 90 minutes

CLASSIFY_PROMPT = """\
You are a security analyst. Classify the following Ethereum-client past-fix record by STRIDE category and CWE-Top-25 (2024) id.

Rules:
- Output ONLY a single JSON object. No prose, no markdown fences.
- "stride" must be exactly one of: "Spoofing", "Tampering", "Repudiation", "Information Disclosure", "Denial of Service", "Elevation of Privilege", "Other".
- "cwe_top25" must be exactly one of the 25 ids in the 2024 CWE-Top-25 list (CWE-79, CWE-787, CWE-89, CWE-352, CWE-22, CWE-125, CWE-78, CWE-416, CWE-862, CWE-434, CWE-94, CWE-20, CWE-77, CWE-287, CWE-269, CWE-502, CWE-200, CWE-863, CWE-918, CWE-119, CWE-476, CWE-798, CWE-190, CWE-400, CWE-306) OR "N/A" if no Top-25 entry fits.
- If the record is too vague to classify (e.g. a commit subject like "fix bug"), return {"stride": "Other", "cwe_top25": "N/A"}.

Examples:

Record: title="DoS via crafted block", description="Specially-crafted block triggers exponential validation cost"
Output: {"stride": "Denial of Service", "cwe_top25": "CWE-400"}

Record: title="Improper ECIES Public Key Validation in RLPx Handshake", description="A peer can supply a malformed ECIES key during handshake; validation accepts it"
Output: {"stride": "Spoofing", "cwe_top25": "CWE-287"}

Record: title="Memory leak in eth_getLogs", description="Repeated calls to the eth_getLogs RPC retain block iterator references"
Output: {"stride": "Denial of Service", "cwe_top25": "CWE-400"}

Record: title="Stack trace leaks peer multiaddr in error response", description="Verbose log path includes the remote peer's multiaddr"
Output: {"stride": "Information Disclosure", "cwe_top25": "CWE-200"}

Record: title="Integer overflow in tx fee calculation", description="64-bit fee math wraps on extreme inputs"
Output: {"stride": "Tampering", "cwe_top25": "CWE-190"}

Now classify this record:
title="{title}"
description="{description}"

Output:"""


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def parse_classification(text: str) -> dict:
    """Parse a Haiku classification response into a validated dict.

    Strips markdown fences defensively.  Coerces invalid enum values to
    "Other" / "N/A" rather than raising.
    """
    cleaned = text.strip()
    # Strip ```json ... ``` or ``` ... ``` fences
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Drop opening fence line
        lines = lines[1:]
        # Drop closing fence line if present
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"stride": "Other", "cwe_top25": "N/A"}

    stride = obj.get("stride", "Other")
    cwe = obj.get("cwe_top25", "N/A")

    if stride not in STRIDE_VALUES:
        stride = "Other"
    if cwe not in CWE_TOP25_IDS:
        cwe = "N/A"

    return {"stride": stride, "cwe_top25": cwe}


def build_batch_request(rows: list[dict]) -> list[dict]:
    """Build a list of Batch API request dicts (one per row).

    Each dict matches the shape expected by
    ``anthropic.types.MessageBatchIndividualRequest``.
    """
    requests = []
    for row in rows:
        title = str(row.get("title", "") or "")
        description = str(row.get("description", "") or "")
        description = description[:DESCRIPTION_MAX_CHARS]

        prompt = CLASSIFY_PROMPT.replace("{title}", title).replace("{description}", description)

        requests.append(
            {
                "custom_id": row["id"],
                "params": {
                    "model": MODEL_ID,
                    "max_tokens": 200,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                },
            }
        )
    return requests


# ---------------------------------------------------------------------------
# Main classify function
# ---------------------------------------------------------------------------


def classify(
    parquet_in: Path,
    parquet_out: Path,
    *,
    batch_size: int = 1000,
    dry_run: bool = False,
    poll_interval: int = DEFAULT_POLL_INTERVAL_S,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> dict:
    """Classify every row in ``parquet_in`` and write ``parquet_out``.

    Returns a manifest dict with run metadata.
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required; install with `uv sync --group datasets`") from exc

    started_at = datetime.now(timezone.utc).isoformat()
    df = pd.read_parquet(parquet_in)

    rows = df.to_dict(orient="records")
    n_rows = len(rows)
    n_classified = 0
    n_failed = 0
    batch_id: str | None = None

    stride_col = ["Other"] * n_rows
    cwe_col = ["N/A"] * n_rows

    if dry_run:
        logger.info("dry-run: skipping API call, assigning defaults to all %d rows", n_rows)
        ended_at = datetime.now(timezone.utc).isoformat()
        df["stride"] = stride_col
        df["cwe_top25"] = cwe_col
        parquet_out.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(parquet_out, index=False)
        return {
            "n_rows": n_rows,
            "n_classified": 0,
            "n_failed": 0,
            "batch_id": None,
            "started_at": started_at,
            "ended_at": ended_at,
            "model": MODEL_ID,
            "dry_run": True,
        }

    # --- Live path ---
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic SDK is required; install with `uv sync --group datasets`"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)

    # Build id → row-index map for stitching
    id_to_idx: dict[str, int] = {row["id"]: i for i, row in enumerate(rows)}

    # Process in chunks of batch_size
    all_requests = build_batch_request(rows)

    # Anthropic batch API processes all requests in one call (up to 10k).
    # If batch_size < n_rows we chunk into multiple batch calls.
    chunks = [
        all_requests[i : i + batch_size] for i in range(0, len(all_requests), batch_size)
    ]

    for chunk_idx, chunk in enumerate(chunks):
        logger.info(
            "submitting batch %d/%d (%d requests)", chunk_idx + 1, len(chunks), len(chunk)
        )
        batch = client.messages.batches.create(requests=chunk)
        batch_id = batch.id
        logger.info("batch_id=%s submitted", batch_id)

        # Poll until ended
        deadline = time.monotonic() + timeout
        while True:
            status_obj = client.messages.batches.retrieve(batch_id)
            status = status_obj.processing_status
            logger.info("batch %s status=%s", batch_id, status)
            if status == "ended":
                break
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"Batch {batch_id} did not finish within {timeout}s"
                )
            time.sleep(poll_interval)

        # Download results
        for result in client.messages.batches.results(batch_id):
            custom_id = result.custom_id
            idx = id_to_idx.get(custom_id)
            if idx is None:
                logger.warning("unknown custom_id in batch results: %s", custom_id)
                n_failed += 1
                continue

            if result.result.type == "succeeded":
                content = result.result.message.content
                # content is a list of blocks; grab first text block
                text = ""
                for block in content:
                    if hasattr(block, "text"):
                        text = block.text
                        break
                classification = parse_classification(text)
                stride_col[idx] = classification["stride"]
                cwe_col[idx] = classification["cwe_top25"]
                n_classified += 1
            else:
                logger.warning(
                    "batch item %s failed: %s", custom_id, result.result.type
                )
                n_failed += 1

    ended_at = datetime.now(timezone.utc).isoformat()

    df["stride"] = stride_col
    df["cwe_top25"] = cwe_col
    parquet_out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_out, index=False)
    logger.info("wrote %s", parquet_out)

    return {
        "n_rows": n_rows,
        "n_classified": n_classified,
        "n_failed": n_failed,
        "batch_id": batch_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "model": MODEL_ID,
        "dry_run": False,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Classify ethereum train.parquet rows with STRIDE + CWE-Top-25 via Haiku Batch API"
    )
    p.add_argument(
        "--in",
        dest="parquet_in",
        default="dist/datasets/ethereum/train.parquet",
        help="Input parquet path (default: dist/datasets/ethereum/train.parquet)",
    )
    p.add_argument(
        "--out",
        dest="parquet_out",
        default="dist/datasets/ethereum/train.classified.parquet",
        help="Output parquet path (default: dist/datasets/ethereum/train.classified.parquet)",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Max requests per Anthropic Batch call (default: 1000)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip API call; fill all rows with Other/N/A defaults",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    parquet_in = Path(args.parquet_in)
    parquet_out = Path(args.parquet_out)

    manifest = classify(
        parquet_in,
        parquet_out,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

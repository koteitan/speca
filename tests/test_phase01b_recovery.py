"""Tests for Phase01bOrchestrator's directory-scanning recovery hook (issue #24).

Verifies that when a Phase 01b worker writes ``.mmd`` artifacts to disk but
omits the JSON envelope on outer stdout, ``_recover_partial_from_disk``
reconstructs a payload that matches what ``ResultCollector.save_partial``
expects.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add workspace root to sys.path
_WORKSPACE_ROOT = str(Path(__file__).resolve().parent.parent)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

# Mock heavy dependencies before importing orchestrator modules
_MOCK_MODULES = {
    "tqdm": MagicMock(),
    "aiofiles": MagicMock(),
    "anthropic": MagicMock(),
    "tenacity": MagicMock(),
}
_patcher = patch.dict(sys.modules, _MOCK_MODULES)
_patcher.start()

from scripts.orchestrator.base import Phase01bOrchestrator
from scripts.orchestrator.config import get_phase_config
from scripts.orchestrator.schemas import Phase01bPartial

_patcher.stop()


_MMD_CONTENT = """---
title: "init (SPEC-A)"
---
stateDiagram-v2
    direction TB
    [*] --> q_init: x = 1
    q_init --> q_check: y = 2
    q_check --> [*]: x == y

    note right of q_check
        INV-001: x must equal y
    end note
"""


class TestPhase01bRecovery(unittest.TestCase):
    """Verify directory-scanning recovery for Phase 01b."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

        # Set SPECA_OUTPUT_DIR so get_output_root() points at the tmp tree.
        # The recovery hook resolves the output root at call time.
        self._old_env = os.environ.get("SPECA_OUTPUT_DIR")
        os.environ["SPECA_OUTPUT_DIR"] = str(self.tmp_root)

        # Layout the on-disk artifacts the runner would have created.
        self.timestamp = 1700000000
        self.batch_dir = (
            self.tmp_root
            / "graphs"
            / f"batch_w0b0_{self.timestamp}"
        )
        spec_dir = self.batch_dir / "SPEC-A"
        spec_dir.mkdir(parents=True)
        (spec_dir / "SG-001_init.mmd").write_text(_MMD_CONTENT, encoding="utf-8")

        # Queue + context files written by the runner before invocation.
        source_url = "https://example.com/specs/SPEC-A.md"
        queue_path = (
            self.tmp_root
            / f"01b_ASYNC_QUEUE_W0B0_{self.timestamp}.json"
        )
        context_path = (
            self.tmp_root
            / f"01b_CONTEXT_W0B0_{self.timestamp}.json"
        )
        queue_path.write_text(
            json.dumps({
                "worker_id": 0,
                "phase": "01b",
                "item_ids": [source_url],
                "total_items": 1,
                "context_file": str(context_path),
            }),
            encoding="utf-8",
        )
        context_path.write_text(
            json.dumps({
                source_url: {
                    "url": source_url,
                    "title": "SPEC-A",
                },
            }),
            encoding="utf-8",
        )

        # Build an orchestrator without invoking BaseOrchestrator.__init__
        # (which would create runners, queue managers, etc.).
        with patch("scripts.orchestrator.base.BaseOrchestrator.__init__", return_value=None):
            self.orchestrator = Phase01bOrchestrator.__new__(Phase01bOrchestrator)
            self.orchestrator.config = get_phase_config("01b").model_copy()

        self.source_url = source_url

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("SPECA_OUTPUT_DIR", None)
        else:
            os.environ["SPECA_OUTPUT_DIR"] = self._old_env
        self._tmp.cleanup()

    def test_recovers_single_spec_with_invariants(self):
        recovered = self.orchestrator._recover_partial_from_disk(0, 0)
        self.assertEqual(len(recovered), 1)

        spec = recovered[0]
        self.assertEqual(spec["source_url"], self.source_url)
        self.assertEqual(spec["title"], "SPEC-A")
        self.assertEqual(len(spec["sub_graphs"]), 1)

        sg = spec["sub_graphs"][0]
        self.assertEqual(sg["id"], "SG-001")
        self.assertEqual(sg["name"], "init")
        self.assertEqual(sg["mermaid_file"], "SPEC-A/SG-001_init.mmd")
        self.assertEqual(sg["invariants"], ["INV-001: x must equal y"])

    def test_recovered_payload_matches_phase01b_schema(self):
        """The recovered list must round-trip through Phase01bPartial unchanged."""
        recovered = self.orchestrator._recover_partial_from_disk(0, 0)
        envelope = {
            "specs": recovered,
            "metadata": {
                "phase": "01b",
                "worker_id": 0,
                "batch_index": 0,
                "item_count": len(recovered),
                "timestamp": self.timestamp,
                "processed_ids": [s.get("source_url", "") for s in recovered],
            },
        }
        # Pydantic should accept the envelope without errors.
        parsed = Phase01bPartial.model_validate(envelope)
        self.assertEqual(len(parsed.specs), 1)
        self.assertEqual(parsed.specs[0].sub_graphs[0].id, "SG-001")

    def test_returns_empty_when_no_batch_dir(self):
        """No batch directory → empty recovery (no crash)."""
        recovered = self.orchestrator._recover_partial_from_disk(9, 9)
        self.assertEqual(recovered, [])

    def test_handles_subgraph_without_name_suffix(self):
        """``SG-002.mmd`` (no underscore) → id=SG-002, name=""."""
        spec_dir = self.batch_dir / "SPEC-A"
        (spec_dir / "SG-002.mmd").write_text(
            "---\ntitle: bare\n---\nstateDiagram-v2\n[*] --> [*]: noop\n",
            encoding="utf-8",
        )

        recovered = self.orchestrator._recover_partial_from_disk(0, 0)
        sg_ids = {sg["id"]: sg for sg in recovered[0]["sub_graphs"]}
        self.assertIn("SG-002", sg_ids)
        self.assertEqual(sg_ids["SG-002"]["name"], "")
        self.assertEqual(sg_ids["SG-002"]["invariants"], [])

    def test_inv_lines_outside_note_blocks_ignored(self):
        """Only INV lines inside ``note right of`` ... ``end note`` count."""
        spec_dir = self.batch_dir / "SPEC-B"
        spec_dir.mkdir()
        (spec_dir / "SG-001_loose.mmd").write_text(
            "---\ntitle: loose\n---\nstateDiagram-v2\n"
            "[*] --> q1: noop\n"
            "INV-999: not a real invariant (outside note block)\n"
            "note right of q1\n"
            "    INV-001: real one\n"
            "end note\n",
            encoding="utf-8",
        )

        recovered = self.orchestrator._recover_partial_from_disk(0, 0)
        spec_b = next(s for s in recovered if s["title"] == "SPEC-B")
        self.assertEqual(
            spec_b["sub_graphs"][0]["invariants"],
            ["INV-001: real one"],
        )

    def test_url_lookup_falls_back_to_queue_when_context_missing(self):
        """When the CONTEXT file is absent, the queue's ``item_ids`` (URL list
        for Phase 01b) must still feed the candidate-dir lookup so we can
        recover ``source_url``. Reproduces the case where a crash before
        context-write left only the queue on disk."""
        # Remove the context file written in setUp; the queue alone must
        # carry enough information for url recovery to succeed.
        context_path = (
            self.tmp_root
            / f"01b_CONTEXT_W0B0_{self.timestamp}.json"
        )
        context_path.unlink()

        recovered = self.orchestrator._recover_partial_from_disk(0, 0)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["source_url"], self.source_url)

    def test_url_lookup_yields_empty_when_no_queue_or_context(self):
        """No queue, no context → recovery still returns the .mmd content but
        with ``source_url`` set to the empty string (Pydantic-permitted)."""
        for path in self.tmp_root.glob("01b_CONTEXT_*"):
            path.unlink()
        for path in self.tmp_root.glob("01b_ASYNC_QUEUE_*"):
            path.unlink()

        recovered = self.orchestrator._recover_partial_from_disk(0, 0)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["source_url"], "")
        # The on-disk artifact (.mmd) is still preserved.
        self.assertEqual(recovered[0]["title"], "SPEC-A")
        self.assertEqual(len(recovered[0]["sub_graphs"]), 1)


class TestPhase01bCandidateDirNames(unittest.TestCase):
    """Pure-logic tests for ``Phase01bOrchestrator._candidate_dir_names``."""

    def test_url_with_extension_yields_basename_and_stem(self):
        candidates = Phase01bOrchestrator._candidate_dir_names(
            "https://example.com/specs/SPEC-A.md",
        )
        self.assertIn("SPEC-A.md", candidates)
        self.assertIn("SPEC-A", candidates)

    def test_url_with_trailing_slash_drops_it(self):
        candidates = Phase01bOrchestrator._candidate_dir_names(
            "https://example.com/specs/EIP-7892/",
        )
        self.assertIn("EIP-7892", candidates)

    def test_url_without_path_segments_yields_no_usable_candidates(self):
        # A bare host has no usable basename — the recovery falls back to "".
        candidates = Phase01bOrchestrator._candidate_dir_names("https://example.com")
        for c in candidates:
            self.assertNotIn("://", c, f"candidate looks like a URL not a dirname: {c!r}")


if __name__ == "__main__":
    unittest.main()

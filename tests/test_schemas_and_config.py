"""
Comprehensive tests for orchestrator schemas and config.

Covers:
  - PhaseConfig construction and computed fields
  - All Pydantic data models (Phase01a through Phase04)
  - Validation helpers for each phase
  - Enum correctness
  - Edge cases and error detection
"""

import sys
import os
import pytest

# Ensure the scripts directory is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from orchestrator.config import PhaseConfig, PHASE_CONFIGS, get_phase_config, get_phase_chain
from orchestrator.schemas import (
    # Enums
    Severity,
    AuditClassification,
    ReviewVerdict,
    ReachabilityClassification,
    BugBountyScope,
    ChecklistMindset,
    # Phase 01a
    DiscoveredSpec,
    Phase01aState,
    # Phase 01b
    ProgramGraph,
    SubGraph,
    SpecSubGraphs,
    Phase01bPartial,
    # Phase 01c
    VerificationResult,
    Phase01cPartial,
    # Phase 01d
    TrustModelActor,
    TrustBoundary,
    TrustAssumption,
    StrideAnalysisItem,
    TrustModel,
    BugBountyScopeInfo,
    Phase01dPartial,
    # Phase 01e
    PropertyReachability,
    PropertyCovers,
    Property,
    Phase01ePartial,
    # Phase 02
    ChecklistItem,
    ChecklistReachability,
    Phase02Partial,
    # Phase 03
    Phase1AbstractInterpretation,
    Phase2SymbolicExecution,
    Phase2_5ReachabilityAnalysis,
    Phase3InvariantProving,
    Phase3_5ScopeFiltering,
    AuditTrail,
    AuditMapItem,
    Phase03Partial,
    # Phase 04
    OriginalFinding,
    ReviewedItem,
    Phase04Partial,
    # Shared
    QueuePayload,
    PartialMetadata,
    TargetInfo,
    # Validators
    validate_discovered_spec,
    validate_subgraph,
    validate_property,
    validate_checklist_item,
    validate_audit_map_item,
    validate_reviewed_item,
)


# =========================================================================
# PhaseConfig tests
# =========================================================================

class TestPhaseConfig:
    def test_all_phase_configs_are_valid(self):
        """Every entry in PHASE_CONFIGS must be a valid PhaseConfig."""
        for pid, cfg in PHASE_CONFIGS.items():
            assert isinstance(cfg, PhaseConfig)
            assert cfg.phase_id == pid

    def test_effective_result_id_field_explicit(self):
        cfg = PHASE_CONFIGS["01b"]
        assert cfg.effective_result_id_field == "source_url"

    def test_effective_result_id_field_fallback(self):
        cfg = PHASE_CONFIGS["03"]
        assert cfg.effective_result_id_field == cfg.item_id_field

    def test_get_phase_config_known(self):
        cfg = get_phase_config("03")
        assert cfg.name == "Audit Map Generation"

    def test_get_phase_config_unknown(self):
        with pytest.raises(ValueError, match="Unknown phase"):
            get_phase_config("99")

    def test_get_phase_chain(self):
        chain = get_phase_chain("03")
        assert "01a" in chain
        assert "02" in chain
        assert chain[-1] == "03"

    def test_phase03_config_values(self):
        cfg = PHASE_CONFIGS["03"]
        assert cfg.batch_strategy == "count"
        assert cfg.max_batch_size == 25
        assert cfg.result_key == "audit_items"
        assert cfg.output_prefix == "AUDITMAP"


# =========================================================================
# Enum tests
# =========================================================================

class TestEnums:
    def test_severity_values(self):
        assert Severity.CRITICAL == "Critical"
        assert Severity.LOW == "Low"

    def test_audit_classification_values(self):
        assert AuditClassification.VULNERABLE == "vulnerable"
        assert AuditClassification.SAFE == "safe"

    def test_review_verdict_values(self):
        assert ReviewVerdict.CONFIRMED == "Confirmed"
        assert ReviewVerdict.DISPUTED == "Disputed"

    def test_reachability_classification_values(self):
        assert ReachabilityClassification.EXTERNAL_REACHABLE == "external-reachable"
        assert ReachabilityClassification.INTERNAL_ONLY == "internal-only"

    def test_bug_bounty_scope_values(self):
        assert BugBountyScope.IN_SCOPE == "in-scope"
        assert BugBountyScope.OUT_OF_SCOPE == "out-of-scope"

    def test_checklist_mindset_values(self):
        assert ChecklistMindset.BOUNDARY_GUARD == "Boundary Guard"


# =========================================================================
# Phase 01a – Discovery
# =========================================================================

class TestPhase01a:
    def test_discovered_spec_valid(self):
        spec = DiscoveredSpec(url="https://example.com/spec")
        assert spec.url == "https://example.com/spec"
        assert spec.status == "pending"

    def test_phase01a_state_valid(self):
        state = Phase01aState(
            found_specs=[
                {"url": "https://a.com", "title": "Spec A"},
                {"url": "https://b.com"},
            ]
        )
        assert len(state.found_specs) == 2
        assert state.found_specs[0].title == "Spec A"

    def test_phase01a_state_empty(self):
        state = Phase01aState()
        assert state.found_specs == []

    def test_validate_discovered_spec_valid(self):
        item, errs = validate_discovered_spec({"url": "https://x.com", "title": "X"})
        assert item is not None
        assert errs == []

    def test_validate_discovered_spec_empty_url(self):
        item, errs = validate_discovered_spec({"url": ""})
        assert "url is empty" in errs


# =========================================================================
# Phase 01b – Subgraph Extraction
# =========================================================================

class TestPhase01b:
    def test_program_graph_valid(self):
        pg = ProgramGraph(
            Q=["q_init", "q1", "q_final"],
            q_init="q_init",
            q_final="q_final",
            Act=["x = 1", "x > 0"],
            E=[["q_init", "x = 1", "q1"], ["q1", "x > 0", "q_final"]],
        )
        assert len(pg.Q) == 3
        assert len(pg.E) == 2

    def test_subgraph_valid(self):
        sg = SubGraph(
            id="SG-001",
            name="factorial",
            mermaid_file="examples/SG-001_factorial.mmd",
            program_graph=ProgramGraph(
                Q=["q1", "q2"],
                q_init="q1",
                q_final="q2",
                Act=["a"],
                E=[["q1", "a", "q2"]],
            ),
            invariants=["INV-001: x >= 0"],
        )
        assert sg.id == "SG-001"
        assert len(sg.invariants) == 1

    def test_spec_subgraphs_valid(self):
        spec = SpecSubGraphs(
            source_url="https://example.com/eip-7594",
            title="EIP-7594",
            sub_graphs=[
                SubGraph(id="SG-001", name="test"),
            ],
        )
        assert len(spec.sub_graphs) == 1

    def test_phase01b_partial_valid(self):
        partial = Phase01bPartial(
            specs=[
                {
                    "source_url": "https://example.com",
                    "title": "Test",
                    "sub_graphs": [{"id": "SG-001", "name": "test"}],
                }
            ]
        )
        assert len(partial.specs) == 1
        assert partial.specs[0].sub_graphs[0].id == "SG-001"

    def test_validate_subgraph_valid(self):
        data = {
            "id": "SG-001",
            "name": "factorial",
            "program_graph": {
                "Q": ["q1", "q2"],
                "q_init": "q1",
                "q_final": "q2",
                "Act": ["a"],
                "E": [["q1", "a", "q2"]],
            },
        }
        item, errs = validate_subgraph(data)
        assert item is not None
        assert errs == []

    def test_validate_subgraph_empty_graph(self):
        data = {"id": "SG-001", "name": "test", "program_graph": {"Q": [], "E": []}}
        item, errs = validate_subgraph(data)
        assert "program_graph.Q is empty (no nodes)" in errs
        assert "program_graph.E is empty (no edges)" in errs

    def test_validate_subgraph_missing_name(self):
        data = {"id": "SG-001", "program_graph": {"Q": ["q1"], "E": [["q1", "a", "q1"]]}}
        item, errs = validate_subgraph(data)
        assert "name is empty" in errs


# =========================================================================
# Phase 01c – Verification
# =========================================================================

class TestPhase01c:
    def test_verification_result_valid(self):
        vr = VerificationResult(
            file_path="outputs/01b_PARTIAL_0.json",
            status="verified",
            issues=[],
        )
        assert vr.status == "verified"

    def test_phase01c_partial_valid(self):
        partial = Phase01cPartial(
            results=[
                {"file_path": "test.json", "status": "verified"},
                {"file_path": "test2.json", "status": "failed", "issues": ["bad edge"]},
            ]
        )
        assert len(partial.results) == 2
        assert partial.results[1].issues == ["bad edge"]


# =========================================================================
# Phase 01d – Trust Model
# =========================================================================

class TestPhase01d:
    def test_trust_model_actor_valid(self):
        actor = TrustModelActor(
            id="actor-user",
            name="User",
            description="External user",
            trust_level="untrusted",
        )
        assert actor.trust_level == "untrusted"

    def test_trust_boundary_valid(self):
        tb = TrustBoundary(
            id="tb-001",
            from_actor="actor-user",
            to_actor="actor-validator",
            entry_point_type="Transaction",
            bug_bounty_scope="in-scope",
            attacker_controlled=True,
        )
        assert tb.attacker_controlled is True

    def test_stride_analysis_item_valid(self):
        stride = StrideAnalysisItem(
            id="stride-001",
            trust_boundary_id="tb-001",
            threat_type="Tampering",
            severity="HIGH",
        )
        assert stride.threat_type == "Tampering"

    def test_trust_model_valid(self):
        tm = TrustModel(
            actors=[{"id": "a1", "name": "User"}],
            trust_boundaries=[{"id": "tb-001"}],
            assumptions=[{"id": "asm-001", "text": "Validators are honest"}],
            stride_analysis=[{"id": "s-001", "threat_type": "Spoofing"}],
        )
        assert len(tm.actors) == 1
        assert len(tm.stride_analysis) == 1

    def test_phase01d_partial_valid(self):
        partial = Phase01dPartial(
            source_files=["outputs/01b_PARTIAL_0.json"],
            trust_model={
                "actors": [{"id": "a1", "name": "User"}],
                "trust_boundaries": [],
                "assumptions": [],
                "stride_analysis": [],
            },
        )
        assert len(partial.trust_model.actors) == 1

    def test_bug_bounty_scope_info(self):
        info = BugBountyScopeInfo(
            program_name="Ethereum Bug Bounty",
            in_scope_components=["P2P", "Transaction"],
            out_of_scope_components=["JSON-RPC API"],
        )
        assert "P2P" in info.in_scope_components


# =========================================================================
# Phase 01e – Properties
# =========================================================================

class TestPhase01e:
    def test_property_valid(self):
        prop = Property(
            id="PROP-001",
            text="Total supply must not change",
            type="invariant",
            severity="CRITICAL",
            covers={"primary_element": "FN-001", "nodes": ["User"]},
            reachability={
                "classification": "external-reachable",
                "entry_points": ["Transaction"],
                "attacker_controlled": True,
                "bug_bounty_scope": "in-scope",
            },
            bug_bounty_eligible=True,
        )
        assert prop.reachability.attacker_controlled is True
        assert prop.covers.primary_element == "FN-001"

    def test_property_minimal(self):
        prop = Property(id="PROP-002")
        assert prop.type == ""
        assert prop.severity == ""

    def test_phase01e_partial_valid(self):
        partial = Phase01ePartial(
            properties=[
                {"id": "PROP-001", "type": "invariant", "severity": "HIGH"},
                {"id": "PROP-002", "type": "pre-condition", "severity": "LOW"},
            ]
        )
        assert len(partial.properties) == 2

    def test_validate_property_valid(self):
        data = {
            "id": "PROP-001",
            "type": "invariant",
            "severity": "CRITICAL",
            "covers": {"primary_element": "FN-001"},
        }
        item, errs = validate_property(data)
        assert item is not None
        assert errs == []

    def test_validate_property_missing_fields(self):
        data = {"id": "PROP-001"}
        item, errs = validate_property(data)
        assert "type is empty" in errs
        assert "severity is empty" in errs

    def test_validate_property_no_covers(self):
        data = {"id": "PROP-001", "type": "invariant", "severity": "HIGH", "covers": {}}
        item, errs = validate_property(data)
        assert any("covers" in e for e in errs)


# =========================================================================
# Phase 02 – Checklist
# =========================================================================

class TestChecklistItem:
    def test_valid_item(self):
        item = ChecklistItem(
            check_id="CHK-001",
            property_id="PROP-001",
            title="Test check",
            severity="High",
            test_procedure="Run the test",
        )
        assert item.check_id == "CHK-001"

    def test_minimal_item(self):
        item = ChecklistItem(check_id="CHK-002")
        assert item.property_id == ""
        assert item.is_boundary_check is False

    def test_extra_fields_ignored(self):
        item = ChecklistItem.model_validate(
            {"check_id": "CHK-003", "unknown_field": "value"}
        )
        assert item.check_id == "CHK-003"


class TestPhase02Partial:
    def test_checklist_key(self):
        partial = Phase02Partial(
            checklist=[{"check_id": "CHK-001"}]
        )
        assert len(partial.checklist) == 1

    def test_checklist_items_key_merged(self):
        partial = Phase02Partial(
            checklist_items=[{"check_id": "CHK-001"}, {"check_id": "CHK-002"}]
        )
        assert len(partial.checklist) == 2

    def test_empty_partial(self):
        partial = Phase02Partial()
        assert partial.checklist == []


# =========================================================================
# Phase 03 – Audit Map
# =========================================================================

class TestAuditMapItem:
    def test_valid_audit_item(self):
        item = AuditMapItem(
            check_id="CHK-001",
            property_id="PROP-001",
            final_classification="vulnerable",
            bug_bounty_eligible=True,
            summary="Found a vulnerability",
        )
        assert item.final_classification == "vulnerable"

    def test_audit_trail_defaults(self):
        item = AuditMapItem(check_id="CHK-002")
        assert item.audit_trail.phase1_abstract_interpretation.summary == ""
        assert item.audit_trail.phase2_symbolic_execution.counterexample_found is False

    def test_full_audit_trail(self):
        item = AuditMapItem(
            check_id="CHK-003",
            audit_trail={
                "phase1_abstract_interpretation": {
                    "summary": "Found anomaly",
                    "state_anomalies_found": ["overflow"],
                },
                "phase2_symbolic_execution": {
                    "summary": "Counterexample found",
                    "counterexample_found": True,
                    "counterexample": {"input": "0xFFFF"},
                },
                "phase2_5_reachability_analysis": {
                    "summary": "Reachable via P2P",
                    "classification": "external-reachable",
                    "attacker_controlled": True,
                },
                "phase3_invariant_proving": {
                    "summary": "Proof failed",
                    "proof_successful": False,
                },
                "phase3_5_scope_filtering": {
                    "bug_bounty_eligible": True,
                    "reason": "In-scope via P2P",
                },
            },
        )
        trail = item.audit_trail
        assert trail.phase1_abstract_interpretation.state_anomalies_found == ["overflow"]
        assert trail.phase2_symbolic_execution.counterexample_found is True
        assert trail.phase2_5_reachability_analysis.attacker_controlled is True
        assert trail.phase3_5_scope_filtering.bug_bounty_eligible is True


class TestPhase03Partial:
    def test_valid_partial(self):
        partial = Phase03Partial(
            audit_items=[
                {"check_id": "CHK-001", "final_classification": "safe"},
            ]
        )
        assert len(partial.audit_items) == 1


# =========================================================================
# Phase 04 – Audit Review
# =========================================================================

class TestPhase04Partial:
    def test_valid_review(self):
        partial = Phase04Partial(
            reviewed_items=[
                {
                    "check_id": "CHK-001",
                    "review_verdict": "Confirmed",
                    "adjusted_severity": "High",
                }
            ]
        )
        assert len(partial.reviewed_items) == 1
        assert partial.reviewed_items[0].review_verdict == "Confirmed"

    def test_reviewed_item_defaults(self):
        item = ReviewedItem(check_id="CHK-002")
        assert item.review_verdict == ""
        assert item.reviewer_notes == ""


# =========================================================================
# Validation helpers
# =========================================================================

class TestValidationHelpers:
    # -- checklist items --
    def test_validate_checklist_item_valid(self):
        data = {
            "check_id": "CHK-001",
            "property_id": "PROP-001",
            "test_procedure": "Run test",
        }
        item, errs = validate_checklist_item(data)
        assert item is not None
        assert errs == []

    def test_validate_checklist_item_missing_fields(self):
        data = {"check_id": "CHK-001"}
        item, errs = validate_checklist_item(data)
        assert "property_id is empty" in errs
        assert "test_procedure is empty" in errs

    def test_validate_checklist_item_empty_check_id(self):
        data = {"check_id": ""}
        item, errs = validate_checklist_item(data)
        assert "check_id is empty" in errs

    # -- audit map items --
    def test_validate_audit_map_item_valid(self):
        data = {
            "check_id": "CHK-001",
            "final_classification": "vulnerable",
        }
        item, errs = validate_audit_map_item(data)
        assert item is not None
        assert errs == []

    def test_validate_audit_map_item_missing_classification(self):
        data = {"check_id": "CHK-001"}
        item, errs = validate_audit_map_item(data)
        assert "final_classification is empty" in errs

    # -- reviewed items --
    def test_validate_reviewed_item_valid(self):
        data = {
            "check_id": "CHK-001",
            "review_verdict": "Confirmed",
        }
        item, errs = validate_reviewed_item(data)
        assert item is not None
        assert errs == []

    def test_validate_reviewed_item_missing_verdict(self):
        data = {"check_id": "CHK-001"}
        item, errs = validate_reviewed_item(data)
        assert "review_verdict is empty" in errs

    def test_validate_reviewed_item_empty_check_id(self):
        data = {"check_id": "", "review_verdict": "Confirmed"}
        item, errs = validate_reviewed_item(data)
        assert "check_id is empty" in errs


# =========================================================================
# Shared models
# =========================================================================

class TestQueuePayload:
    def test_valid_payload(self):
        payload = QueuePayload(
            worker_id=0,
            phase="03",
            items=[{"check_id": "CHK-001"}],
            total_items=1,
        )
        assert payload.worker_id == 0


class TestPartialMetadata:
    def test_valid_metadata(self):
        meta = PartialMetadata(
            phase="03",
            worker_id=0,
            batch_index=1,
            item_count=5,
            timestamp=1700000000,
            processed_ids=["CHK-001", "CHK-002"],
        )
        assert meta.item_count == 5
        assert len(meta.processed_ids) == 2


class TestTargetInfo:
    def test_valid_target(self):
        info = TargetInfo(
            target_repo="ethereum/go-ethereum",
            target_ref_type="branch",
            target_ref_label="master",
        )
        assert info.target_repo == "ethereum/go-ethereum"


# =========================================================================
# Cross-phase data flow tests
# =========================================================================

class TestCrossPhaseDataFlow:
    """Test that data structures are compatible across phase boundaries."""

    def test_01e_property_to_02_checklist(self):
        """Property from 01e should be usable as input for 02 checklist."""
        prop = Property(
            id="PROP-001",
            type="invariant",
            severity="HIGH",
            covers={"primary_element": "FN-001"},
            reachability={
                "classification": "external-reachable",
                "bug_bounty_scope": "in-scope",
            },
        )
        # Simulate what Phase02Orchestrator.load_items does
        item = {
            "property_id": prop.id,
            "property": prop.model_dump(),
            "source_file": "test.json",
        }
        assert item["property"]["reachability"]["bug_bounty_scope"] == "in-scope"

    def test_02_checklist_to_03_audit(self):
        """Checklist item from 02 should be parseable as Phase03 input."""
        cl = ChecklistItem(
            check_id="CHK-001",
            property_id="PROP-001",
            title="Test check",
            severity="High",
            test_procedure="Run the test",
        )
        # Simulate Phase03Orchestrator.load_items
        entry = cl.model_dump()
        parsed, errs = validate_checklist_item(entry)
        assert parsed is not None
        assert errs == []

    def test_03_audit_to_04_review(self):
        """Audit item from 03 should be parseable as Phase04 input."""
        audit = AuditMapItem(
            check_id="CHK-001",
            property_id="PROP-001",
            final_classification="vulnerable",
            summary="Found issue",
        )
        # Simulate Phase04Orchestrator.load_items
        entry = audit.model_dump()
        parsed, errs = validate_audit_map_item(entry)
        assert parsed is not None
        assert errs == []

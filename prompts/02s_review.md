
---
Description: [ORCHESTRATOR] Perform a multi-phase review of all generated artifacts.
Usage: `/02s_review`
Language: English only.
Execution hint: This is the final step of the preparation phase. It validates all prior outputs.
---

<task>
  <goal>Perform a multi-phase review of all generated artifacts (SPEC, TRUSTMODEL, PROP), starting with a critical self-verification of data consistency.</goal>
  <input type="file" id="spec">outputs/01_SPEC.json</input>
  <input type="file" id="prop">outputs/01e_PROP.json</input>
  <output type="file" id="results">outputs/02s_REVIEW_REPORT.json</output>

  <critical_requirements>
    1. You MUST perform the pre-computation and self-verification checks in Phase 0 before any other analysis.
    2. If any Phase 0 check fails, the `overall_verdict` MUST be `FAIL`, and you MUST NOT proceed to other phases.
    3. The final review report MUST be written to <ref id="results"/>.
  </critical_requirements>

  <instructions>
    ### Phase 0: Pre-computation & Self-Verification
    1. **Verify Property Coverage**: Read the `coverage_summary` from <ref id="prop"/>. If `coverage_ok` is `false`, fail the review immediately.
    2. **Verify Spec Metadata**: Count the actual nodes and edges in the `program_graph` of <ref id="spec"/> and compare them to the metadata counts. If they do not match, fail the review.
    3. **Verify Property Metadata**: Count the actual properties in <ref id="prop"/> and compare to the `total_properties` in the metadata. If they do not match, fail the review.

    ### Phase 1-5: Detailed Review (if Phase 0 passes)
    - **Phase 1: Specification Completeness**: Check for orphan nodes and ensure all major specs are represented.
    - **Phase 2: Trust Model Consistency**: Use a Tree of Thoughts approach to verify entity coverage, boundary edge coverage, and trust level appropriateness.
    - **Phase 3: Adversarial Scenario Testing**: Hypothesize and trace 3-5 attack scenarios against boundary edges.
    - **Phase 4: Property Coverage Review**: Use multiple approaches (Node→Prop, Prop→Node, Boundary→Prop) to cross-validate property coverage.
    - **Phase 5: Ambiguity/Assumption Handling**: Ensure all ambiguities and assumptions are addressed by properties.

    ### Final Step: Write Output
    - Assemble the final report with the `overall_verdict` and detailed phase results, and write it to <ref id="results"/>.
  </instructions>

  <data_sources>
    - **Specification File**: <ref id="spec"/>
    - **Property File**: <ref id="prop"/>
  </data_sources>
</task>

<output>
  <format>JSON object</format>
  <stdout>Max 15 lines: summary of each review phase and the final verdict.</stdout>
  <final_line>Output File: {{OUTPUT_FILE}}</final_line>
</output>

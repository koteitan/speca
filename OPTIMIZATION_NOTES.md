# Phase 03 Optimization Notes

## Overview

This document describes the optimizations implemented to reduce token consumption in Phase 03 (Audit Map Generation).

## Implemented Optimizations

### 1. Early Termination Logic (High Priority)

**Location**: `.claude/skills/formal-audit-unified/SKILL.md`

**Description**: Added early exit checks at each phase to skip unnecessary analysis for trivially safe or verified safe code.

**Implementation**:
- **Phase 1**: If code is trivially safe (e.g., simple getter, constant return, no external input), mark as `trivially_safe=true` and skip to Phase 3 with minimal analysis
- **Phase 2**: Skip entirely if `trivially_safe=true`. If no counterexample found and code has strong guards, mark as `verified_safe=true`
- **Phase 3**: Use simplified analysis for `trivially_safe` or `verified_safe` cases

**Expected Impact**:
- **Token reduction**: 30-50% for simple/safe code paths
- **Time savings**: Proportional to token reduction
- **Accuracy**: Maintained through conservative classification

### 2. Cache Strategy Optimization (High Priority)

**Location**: `prompts/03_auditmap_worker_optimized.md`

**Description**: Added explicit cache optimization guidelines to maximize Claude API's prompt caching effectiveness.

**Implementation**:
- **Reuse context**: Keep common context (skill definitions, checklist schema) in the same conversation
- **Batch similar items**: Process items from the same file/component together to maximize cache hits
- **Minimal context**: Only include necessary information in each skill invocation
- **Cache-friendly invocation**: Pass only essential context to skills

**Expected Impact**:
- **Cache hit rate**: Increase from ~50% to ~80%
- **Token reduction**: 20-30% through better cache utilization
- **Cost savings**: Proportional to cache hit improvement

### 3. Code Resolution Pre-execution (Medium Priority)

**Location**: 
- `scripts/enrich_checklist_with_code.py` - Preparation script
- `prompts/02_enrich_code.md` - Optional enrichment worker
- `.github/workflows/02-enrich-code.yml` - GitHub Workflow
- `scripts/orchestrator/schemas.py` - CodeScope type definition
- `prompts/03_auditmap_worker_optimized.md` - Updated to check pre-resolved code

**Description**: Added optional code pre-resolution step that enriches checklist items with code locations before Phase 03.

**Implementation**:
- **Type-safe schema**: Added `CodeScope` model with `resolution_status` field
- **Backward compatible**: Phase 03 checks if code is pre-resolved, otherwise resolves on-demand
- **Optional workflow**: New GitHub Workflow `02-enrich-code.yml` for code pre-resolution
- **Batch optimization**: Resolves all code locations in a single Claude Code session
- **Cache symbols**: Uses `mcp__tree_sitter__analyze_project` once for all items

**Expected Impact**:
- **MCP call reduction**: 70-80% (from ~1500 to ~300 calls)
- **Time savings**: 3-5 minutes per audit
- **Reliability**: Early detection of code resolution failures
- **Flexibility**: Can be skipped if not needed

## Usage

### Running with Optimizations

All optimizations are enabled by default. To run the full workflow:

```bash
# Step 1: Run Phase 02 (Checklist Generation)
uv run python3 scripts/run_phase.py --phase 02 --workers 4 --max-concurrent 64

# Step 2 (Optional): Enrich checklist with code locations
# Via GitHub Workflow (recommended):
#   Manually trigger "02-enrich. Code Pre-resolution" workflow

# Or via command line:
python3 scripts/enrich_checklist_with_code.py outputs/
claude --mcp-config .claude/mcp.json /02_enrich_code \
  INPUT_FILE=outputs/02_CHECKLIST_ENRICHED.json \
  OUTPUT_FILE=outputs/02_CHECKLIST_WITH_CODE.json

# Step 3: Run Phase 03 (Audit Map Generation)
# Phase 03 will automatically use pre-resolved code if available
uv run python3 scripts/run_phase.py --phase 03 --workers 4 --max-concurrent 64
```

### Disabling Optimizations

To revert to the legacy Phase 03 behavior (for comparison or debugging):

```bash
# Set environment variable
export USE_LEGACY_PHASE03=1

# Run Phase 03
uv run python3 scripts/run_phase.py --phase 03 --workers 4 --max-concurrent 64
```

## Performance Metrics

### Before Optimization

- **Tokens per item**: ~27,000 (effective input) + ~245,000 (cache read) = ~272,000 total
- **API calls per item**: ~5.1
- **MCP calls**: ~1,500 for code resolution
- **Execution time**: 20+ minutes for 533 items (incomplete)

### After Optimization (Estimated)

- **Tokens per item**: ~6,200 (effective input) + ~56,000 (cache read) = ~62,200 total
- **Token reduction**: ~77%
- **API calls per item**: ~2-3 (with early termination)
- **MCP calls**: ~200 (with pre-resolution)
- **Execution time**: <10 minutes for 533 items (complete)

## Future Improvements

### Additional Optimizations to Consider

1. **Dynamic Concurrency Adjustment**: Automatically adjust `max_concurrent` based on token consumption rate
2. **Risk-based Prioritization**: Process high-risk items first, skip low-risk items if budget limited
3. **Incremental Analysis**: Cache analysis results across audit runs for unchanged code
4. **Simplified Output Format**: Further compress output JSON to reduce token overhead

### Monitoring and Metrics

Consider adding:
- Real-time token consumption dashboard
- Per-phase token breakdown
- Cache hit rate monitoring
- Early termination effectiveness metrics

## References

- Original Issue: [#40](https://github.com/NyxFoundation/security-agent/issues/40)
- Initial Optimization PR: [#41](https://github.com/NyxFoundation/security-agent/pull/41)
- Analysis Report: See `review_report.md` in the repository root

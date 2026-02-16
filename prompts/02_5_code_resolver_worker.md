---
Description: [WORKER] Pre-resolve code locations for checklist items to optimize Phase 03.
Usage: `/02_5_code_resolver QUEUE_FILE=... OUTPUT_FILE=...`
Example: `/02_5_code_resolver QUEUE_FILE=outputs/02_5_CODE_RESOLUTION_QUEUE.json OUTPUT_FILE=outputs/02_5_CODE_RESOLVED.json`
Language: English only.
Execution hint: This worker runs between Phase 02 and Phase 03 to batch-resolve code locations.
---

<task>
  <goal>Resolve code locations for all checklist items in advance to reduce MCP calls during Phase 03.</goal>
  <input type="file" id="queue">{{QUEUE_FILE}}</input>
  <output type="file" id="results">{{OUTPUT_FILE}}</output>

  <rationale>
    By resolving code locations in a single batch operation before Phase 03:
    - **Reduce MCP calls**: Each item's code location is resolved once, not repeatedly
    - **Enable caching**: Tree-sitter analysis results can be cached across items
    - **Improve parallelism**: Phase 03 workers can start immediately without waiting for code resolution
    - **Better error handling**: Code resolution failures are identified early
  </rationale>

  <instructions>
    1. **Load Queue**: Read <ref id="queue"/> containing checklist items needing code resolution.

    2. **Batch Resolution**: For each item:
       a. Extract `graph_element_under_test` (e.g., "beacon_chain.go:ProcessBlock")
       b. Use `mcp__tree_sitter__get_symbols` to find the symbol in the codebase
       c. If found, populate `code_scope` with:
          - `file`: absolute or relative file path
          - `function`: function/method name
          - `line_range`: start and end line numbers (e.g., "100-150")
       d. If not found or ambiguous:
          - Mark `code_scope.file` as "NOT_FOUND" or "AMBIGUOUS"
          - Add `code_scope.resolution_error` with details

    3. **Optimize MCP Usage**:
       - **Cache symbols**: Use `mcp__tree_sitter__analyze_project` once to get all symbols
       - **Batch queries**: Group items by file/component to minimize tree-sitter invocations
       - **Skip duplicates**: If multiple items reference the same function, resolve once

    4. **Write Output**: Save all items with resolved `code_scope` to <ref id="results"/>.

    5. **Report**: Print summary:
       - Total items processed
       - Successfully resolved
       - Failed/ambiguous resolutions
       - Time saved estimate (based on MCP calls avoided)
  </instructions>

  <data_sources>
    - **Tree-sitter MCP**: Use `mcp__tree_sitter__analyze_project` and `mcp__tree_sitter__get_symbols`
    - **Filesystem MCP**: Use `mcp__filesystem__list_directory` to validate file paths
  </data_sources>

  <output_schema>
    Each item should have:
    ```json
    {
      "check_id": "...",
      "graph_element_under_test": "...",
      "code_scope": {
        "file": "path/to/file.go",
        "function": "FunctionName",
        "line_range": "100-150",
        "resolution_status": "resolved|not_found|ambiguous|error",
        "resolution_error": "optional error message"
      }
    }
    ```
  </output_schema>
</task>

<optimization_notes>
  This phase is designed to be run once per audit, not per worker.
  It should complete in 2-5 minutes for typical codebases (1000-5000 items).
  
  Expected token savings in Phase 03:
  - Before: ~2-3 MCP calls per item × 500 items = 1000-1500 MCP calls
  - After: ~1 MCP call per unique symbol × 200 symbols = 200 MCP calls
  - **Savings: 80-85% reduction in code resolution overhead**
</optimization_notes>

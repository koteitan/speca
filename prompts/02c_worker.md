
---
Description: [WORKER] Pre-resolve code locations for checklist items before Phase 03
Usage: `/02c_worker WORKER_ID=... QUEUE_FILE=... [TIMESTAMP=...] [ITERATION=...] [BATCH_SIZE=...] [OUTPUT_FILE=...]`
Example: `/02c_worker WORKER_ID=0 QUEUE_FILE=outputs/02c_QUEUE_0.json TIMESTAMP=1700000000 ITERATION=1 BATCH_SIZE=100 OUTPUT_FILE=outputs/02c_CODE_RESOLVED_PARTIAL_W0_1700000000_1.json`
Language: English only.
Execution hint: This worker uses built-in file and shell tools for reliable code resolution. MCP tools are NOT required.
---

<task>
  <goal>For each checklist item in the batch, resolve code locations using grep/ripgrep and populate code_scope and code_excerpt fields.</goal>
  <input type="file" id="queue">{{QUEUE_FILE}}</input>
  <output type="file" id="results">{{OUTPUT_FILE}}</output>

  <critical_requirements>
    1. Process ALL items in the batch
    2. Use shell tools (grep, rg, find) for code resolution - NO MCP tools
    3. Use file tool for reading code excerpts
    4. Write JSON file to <ref id="results"/> after processing ALL items
    5. File MUST be written even if some items fail resolution
    6. Handle errors gracefully - continue processing even if individual items fail
  </critical_requirements>

  <instructions>
    1. **Initialize**: 
       - Read <ref id="queue"/> using file tool
       - Parse JSON and select first BATCH_SIZE items
       - Create empty `results = []` array
       - Determine target workspace path (usually `target_workspace/` or current directory)

    2. **Batch Symbol Collection**:
       - Extract ALL `graph_element_under_test` values from all items
       - Create a deduplicated list of symbols to search
       - Build a single grep/ripgrep pattern for all symbols: `(Symbol1|Symbol2|Symbol3)`

    3. **Batch Code Search** (ONE command for all symbols):
       ```bash
       rg --json --line-number --no-heading '(func|type|const|var)\s+(Symbol1|Symbol2|Symbol3)' target_workspace/
       ```
       OR if ripgrep not available:
       ```bash
       grep -rn -E '(func|type|const|var)\s+(Symbol1|Symbol2|Symbol3)' target_workspace/
       ```
       - Parse results and create a symbol→location mapping
       - This reduces search operations from O(n) to O(1)

    4. **Process Each Item**:
       For each checklist item in the batch:
       
       a. **Extract Element Info**: 
          - Get `graph_element_under_test` from item
          - If missing/empty: set `resolution_status: "no_element"`, append to results, continue

       b. **Resolve Primary Location** (from batch search results):
          - Look up symbol in the mapping created in step 3
          - If found:
            * Extract file path, line number
            * Read surrounding lines (±10 lines) to get function/type definition
            * Determine line range by finding function start/end
            * Create location: {file, symbol, line_range: {start, end}, role: "primary"}
          - If not found:
            * Try fuzzy search with partial symbol name
            * If still not found: set `resolution_status: "not_found"`, continue

       c. **Extract Code Excerpt**:
          - Use file tool to read the file at the identified location
          - Extract lines from line_range.start to line_range.end
          - Format as:
            ```
            // PRIMARY: path/to/file.go:FunctionName (lines 10-50)
            [code here]
            ```
          - Limit to 100 lines max to avoid token bloat

       d. **Find Related Locations** (OPTIONAL, time permitting):
          - Search for callers using grep for symbol name in function calls
          - Limit to top 3 most relevant
          - Add as additional locations with role: "caller"

       e. **Populate Result**:
          ```json
          {
            "check_id": "...",
            "code_scope": {
              "locations": [
                {
                  "file": "beacon-chain/sync/validate.go",
                  "symbol": "validateBlockHeader",
                  "line_range": {"start": 45, "end": 78},
                  "role": "primary"
                }
              ],
              "resolution_status": "resolved|not_found|no_element|error",
              "resolution_error": "error message if status=error"
            },
            "code_excerpt": "// PRIMARY: ...\n[code]"
          }
          ```

       f. **Error Handling**:
          - Wrap each item processing in try-catch logic
          - If error occurs: set `resolution_status: "error"`, add error message, continue
          - DO NOT let one item's error stop the entire batch

    5. **Write Output**:
       - After ALL items processed, write `results` array to <ref id="results"/>
       - Use file tool's write action
       - Ensure valid JSON format

    6. **Confirm**: 
       Print summary:
       ```
       Processed: 100 items
       Resolved: 75
       Not found: 20
       Errors: 5
       Output File: {{OUTPUT_FILE}}
       ```
  </instructions>

  <search_strategies>
    **For Go code** (Prysm, Geth, etc.):
    - Functions: `grep -rn 'func.*FunctionName' target_workspace/`
    - Types: `grep -rn 'type.*TypeName' target_workspace/`
    - Methods: `grep -rn 'func.*(.*TypeName).*MethodName' target_workspace/`
    
    **For Solidity code**:
    - Functions: `grep -rn 'function.*functionName' target_workspace/`
    - Contracts: `grep -rn 'contract.*ContractName' target_workspace/`
    
    **For Rust code**:
    - Functions: `grep -rn 'fn.*function_name' target_workspace/`
    - Structs: `grep -rn 'struct.*StructName' target_workspace/`
    
    **Use ripgrep (rg) if available** - it's much faster:
    ```bash
    rg --json -n 'pattern' target_workspace/
    ```
  </search_strategies>

  <performance_notes>
    **Optimization Goals**:
    - Target: 1-5 shell commands total for entire batch (not per item)
    - Method: Batch all symbol searches into ONE grep/rg command
    - Avoid: Individual searches per item
    
    **Resource Limits**:
    - Max 100 lines per code excerpt
    - Max 3 related locations per item
    - Total batch processing time: <2 minutes for 100 items
    
    **Reliability**:
    - Use built-in tools only (no MCP dependencies)
    - Graceful degradation: partial results better than no results
    - Clear error messages for debugging
  </performance_notes>

  <example_workflow>
    1. Read queue file → 100 items
    2. Extract symbols → ["validateBlock", "processAttestation", "verifySignature"]
    3. Run ONE grep: `rg -n '(validateBlock|processAttestation|verifySignature)' target_workspace/`
    4. Parse results → create symbol map
    5. For each item:
       - Lookup symbol in map
       - Read code excerpt
       - Build result object
    6. Write all results to output file
    7. Print summary
  </example_workflow>
</task>

<output>
  <format>JSON object with "checklist_with_code" array</format>
  <schema>
    {
      "checklist_with_code": [
        {
          "check_id": "string",
          "property_id": "string",
          "title": "string",
          ...all original fields...,
          "code_scope": {
            "locations": [
              {
                "file": "string (relative path from workspace root)",
                "symbol": "string (function/type name)",
                "line_range": {"start": int, "end": int},
                "role": "primary|caller|callee|related"
              }
            ],
            "resolution_status": "resolved|not_found|no_element|error",
            "resolution_error": "string (optional, only if status=error)"
          },
          "code_excerpt": "string (optional, formatted code with markers)"
        }
      ]
    }
  </schema>
  <stdout>Max 10 lines: batch size, resolution stats, status.</stdout>
  <final_line>Output File: {{OUTPUT_FILE}}</final_line>
</output>

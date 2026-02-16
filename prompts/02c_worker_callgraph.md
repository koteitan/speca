# Phase 02c: Code Pre-resolution with Call Graph Analysis

You are an expert code analyst tasked with mapping security audit checklist items to their implementation in a codebase using **call graph analysis**.

## Objective

For each batch of checklist items, use Tree-sitter MCP tools to:
1. Identify entry points based on the `reachability.entry_points` field
2. Build call graphs from those entry points
3. Map checklist items to specific code locations using keyword matching and call graph traversal

## Methodology: Entry-Point-Driven Call Graph Analysis

### Phase 1: Entry Point Identification

For each unique `entry_points` category in the batch, identify relevant functions:

**Category Patterns:**

- **P2P**: Functions handling P2P network messages
  - Patterns: `Handle.*Message`, `Receive.*Block`, `Process.*Block`, `Validate.*Block`
  - File paths: `**/p2p/**`, `**/sync/**`, `**/network/**`

- **Transaction**: Functions processing transactions
  - Patterns: `Process.*Transaction`, `Validate.*Transaction`, `Apply.*Transaction`, `Recover.*Sender`
  - File paths: `**/txpool/**`, `**/core/types/transaction*`, `**/core/state_transition*`

- **EngineAPI** / **Engine API**: Engine API handlers
  - Patterns: `Engine.*`, `ForkchoiceUpdated.*`, `NewPayload.*`, `GetPayload.*`
  - File paths: `**/eth/catalyst/**`, `**/beacon/engine/**`, `**/miner/payload*`

- **Consensus**: Consensus layer functions
  - Patterns: `VerifyHeader.*`, `Prepare.*`, `Finalize.*`, `Seal.*`
  - File paths: `**/consensus/**`, `**/core/headerchain*`

- **Internal** / **Internal API** / **Internal state transition**: Internal state processing
  - Patterns: `process.*`, `apply.*`, `execute.*`, `transition.*`
  - File paths: `**/core/**`, `**/internal/**`

**Tool Usage:**
```bash
# Get all symbols from the project
manus-mcp-cli tool call get_symbols --server tree_sitter --input '{
  "project": "target-project",
  "file_path": "**/*.go"
}'
```

Filter symbols by category patterns to identify entry points.

### Phase 2: Call Graph Construction

For each identified entry point, build a call graph using Tree-sitter queries:

**Go Language Call Expression Query:**
```scheme
(call_expression
  function: [
    (identifier) @call
    (selector_expression
      field: (field_identifier) @call)
  ])
```

**Tool Usage:**
```bash
# Run query to extract function calls
manus-mcp-cli tool call run_query --server tree_sitter --input '{
  "project": "target-project",
  "query": "(call_expression function: [(identifier) @call (selector_expression field: (field_identifier) @call)])",
  "file_path": "path/to/entry_point.go",
  "language": "go"
}'
```

**Algorithm:**
1. Start from entry point function
2. Extract all function calls within that function
3. Recursively explore called functions (max depth: 5 levels)
4. Build a tree of function calls

**Output Format:**
```json
{
  "entry_point": "HandleBlockMessage",
  "file": "beacon-chain/sync/rpc_block_handler.go",
  "calls": [
    {
      "from": "HandleBlockMessage",
      "to": "ValidateBlock",
      "file": "beacon-chain/sync/validator.go",
      "line": 45,
      "depth": 1
    },
    {
      "from": "ValidateBlock",
      "to": "ValidateRLPSize",
      "file": "core/types/block.go",
      "line": 120,
      "depth": 2
    }
  ]
}
```

### Phase 3: Keyword Extraction and Matching

For each checklist item:

1. **Extract keywords** from `test_procedure`:
   - ALL_CAPS words (e.g., `RLP`, `MAX_RLP_BLOCK_SIZE`)
   - snake_case identifiers (e.g., `recover_sender`, `state_transition`)
   - camelCase identifiers (e.g., `validateBlock`, `processTransaction`)

2. **Search call graph** for functions matching keywords:
   - Exact match: highest relevance
   - Partial match: medium relevance
   - Related functions in same call chain: low relevance

3. **Rank matches** by relevance score:
   ```
   relevance = (keyword_matches / total_keywords) * depth_penalty
   depth_penalty = 1.0 / (1 + depth * 0.2)
   ```

4. **Extract code locations** for top 5 matches:
   ```bash
   # Get function definition range
   manus-mcp-cli tool call get_symbols --server tree_sitter --input '{
     "project": "target-project",
     "file_path": "path/to/file.go"
   }'
   ```

### Phase 4: Output Generation

For each checklist item, produce:

```json
{
  "check_id": "...",
  "code_scope": {
    "locations": [
      {
        "file": "core/types/block.go",
        "symbol": "ValidateRLPSize",
        "line_range": [120, 145],
        "role": "primary"
      },
      {
        "file": "beacon-chain/sync/validator.go",
        "symbol": "ValidateBlock",
        "line_range": [45, 78],
        "role": "caller"
      }
    ],
    "resolution_status": "resolved"
  }
}
```

## Batch Processing Strategy

To maximize efficiency:

1. **Group by entry_points**: Process all items with the same entry points together
2. **Cache call graphs**: Build each entry point's call graph once, reuse for all items
3. **Parallel keyword matching**: Match all items against the same call graph in one pass

**Example Workflow:**
```
Batch: 15 checklist items

Step 1: Identify unique entry_points
  - P2P: 10 items
  - Transaction: 3 items
  - EngineAPI: 2 items

Step 2: Build call graphs (once per category)
  - P2P entry points → 5 call graphs
  - Transaction entry points → 2 call graphs
  - EngineAPI entry points → 1 call graph

Step 3: Match all 15 items against cached call graphs
  - Extract keywords for all items
  - Search call graphs in parallel
  - Rank and output top matches

Total MCP calls: ~50 (vs. 1,500 without caching)
```

## Error Handling

- **Entry point not found**: Mark as `resolution_status: "entry_point_not_found"`
- **No keyword matches**: Mark as `resolution_status: "not_found"`
- **MCP tool error**: Retry once, then mark as `resolution_status: "error"`

## Output

Return a JSON array with one object per checklist item:

```json
[
  {
    "check_id": "...",
    "code_scope": { ... }
  },
  ...
]
```

## Tools Available

- `manus-mcp-cli tool call register_project_tool --server tree_sitter`
- `manus-mcp-cli tool call get_symbols --server tree_sitter`
- `manus-mcp-cli tool call run_query --server tree_sitter`
- `manus-mcp-cli tool call list_files --server tree_sitter`

## Important Notes

1. **Use MCP tools, not grep**: Tree-sitter provides AST-level accuracy
2. **Cache aggressively**: Build call graphs once per entry point
3. **Batch keyword matching**: Process multiple items against same call graph
4. **Limit depth**: Max call graph depth = 5 to avoid explosion
5. **Top 5 only**: Return at most 5 code locations per item

Begin processing the batch now.

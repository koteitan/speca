
---
Description: [WORKER] Invoke the subgraph-extractor skill for a batch of items, outputting program graphs as Mermaid diagrams.
Usage: `/01b_extract_worker WORKER_ID=... QUEUE_FILE=... [TIMESTAMP=...] [ITERATION=...] [BATCH_SIZE=...] [OUTPUT_DIR=...]`
Example: `/01b_extract_worker WORKER_ID=0 QUEUE_FILE=outputs/01b_QUEUE_0.json TIMESTAMP=1700000000 ITERATION=1 BATCH_SIZE=5 OUTPUT_DIR=outputs/graphs/W0B1_1700000000`
Language: English only.
Execution hint: This worker prompt is invoked by the phase-01 async orchestrator.
---

<task>
  <goal>For each item in the batch, invoke the /subgraph-extractor skill **once per URL** to extract program graphs as enriched Mermaid diagrams.</goal>
  <input type="file" id="queue">{{QUEUE_FILE}}</input>
  <input type="file" id="context">{{CONTEXT_FILE}}</input>
  <output type="directory" id="graphs">{{OUTPUT_DIR}}</output>

  <program_graph_definition>
    A program graph **PG = (Q, q▷, q◀, Act, E)** consists of:
    - **Q**: finite set of nodes (program points)
    - **q▷, q◀**: initial and final nodes
    - **Act**: set of actions (assignments, tests/guards)
    - **E ⊆ Q × Act × Q**: finite set of edges

    Reference: Nielson & Nielson, "Formal Methods: An Appetizer", Springer 2019
  </program_graph_definition>

  <critical_requirements>
    **YOU MUST COMPLETE ALL OF THE FOLLOWING:**
    1. Process ALL items in the batch (up to BATCH_SIZE).
    2. For each subgraph, output an enriched `.mmd` Mermaid file (with YAML frontmatter and invariant notes) to <ref id="graphs"/>.
    3. The output files MUST be written even if some items fail.
    4. Emit a single fenced ```json ... ``` block on outer stdout that aggregates the per-spec results returned by `/subgraph-extractor` into a `{"specs": [...]}` envelope. The orchestrator's result parser scans outer stdout for this block; if it is missing, all `.mmd` files written to disk are orphaned and the next phase has no inputs.

    **FAILURE TO WRITE OUTPUT FILES OR TO EMIT THE JSON ENVELOPE IS A CRITICAL ERROR.**
  </critical_requirements>

  <instructions>
    1. **Initialize**: Read <ref id="queue"/> to get `item_ids` (list of IDs to process) and `context_file` path. Read <ref id="context"/> to get item data (keyed by ID). For each ID in `item_ids`, look up the item data in context. Create output directory structure.

    2. **Process Each Item** (one SKILL call per URL):
       For each item in the batch:
       a. **Invoke Skill**: Call `/subgraph-extractor` passing that item's `url` and `output_dir` = <ref id="graphs"/>.
          The skill reads one specification, extracts multiple program graphs, writes `.mmd` files, and returns a JSON result.
       b. **Collect Result**: Append the skill's returned JSON object to the results array.
       c. **Handle Errors**: If the skill fails for an item, log the error and continue to the next item.

    3. **Confirm Completion**:
       a. Print a fenced ```json ... ``` block whose body is `{"specs": [<one entry per spec>]}`. Each entry MUST be the per-spec object returned by `/subgraph-extractor` (`source_url`, `title`, `sub_graphs[]`). Include every spec the skill processed successfully — drop only items whose skill call failed.
       b. After the JSON block, print the short status summary.
       c. End with the exact line: `Output Directory: {{OUTPUT_DIR}}`
  </instructions>

  <output_structure>
    ```
    {{OUTPUT_DIR}}/
    ├── EIP-7594/
    │   ├── SG-001_erasure_coding.mmd      # Enriched: frontmatter + invariant notes
    │   ├── SG-002_kzg_verification.mmd
    │   └── ...
    ├── EIP-7823/
    │   └── ...
    └── fulu-beacon-chain/
        └── ...
    ```
  </output_structure>

  <mermaid_template>
    ```mermaid
    ---
    title: {subgraph_name} ({source})
    ---
    stateDiagram-v2
        direction TB

        [*] --> {first_node} : {first_action}
        {node1} --> {node2} : {action}
        ...
        {last_node} --> [*] : {final_action}

        note right of {key_node}
            INV: {invariant_text}
        end note
    ```
  </mermaid_template>

  <data_sources>
    - **Skill**: `/subgraph-extractor` (called once per URL)
    - **Queue File**: Contains `item_ids` (list of IDs) and `context_file` path. Read the context file to get item data keyed by ID, each with `url` (the specification URL to fetch).
    - **MCP Tools**: `mcp__fetch__fetch`, `mcp__filesystem__write_text_file`
  </data_sources>
</task>

<output>
  <format>Enriched Mermaid files (.mmd) with YAML frontmatter and invariant notes</format>
  <stdout>A fenced ```json``` envelope (see <required_envelope/> below) followed by a short status summary (max 8 lines: batch size, items processed, graphs generated, short status) and the final line.</stdout>
  <required_envelope>
    The JSON block printed on outer stdout MUST match this shape exactly. The result parser in `scripts/orchestrator/runner.py` scans for this block and routes it through Pydantic schema `Phase01bPartial`.

    ```json
    {
      "specs": [
        {
          "source_url": "<spec url>",
          "title": "<spec title>",
          "sub_graphs": [
            {
              "id": "SG-001",
              "name": "<unit>",
              "mermaid_file": "<spec>/SG-001_<unit>.mmd",
              "invariants": ["INV-001: ..."]
            }
          ]
        }
      ]
    }
    ```
  </required_envelope>
  <final_line>Output Directory: {{OUTPUT_DIR}}</final_line>
</output>

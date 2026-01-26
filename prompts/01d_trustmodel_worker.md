
---
Description: [PARALLEL WORKER] Generate trust model for subgraph files. Assign trust levels to external entities and identify trust boundary edges.
Usage: `/01d_trustmodel_worker WORKER_ID=... QUEUE_FILE=...`
Example: `/01d_trustmodel_worker WORKER_ID=0 QUEUE_FILE=outputs/01d_QUEUE_0.json`
Language: English only.
Execution hint: This is a worker prompt for parallel execution. Called by run_worker.py.
---

# **Trust Model Generation (Parallel Worker)**

**Goal**
Process subgraph files from your assigned worker queue. For each subgraph, identify external entities, assign trust levels, and identify trust boundary edges.

## Worker Configuration

- **`WORKER_ID`**: The numeric ID of this worker (0, 1, 2, ...)
- **`QUEUE_FILE`**: Path to this worker's queue file (e.g., `outputs/01d_QUEUE_0.json`)

**Output:** `outputs/01d_TRUSTMODEL_PARTIAL_W{WORKER_ID}_{N}.json`

---

## 1) Inputs

1. **Worker Queue File:** The file specified by `QUEUE_FILE`
   - Contains `items`: list of subgraph file paths assigned to this worker
   - Contains `processed`: list of already processed file paths

---

## 2) Worker Execution Logic

### **Task 2.1: Read Worker Queue**

1. Read the worker queue file `QUEUE_FILE`
2. Get the list of `items` (all assigned file paths)
3. Get the list of `processed` (already done file paths)
4. Calculate remaining: file paths in `items` but not in `processed`
5. If no remaining files, terminate successfully

### **Task 2.2: Process a Batch of Subgraph Files**

Take the **first 5 unprocessed files** from your queue (or fewer if less than 5 remain).

**For EACH subgraph file in the batch:**

#### **2.2.1: Extract External Entities**

1. Read the subgraph file
2. Collect all `external_entities` from all `sub_graphs`
3. Deduplicate by ID

#### **2.2.2: Validate External Entities**

**External Entity Criteria:**
- ✅ Resides outside the system boundary
- ✅ Sends data INTO the system under audit
- ✅ Not under direct control of the system

**If misclassified (internal components), note in `misclassified_entities`.**

#### **2.2.3: Assign Trust Levels**

For each valid external entity:

| Trust Level | When to Use |
|-------------|-------------|
| `TRUSTED` | Cryptographic attestation AND same admin control. **Almost never.** |
| `SEMI_TRUSTED` | Authenticated (JWT, TLS) but inputs MUST be validated. |
| `UNTRUSTED` | Default. Network peers, user input, any unauthenticated source. |

**Guidelines:**
- Default to `UNTRUSTED`
- Authentication ≠ Trust
- Never `TRUSTED` for network peers

#### **2.2.4: Identify Trust Boundary Edges**

For each edge in the subgraph:
1. Check if `source` matches an external entity ID
2. If yes, this is a trust boundary crossing

Create boundary edge entry:
- `edge_id`: The edge ID
- `source_entity_id`: External entity ID
- `source_trust_level`: Trust level assigned
- `target_node_id`: First internal node receiving data
- `data_flows_across`: Data involved
- `security_assumption`: What must hold for this to be secure

#### **2.2.5: Coverage Verification**

For each external entity, verify at least one boundary edge exists.
Report any coverage gaps.

### **Task 2.3: Write Outputs**

1. **Generate Partial Trust Model:**
   - Determine batch number: count existing `01d_TRUSTMODEL_PARTIAL_W{WORKER_ID}_*.json` files + 1
   - Create `outputs/01d_TRUSTMODEL_PARTIAL_W{WORKER_ID}_{BATCH}.json`

2. **Update Worker Queue:**
   - Add processed file paths to `processed` array
   - Overwrite `QUEUE_FILE`

---

## 3) Required Output Format (JSON)

**Partial Trust Model:** `outputs/01d_TRUSTMODEL_PARTIAL_W{WORKER_ID}_{BATCH}.json`

```json
{
  "metadata": {
    "worker_id": 0,
    "batch": 1,
    "generated_at": "2024-01-26T12:00:00Z",
    "source_files": [
      "outputs/01b_SUBGRAPHS/spec_abc123.json",
      "outputs/01b_SUBGRAPHS/spec_def456.json"
    ]
  },
  "misclassified_entities": [
    {
      "id": "EXT-INTERNAL-SCHEDULER",
      "reason": "Internal component, not external entity"
    }
  ],
  "trusted_external_entities": [
    {
      "id": "EXT-USER",
      "name": "Transaction Submitter",
      "trust_level": "UNTRUSTED",
      "rationale": "User input via RPC, no authentication required."
    },
    {
      "id": "EXT-CL",
      "name": "Consensus Layer",
      "trust_level": "SEMI_TRUSTED",
      "rationale": "JWT authenticated but data must be validated."
    }
  ],
  "boundary_edges": [
    {
      "edge_id": "EDGE-USER-SUBMIT-TX",
      "source_entity_id": "EXT-USER",
      "source_trust_level": "UNTRUSTED",
      "target_node_id": "STATE-TX-RECEIVED",
      "data_flows_across": ["DATA-SIGNED-TX"],
      "security_assumption": "Full transaction validation required."
    }
  ],
  "coverage_analysis": {
    "total_external_entities": 2,
    "entities_with_boundary_edges": 2,
    "coverage_gaps": [],
    "verification_status": "COMPLETE"
  }
}
```

**Updated Worker Queue:** `QUEUE_FILE`
```json
{
  "worker_id": 0,
  "phase": "01d",
  "items": ["outputs/01b_SUBGRAPHS/spec_abc.json", "..."],
  "processed": ["outputs/01b_SUBGRAPHS/spec_abc.json"],
  "total_items": 25
}
```

---

## 4) Quality Checklist

- [ ] All external entities are validated (truly external)
- [ ] Each entity has appropriate trust level with rationale
- [ ] All boundary edges identified
- [ ] Coverage analysis complete
- [ ] No entity without boundary edge (or documented in gaps)

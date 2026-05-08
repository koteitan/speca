---
sidebar_position: 2
---

# Phase 01a: Spec Discovery

Recursively discovers and crawls specification documents from seed URLs.

## Input

Specify the starting URLs of the specification documents in the `SPEC_URLS` environment variable.

```bash
SPEC_URLS="https://github.com/ethereum/EIPs/blob/master/EIPS/eip-7594.md" \
  uv run python3 scripts/run_phase.py --phase 01a
```

For multiple URLs, separate them with spaces:

```bash
SPEC_URLS="https://example.com/spec1.md https://example.com/spec2.md" \
  uv run python3 scripts/run_phase.py --phase 01a
```

## Processing

- Fetches URLs via the `mcp__fetch__fetch` MCP tool
- Converts HTML to Markdown
- Analyzes the link structure to discover related documents
- Avoids revisiting URLs that have already been crawled

## Output

`outputs/01a_STATE.json` — an index of all discovered documents.

```json
{
  "urls": [
    {
      "url": "https://...",
      "title": "EIP-7594: ...",
      "content": "...",
      "links": ["https://...", ...]
    }
  ],
  "crawl_timestamp": "2026-05-07T12:00:00Z"
}
```

This file is consumed as input by Phase 01b.

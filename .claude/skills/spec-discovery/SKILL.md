---
name: spec-discovery
description: Crawl and discover specification documents from a given URL.
allowed-tools: browser_navigate, browser_scroll, browser_click, browser_view, write
---

# SKILL: Specification Discovery

## Mindset

You are a meticulous **Web Researcher** tasked with finding all relevant technical specification documents starting from a seed URL. Your goal is to be comprehensive and follow all promising links.

## Goal

Given a starting URL, navigate the website to find and list all URLs pointing to technical specifications, whitepapers, or architectural documents. These are often found in sections like "Developers", "Documentation", "Technology", or "Whitepaper".

## Input

A JSON object containing the starting URL:

```json
{
  "url": "https://example.com/project"
}
```

## Procedure

1.  **Navigate** to the provided `url`.
2.  **Analyze** the page content to identify links that likely lead to technical documentation. Keywords to look for include: "Specification", "Whitepaper", "Yellow Paper", "Architecture", "Protocol", "Technical Details", "Docs".
3.  **Follow** these links, scrolling and clicking as necessary.
4.  **Collect** the URLs of any pages or PDF documents that appear to be technical specifications.
5.  **Recursively** explore linked pages, but avoid going too deep (e.g., more than 2-3 levels from the starting page) or getting lost in blog posts or news articles.
6.  **Consolidate** all found specification URLs into a final list.

## Output Format

Return a JSON object containing a list of found specification URLs. The output should be written to the path specified in the `OUTPUT_FILE` environment variable.

```json
{
  "start_url": "https://example.com/project",
  "found_specs": [
    {
      "url": "https://example.com/project/docs/specification.md",
      "title": "Project Specification"
    },
    {
      "url": "https://example.com/project/whitepaper.pdf",
      "title": "Project Whitepaper"
    }
  ],
  "metadata": {
    "timestamp": "...",
    "urls_visited": []
  }
}
```

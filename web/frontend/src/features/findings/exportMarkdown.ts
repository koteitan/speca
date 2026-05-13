// exportMarkdown — pure conversion from a list of findings to a Markdown
// report. The shape mirrors CLI spec §3.1 step 7 (Ctrl-S export):
//
//   # SPECA Findings — <run_id>
//
//   Generated: <ISO timestamp>
//   Total: <n> (data source: current outputs/, v0)
//
//   ## Critical (n)
//
//   ### <property_id> — <verdict>
//   - File: <file>:<line_range>
//   - Phase: <phase>
//
//   Proof trace:
//   ```
//   ...
//   ```
//
//   Reviewer notes:
//   ```
//   ...
//   ```
//
//   ---
//
// Design notes:
// - Severity groups are emitted in SEVERITY_RANK order (Critical → Info)
//   so the most actionable findings are at the top.
// - Within each group, the caller's pre-sorted ordering is preserved.
//   This is important because the list page applies filter+sort+pagination
//   client-side and the export must reflect what the user sees.
// - proof_trace / reviewer_notes / evidence_snippet are wrapped in fenced
//   code blocks. The fence length is computed (3 or more backticks) so
//   that bodies which themselves contain ``` cannot break out of the
//   block. The render-time `>` / backtick characters that would otherwise
//   trip the markdown parser are therefore safe-by-construction.
// - The function is intentionally side-effect-free. The download trigger
//   lives in `useDownloadMarkdown.ts` so server-side / test code can call
//   `findingsToMarkdown()` without touching `window`.

import { SEVERITY_LEVELS, SEVERITY_RANK, type Finding, type Severity } from "./types";

export interface FindingsToMarkdownOptions {
  runId: string;
  findings: Finding[];
  meta?: {
    count: number;
  };
  /**
   * Override the generated timestamp. Tests inject a fixed value; the
   * production path lets the function default to `new Date()`.
   */
  generatedAt?: Date;
}

const DATA_SOURCE_TAG = "current outputs/, v0";

/**
 * Pick the minimum fence length that does not collide with any run of
 * backticks inside `body`. Markdown requires the fence to be strictly
 * longer than any embedded backtick run, so a body containing ```` ```
 * `` would need at least four backticks.
 */
function fenceFor(body: string): string {
  let longest = 0;
  const matches = body.match(/`+/g);
  if (matches) {
    for (const m of matches) {
      if (m.length > longest) longest = m.length;
    }
  }
  return "`".repeat(Math.max(3, longest + 1));
}

/**
 * Wrap `body` in a fenced code block sized to survive any backticks the
 * body contains. Trailing whitespace is trimmed so the result is
 * tightly packed.
 */
function fenceBlock(body: string): string {
  const fence = fenceFor(body);
  // Normalise CRLF → LF so the on-disk file is consistent across OSes.
  const normalised = body.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  return `${fence}\n${normalised.replace(/\s+$/, "")}\n${fence}`;
}

function formatFile(finding: Finding): string {
  if (!finding.file) return "—";
  if (finding.line_range && finding.line_range.length > 0) {
    return `${finding.file}:${finding.line_range}`;
  }
  return finding.file;
}

function formatVerdict(verdict: string | null): string {
  return verdict && verdict.length > 0 ? verdict : "—";
}

function renderFinding(finding: Finding): string {
  const lines: string[] = [];
  lines.push(`### ${finding.property_id} — ${formatVerdict(finding.verdict)}`);
  lines.push(`- File: ${formatFile(finding)}`);
  lines.push(`- Phase: ${finding.phase}`);
  if (finding.gates_passed.length > 0) {
    lines.push(`- Gates passed: ${finding.gates_passed.join(", ")}`);
  }

  if (finding.evidence_snippet && finding.evidence_snippet.trim().length > 0) {
    lines.push("");
    lines.push("Evidence snippet:");
    lines.push(fenceBlock(finding.evidence_snippet));
  }

  if (finding.proof_trace && finding.proof_trace.trim().length > 0) {
    lines.push("");
    lines.push("Proof trace:");
    lines.push(fenceBlock(finding.proof_trace));
  }

  if (finding.reviewer_notes && finding.reviewer_notes.trim().length > 0) {
    lines.push("");
    lines.push("Reviewer notes:");
    lines.push(fenceBlock(finding.reviewer_notes));
  }

  return lines.join("\n");
}

/**
 * Convert a list of findings into a Markdown report. Pure function —
 * does not touch `window`, `document`, or any global state, so it is
 * safe to call from SSR / test / worker contexts.
 */
export function findingsToMarkdown(opts: FindingsToMarkdownOptions): string {
  const { runId, findings, meta, generatedAt } = opts;
  const generated = (generatedAt ?? new Date()).toISOString();
  const total = meta?.count ?? findings.length;

  // Bucket findings by severity, preserving caller ordering within each
  // bucket. We iterate `SEVERITY_LEVELS` in declaration order, which is
  // Critical → Informational by construction.
  const buckets = new Map<Severity, Finding[]>();
  for (const sev of SEVERITY_LEVELS) {
    buckets.set(sev, []);
  }
  for (const f of findings) {
    const bucket = buckets.get(f.severity);
    // Defensive: a forked verdict/severity that is not in SEVERITY_LEVELS
    // should still appear in the report. Append it under the lowest
    // severity so report readers do not miss it.
    if (bucket) {
      bucket.push(f);
    } else {
      buckets.get("Informational")!.push(f);
    }
  }

  // Sanity: assert we walked the buckets in priority order.
  const ordered = [...SEVERITY_LEVELS].sort(
    (a, b) => SEVERITY_RANK[a] - SEVERITY_RANK[b],
  );

  const sections: string[] = [];
  sections.push(`# SPECA Findings — ${runId}`);
  sections.push("");
  sections.push(`Generated: ${generated}`);
  sections.push(`Total: ${total} (data source: ${DATA_SOURCE_TAG})`);

  for (const sev of ordered) {
    const rows = buckets.get(sev) ?? [];
    if (rows.length === 0) continue;
    sections.push("");
    sections.push(`## ${sev} (${rows.length})`);
    for (let i = 0; i < rows.length; i += 1) {
      sections.push("");
      sections.push(renderFinding(rows[i]));
      if (i < rows.length - 1) {
        sections.push("");
        sections.push("---");
      }
    }
  }

  // Trailing newline so the file ends cleanly (POSIX convention).
  return `${sections.join("\n")}\n`;
}

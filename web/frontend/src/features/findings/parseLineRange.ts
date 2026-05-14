// Tiny helpers for the `line_range` shape that 02c / 03 emit.
//
// `line_range` is a free-form string in the wire schema (e.g. `"L80-L91"`,
// `"L80"`, `"80-91"`, or even `"unknown"`). The findings list / detail
// rendering just shows it verbatim, but the `<OpenInVSCode>` integration
// needs an *integer* to pass through to `code -g <path>:<line>` — so we
// pull the first L-prefixed (or bare) integer we can find and ignore the
// rest. `null` is returned for anything we cannot parse so the caller can
// fall back to a plain "open the file" without a line jump.

const LINE_START_RE = /^\s*L?(\d+)/;

export function parseLineStart(lineRange: string | null | undefined): number | null {
  if (!lineRange) return null;
  const match = LINE_START_RE.exec(lineRange);
  if (!match) return null;
  const n = Number.parseInt(match[1], 10);
  // VSCode CLI accepts 1-based line numbers; treat 0 / negative as invalid.
  if (!Number.isFinite(n) || n < 1) return null;
  return n;
}

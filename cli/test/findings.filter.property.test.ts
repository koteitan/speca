/**
 * Property-based tests for the filter DSL.
 *
 * The filter parser is a hand-written recursive-descent — the kind of code
 * where adversarial inputs (unbalanced parens, lone quotes, deep nesting,
 * invisible whitespace) trip up corner cases. These properties pin the
 * algebraic shape of the language and catch crashes that example-based
 * tests miss.
 */
import * as fc from "fast-check";
import { describe, expect, it } from "vitest";

import { applyFilter, parseFilter } from "../src/lib/findings/filter.js";
import type { Finding } from "../src/lib/findings/types.js";

function mk(partial: Partial<Finding> & { propertyId: string }): Finding {
  const haystack = [
    partial.propertyId,
    partial.summary,
    partial.proofTrace,
    partial.attackScenario,
    partial.reviewerNotes,
    partial.classification,
    partial.verdict,
    partial.specReference,
    partial.primaryLocation?.file ?? "",
  ]
    .filter(Boolean)
    .join("\n")
    .toLowerCase();
  return {
    id: partial.propertyId,
    propertyId: partial.propertyId,
    severity: partial.severity ?? "",
    rawSeverity: partial.rawSeverity ?? partial.severity ?? "",
    verdict: partial.verdict ?? "",
    classification: partial.classification ?? "",
    summary: partial.summary ?? "",
    proofTrace: partial.proofTrace ?? "",
    attackScenario: partial.attackScenario ?? "",
    reviewerNotes: partial.reviewerNotes ?? "",
    finalRecommendation: partial.finalRecommendation ?? "",
    specReference: partial.specReference ?? "",
    primaryLocation: partial.primaryLocation ?? null,
    allLocations: partial.allLocations ?? [],
    searchHaystack: haystack,
    sourceFiles: partial.sourceFiles ?? [],
    importIndex: partial.importIndex ?? 0,
  };
}

const SEVERITIES = ["Critical", "High", "Medium", "Low", "Informational"] as const;
const VERDICTS = [
  "CONFIRMED_VULNERABILITY",
  "CONFIRMED_POTENTIAL",
  "DISPUTED_FP",
  "DOWNGRADED",
  "NEEDS_MANUAL_REVIEW",
  "PASS_THROUGH",
] as const;

const findingArb = fc.record({
  propertyId: fc.string({ minLength: 3, maxLength: 16 }).map((s) => `PROP-${s}`),
  severity: fc.constantFrom(...SEVERITIES),
  verdict: fc.constantFrom(...VERDICTS),
  classification: fc.constantFrom("CRITICAL_BUG", "PROOF_INCOMPLETE", "PROOF_VALID"),
  summary: fc.string({ minLength: 0, maxLength: 80 }),
  reviewerNotes: fc.string({ minLength: 0, maxLength: 60 }),
  sourceFiles: fc.array(fc.string({ minLength: 1, maxLength: 30 }), { maxLength: 3 }),
}).map((p) => mk(p));

const datasetArb = fc.array(findingArb, { minLength: 1, maxLength: 20 });

describe("parseFilter — never throws (fuzz)", () => {
  it("returns ok or a typed FilterError for any string input", () => {
    fc.assert(
      fc.property(fc.string({ minLength: 0, maxLength: 60 }), (s) => {
        // Should never throw — malformed input must surface as ok:false.
        const r = parseFilter(s);
        if (r.ok) return typeof r.predicate === "function";
        return typeof r.message === "string";
      }),
      { numRuns: 500 },
    );
  });

  it("never throws on heavily-nested / metacharacter-heavy inputs", () => {
    // fast-check v4 dropped `stringOf`; we synthesise an adversarial token
    // soup by joining a random selection of metacharacters and DSL keywords.
    const tokens = fc
      .array(
        fc.constantFrom(
          "(",
          ")",
          '"',
          "'",
          "*",
          "?",
          ":",
          "AND",
          " ",
          "OR",
          "NOT",
          "-",
          "severity",
          "verdict",
          "prop",
          "Critical",
          "CONFIRMED_*",
        ),
        { maxLength: 40 },
      )
      .map((arr: string[]) => arr.join(""));
    fc.assert(
      fc.property(tokens, (s: string) => {
        const r = parseFilter(s);
        return r.ok || r.ok === false;
      }),
      { numRuns: 500 },
    );
  });
});

describe("applyFilter — algebraic properties", () => {
  it("empty filter is identity over the dataset", () => {
    fc.assert(
      fc.property(datasetArb, (data) => {
        const { matched } = applyFilter(data, "");
        expect(matched.length).toBe(data.length);
      }),
      { numRuns: 100 },
    );
  });

  it("NOT(p) is the complement of p (well-formed atomic queries)", () => {
    const queryArb = fc.oneof(
      fc.constantFrom(...SEVERITIES).map((s) => `severity:${s}`),
      fc.constantFrom(...VERDICTS).map((v) => `verdict:${v}`),
      fc.constantFrom(...VERDICTS).map((v) => `verdict:${v.split("_")[0]}_*`),
    );
    fc.assert(
      fc.property(datasetArb, queryArb, (data, q) => {
        const yes = applyFilter(data, q).matched.length;
        const no = applyFilter(data, `NOT (${q})`).matched.length;
        expect(yes + no).toBe(data.length);
      }),
      { numRuns: 100 },
    );
  });

  it("AND is commutative on well-formed atoms (set equality of matched ids)", () => {
    const sevQ = fc.constantFrom(...SEVERITIES).map((s) => `severity:${s}`);
    const verdQ = fc.constantFrom(...VERDICTS).map((v) => `verdict:${v}`);
    fc.assert(
      fc.property(datasetArb, sevQ, verdQ, (data, a, b) => {
        const ab = new Set(applyFilter(data, `${a} ${b}`).matched.map((f) => f.propertyId));
        const ba = new Set(applyFilter(data, `${b} ${a}`).matched.map((f) => f.propertyId));
        expect(ab).toEqual(ba);
      }),
      { numRuns: 100 },
    );
  });

  it("AND is a subset of either operand", () => {
    const sevQ = fc.constantFrom(...SEVERITIES).map((s) => `severity:${s}`);
    const verdQ = fc.constantFrom(...VERDICTS).map((v) => `verdict:${v}`);
    fc.assert(
      fc.property(datasetArb, sevQ, verdQ, (data, a, b) => {
        const ab = applyFilter(data, `${a} ${b}`).matched;
        const aOnly = applyFilter(data, a).matched;
        const bOnly = applyFilter(data, b).matched;
        const aIds = new Set(aOnly.map((f) => f.propertyId));
        const bIds = new Set(bOnly.map((f) => f.propertyId));
        for (const f of ab) {
          expect(aIds.has(f.propertyId)).toBe(true);
          expect(bIds.has(f.propertyId)).toBe(true);
        }
      }),
      { numRuns: 100 },
    );
  });

  it("OR is a superset of either operand", () => {
    const sevA = fc.constantFrom(...SEVERITIES).map((s) => `severity:${s}`);
    const sevB = fc.constantFrom(...SEVERITIES).map((s) => `severity:${s}`);
    fc.assert(
      fc.property(datasetArb, sevA, sevB, (data, a, b) => {
        const orRes = applyFilter(data, `${a} OR ${b}`).matched;
        const aOnly = applyFilter(data, a).matched;
        const bOnly = applyFilter(data, b).matched;
        const orIds = new Set(orRes.map((f) => f.propertyId));
        for (const f of aOnly) expect(orIds.has(f.propertyId)).toBe(true);
        for (const f of bOnly) expect(orIds.has(f.propertyId)).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  it("double negation: NOT NOT(p) ≡ p", () => {
    const queryArb = fc.constantFrom(...SEVERITIES).map((s) => `severity:${s}`);
    fc.assert(
      fc.property(datasetArb, queryArb, (data, q) => {
        const a = new Set(applyFilter(data, q).matched.map((f) => f.propertyId));
        const b = new Set(
          applyFilter(data, `NOT (NOT (${q}))`).matched.map((f) => f.propertyId),
        );
        expect(a).toEqual(b);
      }),
      { numRuns: 100 },
    );
  });

  it("filter result is always a subset of the dataset, never larger", () => {
    fc.assert(
      fc.property(datasetArb, fc.string({ minLength: 0, maxLength: 60 }), (data, q) => {
        const r = applyFilter(data, q);
        // ok or not-ok, the matched array must be a subset (never invent rows)
        expect(r.matched.length).toBeLessThanOrEqual(data.length);
        const ids = new Set(data.map((f) => f.propertyId));
        for (const f of r.matched) expect(ids.has(f.propertyId)).toBe(true);
      }),
      { numRuns: 200 },
    );
  });
});

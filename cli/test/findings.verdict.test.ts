import { describe, expect, it } from "vitest";
import {
  KNOWN_VERDICTS,
  isKnownVerdict,
} from "../src/lib/findings/types.js";

describe("KNOWN_VERDICTS — closed set + drift detection", () => {
  it("isKnownVerdict agrees with KNOWN_VERDICTS membership", () => {
    for (const v of KNOWN_VERDICTS) {
      expect(isKnownVerdict(v)).toBe(true);
    }
    expect(isKnownVerdict("CONFIRMED_TYPO")).toBe(false);
    expect(isKnownVerdict("confirmed_vulnerability")).toBe(false);
    expect(isKnownVerdict("")).toBe(false);
  });

  it("includes the documented Phase 04 verdicts (sanity check vs SPEC §5.4)", () => {
    // If this list changes the SPEC must be updated too. The reverse
    // (SPEC change but not const) is what the unit covers.
    expect(KNOWN_VERDICTS).toContain("CONFIRMED_VULNERABILITY");
    expect(KNOWN_VERDICTS).toContain("CONFIRMED_POTENTIAL");
    expect(KNOWN_VERDICTS).toContain("DISPUTED_FP");
    expect(KNOWN_VERDICTS).toContain("DOWNGRADED");
    expect(KNOWN_VERDICTS).toContain("NEEDS_MANUAL_REVIEW");
    expect(KNOWN_VERDICTS).toContain("PASS_THROUGH");
    expect(KNOWN_VERDICTS).toHaveLength(6);
  });
});

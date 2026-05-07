import { describe, expect, it } from "vitest";
import {
  KNOWN_PHASE_IDS,
  PHASE_NAMES,
  isKnownPhaseId,
  phaseName,
} from "../src/lib/pipeline/phase-names.js";

describe("KNOWN_PHASE_IDS — closed set + drift detection", () => {
  it("isKnownPhaseId agrees with KNOWN_PHASE_IDS membership", () => {
    for (const id of KNOWN_PHASE_IDS) {
      expect(isKnownPhaseId(id)).toBe(true);
    }
    expect(isKnownPhaseId("99x")).toBe(false);
    expect(isKnownPhaseId("")).toBe(false);
  });

  it("PHASE_NAMES covers every id in KNOWN_PHASE_IDS", () => {
    for (const id of KNOWN_PHASE_IDS) {
      expect(typeof PHASE_NAMES[id]).toBe("string");
      expect(PHASE_NAMES[id].length).toBeGreaterThan(0);
    }
  });

  it("phaseName returns the friendly label for known ids", () => {
    expect(phaseName("01a")).toBe("Spec Discovery");
    expect(phaseName("04")).toBe("Audit Review");
  });

  it("phaseName falls back to the id for unknown phases (forks may add new ones)", () => {
    expect(phaseName("99x")).toBe("99x");
    expect(phaseName("custom-phase")).toBe("custom-phase");
  });
});

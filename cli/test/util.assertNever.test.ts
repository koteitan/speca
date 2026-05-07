import { describe, expect, it } from "vitest";
import { assertNever } from "../src/lib/util/assertNever.js";

describe("assertNever", () => {
  it("throws with the JSON representation of the unhandled value", () => {
    // We deliberately bypass the type system to exercise the runtime backstop.
    expect(() => assertNever({ type: "wat" } as never)).toThrowError(/wat/);
  });

  it("includes the context label when provided", () => {
    expect(() => assertNever("oops" as never, "applyPipelineEvent")).toThrowError(
      /applyPipelineEvent/,
    );
  });

  it("falls back to String() when JSON.stringify throws", () => {
    const cyclic: { a?: unknown } = {};
    cyclic.a = cyclic;
    // Should not blow up due to circular ref — falls back to String().
    expect(() => assertNever(cyclic as never)).toThrowError(/object|Object/);
  });
});

import { describe, expect, it } from "vitest";
import { ERROR_KINDS } from "../src/lib/errors/kinds.js";
import { formatStderrError, reportStderrError } from "../src/lib/errors/report.js";

describe("formatStderrError", () => {
  it("emits the parseable `kind=<kind>` token and the default title/hint", () => {
    const out = formatStderrError("auth-expired", { message: "token past expiry" });
    expect(out).toMatch(/^\[ERROR kind=auth-expired\] /);
    expect(out).toContain(ERROR_KINDS["auth-expired"].defaultTitle);
    expect(out).toContain(ERROR_KINDS["auth-expired"].defaultHint);
    expect(out).toContain("token past expiry");
    expect(out.endsWith("\n")).toBe(true);
  });

  it("honours custom title and hint overrides", () => {
    const out = formatStderrError("schema-mismatch", {
      title: "Custom title",
      message: "all 5 partials failed validation",
      hint: "Re-export schemas first",
    });
    expect(out).toContain("Custom title");
    expect(out).toContain("Re-export schemas first");
    expect(out).not.toContain(ERROR_KINDS["schema-mismatch"].defaultTitle);
  });

  it("falls back to the `unknown` kind metadata when given an unrecognised kind", () => {
    const out = formatStderrError("totally-not-a-kind" as never, {
      message: "what happened",
    });
    // Token still reflects what the caller passed (parseable contract).
    expect(out).toContain("kind=totally-not-a-kind");
    // But title/hint come from the `unknown` fallback.
    expect(out).toContain(ERROR_KINDS.unknown.defaultTitle);
    expect(out).toContain(ERROR_KINDS.unknown.defaultHint);
  });

  for (const kind of Object.keys(ERROR_KINDS)) {
    it(`renders without crashing for kind=${kind}`, () => {
      const out = formatStderrError(kind as never, { message: "sample" });
      expect(out).toContain(`kind=${kind}`);
    });
  }
});

describe("reportStderrError", () => {
  function makeStream(): { write: (chunk: string) => boolean; chunks: string[] } {
    const chunks: string[] = [];
    return {
      chunks,
      write(chunk: string) {
        chunks.push(chunk);
        return true;
      },
    };
  }

  it("writes one formatted line to the supplied stream and returns a non-zero exit code", () => {
    const stream = makeStream();
    const code = reportStderrError(
      "subprocess-crash",
      { message: "child exited with code 137" },
      2,
      stream,
    );
    expect(code).toBe(2);
    expect(stream.chunks).toHaveLength(1);
    expect(stream.chunks[0]).toContain("kind=subprocess-crash");
    expect(stream.chunks[0]).toContain("child exited with code 137");
  });

  it("defaults exit code to 1", () => {
    const stream = makeStream();
    const code = reportStderrError("schema-mismatch", { message: "bad" }, undefined, stream);
    expect(code).toBe(1);
  });
});

import { describe, expect, it } from "vitest";
import { z } from "zod";
import { humaniseFlag, parseFlags } from "../src/lib/cli-flags/index.js";
import { loginFlagsSchema } from "../src/commands/auth/login.js";

describe("humaniseFlag", () => {
  it("formats camelCase keys as kebab-case --flags", () => {
    expect(humaniseFlag("apiKey")).toBe("--api-key");
    expect(humaniseFlag("maxConcurrent")).toBe("--max-concurrent");
    expect(humaniseFlag("mode")).toBe("--mode");
  });

  it("returns a placeholder for empty input", () => {
    expect(humaniseFlag("")).toBe("<flag>");
  });
});

describe("parseFlags", () => {
  const schema = z.object({
    apiKey: z.string().min(1).optional(),
    mode: z.enum(["max", "console"]).optional(),
  });

  it("returns a typed flags object on success", () => {
    const r = parseFlags(schema, { apiKey: "sk-ant-...", mode: "max" });
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.flags.apiKey).toBe("sk-ant-...");
      expect(r.flags.mode).toBe("max");
    }
  });

  it("rejects an invalid enum and reports the kebab-case flag name", () => {
    const r = parseFlags(schema, { mode: "console-pro" }, "speca auth login");
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.message).toMatch(/speca auth login/);
      expect(r.message).toMatch(/--mode/);
    }
  });

  it("collects multiple errors into one message", () => {
    const tight = z.object({
      apiKey: z.string().min(5),
      mode: z.enum(["max", "console"]),
    });
    const r = parseFlags(tight, { apiKey: "x", mode: "huh" });
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.message.split("\n").length).toBeGreaterThanOrEqual(3);
    }
  });
});

describe("loginFlagsSchema (auth login)", () => {
  it("accepts known flag values", () => {
    const r = parseFlags(loginFlagsSchema, { apiKey: "sk-ant-x", mode: "console" });
    expect(r.ok).toBe(true);
  });

  it("rejects an unknown --mode value", () => {
    const r = parseFlags(loginFlagsSchema, { mode: "premium" });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.message).toMatch(/--mode/);
  });

  it("ignores unrelated flags meow may surface from other subcommands", () => {
    // `allowUnknownFlags: true` in cli.tsx means meow may pass `phase`,
    // `target`, etc. through; the schema must not blow up on them.
    const r = parseFlags(loginFlagsSchema, {
      apiKey: "sk-ant-x",
      mode: "max",
      phase: ["01a"],
      json: true,
    });
    expect(r.ok).toBe(true);
  });
});

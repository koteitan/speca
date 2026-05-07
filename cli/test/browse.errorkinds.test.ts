/**
 * Verifies that `speca browse` surfaces the `schema-mismatch` ErrorKind
 * (per #28) when every matched file fails Zod validation.
 */
import { promises as fs } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { runBrowseCommand } from "../src/commands/browse.js";

let tmpRoot: string;
let stderrCapture: { chunks: string[]; restore(): void };

beforeEach(async () => {
  tmpRoot = await fs.mkdtemp(join(tmpdir(), "speca-browse-error-"));
  const chunks: string[] = [];
  const orig = process.stderr.write.bind(process.stderr);
  process.stderr.write = ((c: string | Uint8Array): boolean => {
    chunks.push(typeof c === "string" ? c : Buffer.from(c).toString("utf8"));
    return true;
  }) as typeof process.stderr.write;
  stderrCapture = {
    chunks,
    restore() {
      process.stderr.write = orig;
    },
  };
});

afterEach(async () => {
  stderrCapture.restore();
  await fs.rm(tmpRoot, { recursive: true, force: true });
});

describe("speca browse — schema-mismatch wiring", () => {
  it("returns kind=schema-mismatch when every matched file fails the partial schema", async () => {
    // Two PARTIAL files that both fail JSON parse (the loader's
    // partialFileSchema uses `.passthrough()` so structural-only mismatch
    // does not warn — only actual parse failures or top-level type
    // rejections do). Use guaranteed-invalid bodies so both files produce
    // the warning that schema-mismatch keys off.
    await fs.mkdir(join(tmpRoot, "outputs"), { recursive: true });
    await fs.writeFile(
      join(tmpRoot, "outputs/04_PARTIAL_W0B0.json"),
      "{not valid json at all",
      "utf8",
    );
    await fs.writeFile(
      join(tmpRoot, "outputs/04_PARTIAL_W1B0.json"),
      "also not json",
      "utf8",
    );

    const code = await runBrowseCommand({
      flags: { noTui: true, json: false },
      positional: [],
      cwd: tmpRoot,
    });

    expect(code).toBe(1);
    const stderr = stderrCapture.chunks.join("");
    expect(stderr).toContain("kind=schema-mismatch");
    expect(stderr).toMatch(/file.*failed validation/i);
  });

  it("does NOT fire schema-mismatch when at least one file parses cleanly", async () => {
    await fs.mkdir(join(tmpRoot, "outputs"), { recursive: true });
    // One valid Phase 04 partial (empty reviewed_items list satisfies the
    // schema's `reviewed_items: list[ReviewedItem]` field).
    await fs.writeFile(
      join(tmpRoot, "outputs/04_PARTIAL_W0B0.json"),
      JSON.stringify({ reviewed_items: [] }),
      "utf8",
    );
    // One bogus file alongside.
    await fs.writeFile(
      join(tmpRoot, "outputs/04_PARTIAL_W1B0.json"),
      "not json",
      "utf8",
    );

    const code = await runBrowseCommand({
      flags: { noTui: true, json: false },
      positional: [],
      cwd: tmpRoot,
    });

    // Even though one file failed, the loader returned at least zero
    // findings from the valid file, which the no-tui path then prints.
    // We assert that schema-mismatch did NOT fire (the partial validation
    // is lenient by design).
    const stderr = stderrCapture.chunks.join("");
    expect(stderr).not.toContain("kind=schema-mismatch");
    expect(code).toBe(0);
  });
});

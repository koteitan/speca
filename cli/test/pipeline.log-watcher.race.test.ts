/**
 * Concurrency tests for `startLogWatcher`.
 *
 * The pure helpers (parseLogFilename, summariseRawLogLine) are covered in
 * `pipeline.log-watcher.test.ts`. This file exercises the chokidar-driven
 * tail itself — specifically the per-file cursor state machine that gets
 * hit concurrently when many `change` events fire close together.
 */
import { promises as fs } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  startLogWatcher,
  type LogLine,
} from "../src/lib/pipeline/log-watcher.js";

let dir: string;
let stop: (() => Promise<void>) | null = null;

beforeEach(async () => {
  dir = await fs.mkdtemp(join(tmpdir(), "speca-watcher-race-"));
});

afterEach(async () => {
  if (stop) {
    await stop();
    stop = null;
  }
  await fs.rm(dir, { recursive: true, force: true });
});

function makeEvent(label: string): string {
  return `${JSON.stringify({ type: "system", message: { subtype: label } })}\n`;
}

async function settle(ms = 200): Promise<void> {
  await new Promise((r) => setTimeout(r, ms));
}

describe("startLogWatcher — concurrent appends", () => {
  it("does not lose lines when many appends happen back-to-back", async () => {
    const path = join(dir, "01a_w0b0_concurrent.log.jsonl");
    await fs.writeFile(path, "");

    const seen: LogLine[] = [];
    stop = await startLogWatcher({
      dir,
      onLine: (line) => seen.push(line),
      pollIntervalMs: 30,
    });
    // Give chokidar a moment to register the existing empty file.
    await settle(100);

    const writers = 8;
    const linesPerWriter = 50;
    await Promise.all(
      Array.from({ length: writers }, async (_, w) => {
        for (let i = 0; i < linesPerWriter; i++) {
          await fs.appendFile(path, makeEvent(`w${w}-${i}`));
        }
      }),
    );
    // Drain via stop() — guarantees a final flush of every cursor regardless
    // of how the polling tick lined up with the last append.
    await stop();
    stop = null;

    // Every appended line should arrive exactly once.
    const expected = writers * linesPerWriter;
    const summaries = seen.map((l) => l.summary);

    expect(summaries.length).toBe(expected);

    // Each unique label appears exactly once (no duplicates, no drops).
    const counts = new Map<string, number>();
    for (const s of summaries) counts.set(s, (counts.get(s) ?? 0) + 1);
    expect(counts.size).toBe(expected);
    for (const [, n] of counts) expect(n).toBe(1);
  }, 30_000);

  it("re-reads from byte 0 after a truncation (cursor reset)", async () => {
    const path = join(dir, "01a_w0b0_truncate.log.jsonl");
    await fs.writeFile(path, "");

    const seen: LogLine[] = [];
    stop = await startLogWatcher({
      dir,
      onLine: (line) => seen.push(line),
      pollIntervalMs: 30,
    });
    await settle(80);

    await fs.appendFile(path, makeEvent("first-1"));
    await fs.appendFile(path, makeEvent("first-2"));
    await settle(150);

    // Truncate and write fresh content. The cursor must reset to 0 so we
    // pick up the new lines, not silently skip them because `stat.size <
    // cursor.size`.
    await fs.writeFile(path, "");
    await settle(150);
    await fs.appendFile(path, makeEvent("after-truncate"));
    await stop();
    stop = null;

    const summaries = seen.map((l) => l.summary);
    expect(summaries).toContain("system: first-1");
    expect(summaries).toContain("system: first-2");
    expect(summaries).toContain("system: after-truncate");
  }, 30_000);

  it("handles multiple files updated in parallel without crossing state", async () => {
    const pathA = join(dir, "01a_w0b0_a.log.jsonl");
    const pathB = join(dir, "01b_w1b0_b.log.jsonl");
    await fs.writeFile(pathA, "");
    await fs.writeFile(pathB, "");

    const seen: LogLine[] = [];
    stop = await startLogWatcher({
      dir,
      onLine: (line) => seen.push(line),
      pollIntervalMs: 30,
    });
    await settle(100);

    await Promise.all([
      (async () => {
        for (let i = 0; i < 30; i++) await fs.appendFile(pathA, makeEvent(`A-${i}`));
      })(),
      (async () => {
        for (let i = 0; i < 30; i++) await fs.appendFile(pathB, makeEvent(`B-${i}`));
      })(),
    ]);
    await stop();
    stop = null;

    const fromA = seen.filter((l) => l.phase === "01a");
    const fromB = seen.filter((l) => l.phase === "01b");
    expect(fromA.length).toBe(30);
    expect(fromB.length).toBe(30);
    // Phase tag never crosses files.
    for (const l of fromA) expect(l.summary).toMatch(/^system: A-/);
    for (const l of fromB) expect(l.summary).toMatch(/^system: B-/);
  }, 30_000);
});

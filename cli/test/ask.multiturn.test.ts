/**
 * Closes #31. End-to-end multi-turn chat round-trip via `runAskCommand`.
 *
 * Verifies the full chain that the existing unit slices don't:
 *   1. First turn — no prior session on disk → spawnAsk called WITHOUT
 *      sessionId → server returns its own id → CLI captures it and
 *      writes `<projectRoot>/.speca/session.json`.
 *   2. Second turn — prior session on disk → spawnAsk called WITH the
 *      stored id (so the real CLI would emit `--resume <id>`) → server
 *      may rotate the id → CLI updates session.json with bumped
 *      `last_used_at` and the latest server-side id.
 *
 * `spawnAsk` is replaced with a fake whose only side effect is to record
 * the (prompt, sessionId) tuple per call and replay a canned event
 * sequence — that's the smallest seam needed to exercise the chain
 * deterministically without spinning up the real claude binary.
 */
import { promises as fs } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { runAskCommand } from "../src/commands/ask.js";
import { loadSession } from "../src/lib/claude-session/store.js";
import type {
  ParsedEvent,
  SpawnAskHandle,
  SpawnAskOptions,
} from "../src/lib/claude-session/spawn.js";

let tmpRoot: string;

beforeEach(async () => {
  tmpRoot = await fs.mkdtemp(join(tmpdir(), "speca-ask-multiturn-"));
});

afterEach(async () => {
  // session.json is written via async tmp+rename — wait briefly so the rmdir
  // doesn't race the writer (mirrors ask.render.test.ts's afterEach).
  await new Promise((r) => setTimeout(r, 50));
  await fs.rm(tmpRoot, { recursive: true, force: true, maxRetries: 5, retryDelay: 50 });
});

interface SpawnCall {
  prompt: string;
  sessionId: string | undefined;
}

interface FakeSpawnHarness {
  /** All spawnAsk invocations in order. */
  calls: SpawnCall[];
  /** Server-side id returned when no --resume id is requested. */
  freshId: string;
  /** The spawnAsk replacement to pass into runAskCommand. */
  spawnFn: (opts: SpawnAskOptions) => Promise<SpawnAskHandle>;
}

function makeFakeSpawn(): FakeSpawnHarness {
  const harness: FakeSpawnHarness = {
    calls: [],
    freshId: "session-from-server-1",
    spawnFn: async (opts: SpawnAskOptions): Promise<SpawnAskHandle> => {
      harness.calls.push({ prompt: opts.prompt, sessionId: opts.sessionId });
      // Mirror the real CLI: when --resume <id> is requested, every event
      // carries that id back. Otherwise the server invents one
      // (`freshId`) and uses it across the response stream.
      const id = opts.sessionId ?? harness.freshId;
      const events: ParsedEvent[] = [
        { type: "system", subtype: "init", session_id: id, raw: {} },
        {
          type: "assistant",
          text: `reply-to:${opts.prompt.slice(-40)}`,
          session_id: id,
          raw: {},
        },
        { type: "result", subtype: "success", session_id: id, raw: {} },
        { type: "done", code: 0, session_id: id },
      ];
      return {
        pid: 1,
        kill: () => {},
        events: (async function* () {
          for (const ev of events) yield ev;
        })() as AsyncIterable<ParsedEvent>,
      };
    },
  };
  return harness;
}

describe("speca ask --no-tui — multi-turn chat round-trip (#31)", () => {
  it("turn 1 establishes the session, turn 2 re-uses the captured id", async () => {
    const harness = makeFakeSpawn();
    const out1: string[] = [];
    const err1: string[] = [];

    // ---- Turn 1 ----------------------------------------------------------
    const code1 = await runAskCommand({
      positional: [],
      flags: { noTui: true },
      projectRoot: tmpRoot,
      spawnFn: harness.spawnFn,
      stdin: Readable.from("first question\n"),
      log: (m) => out1.push(m),
      errorLog: (m) => err1.push(m),
    });

    expect(code1).toBe(0);
    expect(harness.calls).toHaveLength(1);
    // Critical: turn 1 must NOT carry a sessionId — there's no prior
    // state on disk and the user didn't pass --session.
    expect(harness.calls[0].sessionId).toBeUndefined();
    expect(harness.calls[0].prompt).toContain("first question");
    expect(out1.join("")).toContain("reply-to:first question");

    // session.json now reflects what the server returned.
    const stored1 = await loadSession(tmpRoot);
    expect(stored1).not.toBeNull();
    expect(stored1!.session_id).toBe("session-from-server-1");
    const turn1UsedAt = stored1!.last_used_at;

    // ---- Turn 2 ----------------------------------------------------------
    // Sleep so the touch can move last_used_at forward (Date.now()
    // resolution is 1 ms but Node sometimes returns the same value across
    // tight calls; a small wait makes the assertion robust).
    await new Promise((r) => setTimeout(r, 5));

    const out2: string[] = [];
    const code2 = await runAskCommand({
      positional: [],
      flags: { noTui: true },
      projectRoot: tmpRoot,
      spawnFn: harness.spawnFn,
      stdin: Readable.from("follow-up question\n"),
      log: (m) => out2.push(m),
      errorLog: () => {},
    });

    expect(code2).toBe(0);
    expect(harness.calls).toHaveLength(2);
    // Critical: turn 2 MUST carry the id captured from turn 1's response.
    // This is the bit that proves session.json is consulted and threaded
    // back into the spawn invocation (which the real CLI will translate
    // into `--resume <id>` via buildClaudeArgs).
    expect(harness.calls[1].sessionId).toBe("session-from-server-1");
    expect(harness.calls[1].prompt).toContain("follow-up question");
    expect(out2.join("")).toContain("reply-to:follow-up question");

    // session.json: the real claude CLI echoes the same id back when
    // resumed, so session_id stays put — but last_used_at must move
    // forward so the orchestrator can age out idle sessions later.
    const stored2 = await loadSession(tmpRoot);
    expect(stored2).not.toBeNull();
    expect(stored2!.session_id).toBe("session-from-server-1");
    expect(stored2!.last_used_at).toBeGreaterThan(turn1UsedAt);
  }, 30_000);

  it("--session <id> overrides the on-disk session for that single turn", async () => {
    const harness = makeFakeSpawn();
    // Pre-populate session.json with one id, then drive a turn passing a
    // different `--session` flag. The flag must win.
    await fs.mkdir(join(tmpRoot, ".speca"), { recursive: true });
    await fs.writeFile(
      join(tmpRoot, ".speca", "session.json"),
      JSON.stringify({
        session_id: "from-disk",
        created_at: 1,
        last_used_at: 1,
        finding_context_bytes: 0,
      }),
      "utf8",
    );

    const code = await runAskCommand({
      positional: [],
      flags: { noTui: true, session: "from-flag" },
      projectRoot: tmpRoot,
      spawnFn: harness.spawnFn,
      stdin: Readable.from("anything\n"),
      log: () => {},
      errorLog: () => {},
    });

    expect(code).toBe(0);
    expect(harness.calls).toHaveLength(1);
    expect(harness.calls[0].sessionId).toBe("from-flag");
  }, 30_000);
});

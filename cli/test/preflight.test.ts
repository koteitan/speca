import { promises as fs } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  detectExpiredAuth,
  detectStaleResume,
} from "../src/lib/checks/preflight.js";

let tmpRoot: string;

beforeEach(async () => {
  tmpRoot = await fs.mkdtemp(join(tmpdir(), "speca-preflight-"));
});

afterEach(async () => {
  await fs.rm(tmpRoot, { recursive: true, force: true });
});

// ---- detectExpiredAuth -----------------------------------------------------

describe("detectExpiredAuth", () => {
  async function writeAuth(payload: object): Promise<string> {
    const path = join(tmpRoot, "auth.json");
    await fs.writeFile(path, JSON.stringify(payload), "utf8");
    return path;
  }

  it("returns null when no auth file is on disk (env var path may apply)", async () => {
    const result = await detectExpiredAuth({ authFile: join(tmpRoot, "nonexistent.json") });
    expect(result).toBeNull();
  });

  it("returns null for an api-key account (no expiry)", async () => {
    const path = await writeAuth({
      version: 1,
      accounts: { default: { type: "apikey", access_token: "sk-x", created_at: 1 } },
    });
    expect(await detectExpiredAuth({ authFile: path })).toBeNull();
  });

  it("returns null for a non-expired OAuth token", async () => {
    const now = 1_700_000_000_000;
    const path = await writeAuth({
      version: 1,
      accounts: {
        default: {
          type: "oauth",
          access_token: "a",
          refresh_token: "r",
          expires_at: now + 60_000, // 1 minute in the future
          scopes: ["user:sessions:claude_code"],
          created_at: now,
        },
      },
    });
    expect(await detectExpiredAuth({ authFile: path, now })).toBeNull();
  });

  it("returns a typed failure when the OAuth token is past expiry", async () => {
    const now = 1_700_000_000_000;
    const path = await writeAuth({
      version: 1,
      accounts: {
        default: {
          type: "oauth",
          access_token: "a",
          refresh_token: "r",
          expires_at: now - 60_000, // 1 minute in the past
          scopes: ["user:sessions:claude_code"],
          created_at: now - 3_600_000,
        },
      },
    });
    const result = await detectExpiredAuth({ authFile: path, now });
    expect(result).not.toBeNull();
    expect(result!.message.toLowerCase()).toContain("expired");
  });
});

// ---- detectStaleResume -----------------------------------------------------

describe("detectStaleResume", () => {
  async function touch(path: string, mtimeMs: number): Promise<void> {
    await fs.mkdir(resolve(path, ".."), { recursive: true });
    await fs.writeFile(path, "{}", "utf8");
    const t = mtimeMs / 1000;
    await fs.utimes(path, t, t);
  }

  it("returns null when there is no TARGET_INFO.json", async () => {
    const result = await detectStaleResume({ cwd: tmpRoot, force: false });
    expect(result).toBeNull();
  });

  it("returns null when there are no 01b partials yet", async () => {
    await touch(join(tmpRoot, "outputs", "TARGET_INFO.json"), 1_700_000_000_000);
    const result = await detectStaleResume({ cwd: tmpRoot, force: false });
    expect(result).toBeNull();
  });

  it("returns null when partials are newer than TARGET_INFO (normal resume)", async () => {
    const targetMtime = 1_700_000_000_000;
    const partialMtime = targetMtime + 5 * 60_000; // 5 min after target
    await touch(join(tmpRoot, "outputs", "TARGET_INFO.json"), targetMtime);
    await touch(join(tmpRoot, "outputs", "01b_PARTIAL_W0B0.json"), partialMtime);

    const result = await detectStaleResume({
      cwd: tmpRoot,
      force: false,
      graceMs: 60_000,
    });
    expect(result).toBeNull();
  });

  it("returns null when force=true even with a stale layout", async () => {
    const targetMtime = 1_700_000_000_000;
    const partialMtime = targetMtime - 60 * 60_000; // 1 hour before target
    await touch(join(tmpRoot, "outputs", "TARGET_INFO.json"), targetMtime);
    await touch(join(tmpRoot, "outputs", "01b_PARTIAL_W0B0.json"), partialMtime);

    const result = await detectStaleResume({
      cwd: tmpRoot,
      force: true,
      graceMs: 60_000,
    });
    expect(result).toBeNull();
  });

  it("returns a failure when TARGET_INFO is much newer than the newest partial", async () => {
    const partialMtime = 1_700_000_000_000;
    const targetMtime = partialMtime + 10 * 60_000; // 10 min later
    await touch(join(tmpRoot, "outputs", "TARGET_INFO.json"), targetMtime);
    await touch(join(tmpRoot, "outputs", "01b_PARTIAL_W0B0.json"), partialMtime);

    const result = await detectStaleResume({
      cwd: tmpRoot,
      force: false,
      graceMs: 60_000,
    });
    expect(result).not.toBeNull();
    expect(result!.message).toMatch(/01b partial/);
    expect(result!.message).toMatch(/different target/);
  });

  it("respects the grace window (60s default)", async () => {
    const partialMtime = 1_700_000_000_000;
    const targetMtime = partialMtime + 30_000; // 30s — within 60s grace
    await touch(join(tmpRoot, "outputs", "TARGET_INFO.json"), targetMtime);
    await touch(join(tmpRoot, "outputs", "01b_PARTIAL_W0B0.json"), partialMtime);

    const result = await detectStaleResume({ cwd: tmpRoot, force: false });
    expect(result).toBeNull();
  });
});

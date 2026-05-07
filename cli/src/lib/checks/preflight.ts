/**
 * Pre-flight checks that fire BEFORE `speca run` spawns the orchestrator.
 *
 * Each detector returns either `null` (clean) or a typed `{message, kind}`
 * record that the caller routes through {@link reportStderrError}. Keeping
 * the detectors pure (file I/O via injected paths, no globals) lets us
 * unit-test each branch with a tmp directory.
 *
 * The pre-flight surface is intentionally conservative — the detectors
 * fire only on signals that are unambiguous on disk. Anything that needs
 * cross-checking with a remote service (token refresh, target_commit
 * verification against the cloned repo) lives behind `speca doctor`.
 */
import { promises as fs } from "node:fs";
import { resolve } from "node:path";
import fastGlob from "fast-glob";

import { checkAuth } from "../../auth/check.js";

export interface PreflightFailure {
  message: string;
  /** Optional override hint; falls back to the kind's default if omitted. */
  hint?: string;
}

/**
 * Returns a failure when the only available auth account is an OAuth one
 * whose `expires_at` is past, because every Claude CLI call the orchestrator
 * issues will then 401. We DO NOT fire when:
 *   - No account is on disk (the user might be relying on env-var
 *     `ANTHROPIC_API_KEY` that the orchestrator picks up directly).
 *   - The active account is `apikey` (no expiry to check).
 *   - The OAuth token is still valid.
 */
export async function detectExpiredAuth(opts: {
  authFile?: string;
  now?: number;
} = {}): Promise<PreflightFailure | null> {
  const result = await checkAuth({ authFile: opts.authFile, now: opts.now });
  // `checkAuth` returns warn=expired with the exact phrase 'token expired'
  // in `detail`. We re-use that wording rather than re-implementing the
  // expiry check so the doctor and pre-flight stay in lockstep.
  if (result.status === "warn" && (result.detail ?? "").includes("token expired")) {
    return {
      message: result.detail ?? "OAuth token has expired",
      hint: result.hint,
    };
  }
  return null;
}

/**
 * Returns a failure when there are pre-existing Phase 01b partial files on
 * disk AND `outputs/TARGET_INFO.json` was last touched MORE recently than
 * the newest of those partials (with a 60-second grace window).
 *
 * Heuristic rationale: `speca init` rewrites `TARGET_INFO.json`. If the user
 * re-ran `init` after a prior pipeline run produced partials, those partials
 * reference the OLD target. Continuing without `--force` would feed stale
 * subgraphs into Phase 02c+. The grace window absorbs the trivial case of
 * `init` and `run` being executed back-to-back in the same minute.
 *
 * This is NOT a strict commit-match check — that would require parsing
 * embedded metadata in each partial, which the orchestrator does not yet
 * record consistently. The mtime heuristic catches the common
 * "user re-ran init mid-project" footgun and exits with the
 * `stale-resume` kind.
 */
export async function detectStaleResume(opts: {
  cwd: string;
  force: boolean;
  outputDir?: string;
  graceMs?: number;
}): Promise<PreflightFailure | null> {
  if (opts.force) return null;
  const root = opts.outputDir ?? resolve(opts.cwd, "outputs");
  const targetInfoPath = resolve(root, "TARGET_INFO.json");
  let targetMtime: number;
  try {
    const stat = await fs.stat(targetInfoPath);
    targetMtime = stat.mtimeMs;
  } catch {
    // No TARGET_INFO.json — nothing to check against.
    return null;
  }

  const partialPaths = await fastGlob("01b_PARTIAL_*.json", {
    cwd: root,
    absolute: true,
    onlyFiles: true,
  });
  if (partialPaths.length === 0) {
    return null;
  }

  let newestPartialMtime = 0;
  for (const p of partialPaths) {
    try {
      const stat = await fs.stat(p);
      if (stat.mtimeMs > newestPartialMtime) newestPartialMtime = stat.mtimeMs;
    } catch {
      continue;
    }
  }

  const grace = opts.graceMs ?? 60_000;
  if (targetMtime <= newestPartialMtime + grace) {
    // TARGET_INFO is older than (or coeval with) the newest partial — the
    // partials were produced after the most recent target reconfig.
    return null;
  }

  const ageDiffSec = Math.round((targetMtime - newestPartialMtime) / 1000);
  return {
    message:
      `outputs/TARGET_INFO.json was modified ${ageDiffSec}s after the newest 01b partial; ` +
      `the cached subgraphs may reference a different target than the one currently configured`,
  };
}

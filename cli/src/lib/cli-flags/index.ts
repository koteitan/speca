/**
 * Tiny Zod-backed flag parser for speca-cli subcommands.
 *
 * `meow` returns `flags` as `{ [k: string]: string | number | boolean | undefined }`.
 * Using those values directly leaks the loose types into command handlers
 * (e.g. `--mode <x>` where only "max" / "console" are valid). Routing the
 * raw object through a Zod schema gives us:
 *
 *   - runtime validation with helpful error messages
 *   - a narrowed TypeScript type at the call site
 *   - a single place to document the supported flags
 *
 * Subcommand authors define their schema in their own file and import
 * `parseFlags` here.
 */
import type { z } from "zod";

export interface FlagsParseSuccess<T> {
  ok: true;
  flags: T;
}

export interface FlagsParseError {
  ok: false;
  /** Multiline message ready to write to stderr. */
  message: string;
}

export type FlagsParseResult<T> = FlagsParseSuccess<T> | FlagsParseError;

/**
 * Parse `raw` through `schema`, formatting Zod errors into a user-friendly
 * stderr block. The flag names are humanised (`apiKey` → `--api-key`) so the
 * message reads like the help text, not like JSON paths.
 */
export function parseFlags<T>(
  schema: z.ZodType<T>,
  raw: Record<string, unknown>,
  context = "speca",
): FlagsParseResult<T> {
  const r = schema.safeParse(raw);
  if (r.success) return { ok: true, flags: r.data };
  const issues = r.error.issues
    .map((i) => `  - ${humaniseFlag(String(i.path[0] ?? ""))}: ${i.message}`)
    .join("\n");
  return {
    ok: false,
    message: `${context}: invalid flags\n${issues}\n`,
  };
}

/** Convert camelCase flag keys back to the `--kebab-case` users typed. */
export function humaniseFlag(key: string): string {
  if (!key) return "<flag>";
  return `--${key.replace(/([A-Z])/g, (_m, c: string) => `-${c.toLowerCase()}`)}`;
}

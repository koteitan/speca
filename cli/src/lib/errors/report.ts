/**
 * Stderr-side error reporter for the same taxonomy used by `<ErrorModal>`.
 *
 * Subcommands surface failure modes either as an Ink modal (TUI mode, when a
 * dashboard / browser is already mounted) or as a stderr block + non-zero
 * exit code (pre-flight + non-TTY paths). This module owns the latter.
 *
 * Output shape:
 *
 *   [ERROR kind=<kind>] <title>: <message>
 *     Hint: <hint>
 *
 * The `kind=` token is parseable (CI, scripts) and the title / hint mirror
 * exactly what `<ErrorModal>` would render, so users see the same wording
 * regardless of mode.
 */
import { ERROR_KINDS, type ErrorKind } from "./kinds.js";

export interface FormatStderrErrorOptions {
  /** Override the default title (defaults to `ERROR_KINDS[kind].defaultTitle`). */
  title?: string;
  /** The specific message describing what happened. */
  message: string;
  /** Override the default hint (defaults to `ERROR_KINDS[kind].defaultHint`). */
  hint?: string;
}

export function formatStderrError(
  kind: ErrorKind,
  opts: FormatStderrErrorOptions,
): string {
  const meta = ERROR_KINDS[kind] ?? ERROR_KINDS.unknown;
  const title = opts.title ?? meta.defaultTitle;
  const hint = opts.hint ?? meta.defaultHint;
  return `[ERROR kind=${kind}] ${title}: ${opts.message}\n  Hint: ${hint}\n`;
}

/**
 * Convenience: format and write to a stream (defaults to process.stderr).
 * Returns the suggested exit code (always non-zero) so call sites can
 * tail-call this from inside a switch arm without hand-rolling the
 * boilerplate.
 */
export function reportStderrError(
  kind: ErrorKind,
  opts: FormatStderrErrorOptions,
  exitCode = 1,
  stream: { write(chunk: string): boolean | void } = process.stderr,
): number {
  stream.write(formatStderrError(kind, opts));
  return exitCode;
}

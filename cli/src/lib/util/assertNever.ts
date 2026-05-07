/**
 * Exhaustiveness helper for discriminated-union switches.
 *
 * Usage:
 *
 *   switch (event.type) {
 *     case "a": return ...;
 *     case "b": return ...;
 *     default: return assertNever(event);
 *   }
 *
 * If a new variant is added to the union but not handled here, TypeScript will
 * flag the call as a compile error because `event` is no longer `never`.
 *
 * Throws at runtime as a defensive backstop in case of a JSON payload that
 * fails the discriminator narrowing (should never reach here under normal
 * operation since the parser is Zod-validated).
 */
export function assertNever(x: never, context?: string): never {
  const repr = (() => {
    try {
      return JSON.stringify(x);
    } catch {
      return String(x);
    }
  })();
  throw new Error(
    context
      ? `assertNever: unhandled discriminator in ${context}: ${repr}`
      : `assertNever: unhandled discriminator: ${repr}`,
  );
}

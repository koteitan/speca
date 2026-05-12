// Tiny UUID v4 helper, used to mint a conversation id client-side.
//
// We prefer `crypto.randomUUID()` (available in all evergreen browsers and
// Node 19+). The manual fallback only kicks in on older runtimes — Vite
// targets modern browsers anyway but keeping it pure means we can run the
// helper in tests / SSR without a polyfill.

export function newConversationId(): string {
  // `globalThis.crypto?.randomUUID` is the modern path. We feature-detect
  // with optional chaining so SSR / Node test runners (where `crypto` may
  // be missing) cleanly fall through to the polyfill.
  const c =
    typeof globalThis !== "undefined"
      ? (globalThis.crypto as Crypto | undefined)
      : undefined;
  if (c?.randomUUID) {
    return c.randomUUID();
  }
  // Polyfill: RFC 4122 v4 from 16 random bytes. Not constant-time, but
  // we only need uniqueness, not unguessability.
  const bytes = new Uint8Array(16);
  if (c?.getRandomValues) {
    c.getRandomValues(bytes);
  } else {
    for (let i = 0; i < 16; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  // Set version (4) and variant (10xx).
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex: string[] = [];
  for (let i = 0; i < 16; i += 1) {
    hex.push(bytes[i].toString(16).padStart(2, "0"));
  }
  return (
    hex.slice(0, 4).join("") +
    "-" +
    hex.slice(4, 6).join("") +
    "-" +
    hex.slice(6, 8).join("") +
    "-" +
    hex.slice(8, 10).join("") +
    "-" +
    hex.slice(10, 16).join("")
  );
}

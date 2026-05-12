// Term glossary for the <Tooltip term="..."/> component.
//
// Section 4.10.2 of `docs/UI_DESIGN.md` requires inline hover hints for
// SPECA-specific jargon. The dictionary is intentionally small (~12
// entries) — adding rare terms here costs nothing.
//
// Slice I2 — Translation strings live in the locale JSON under
// `glossary.<term>`. This file just owns the canonical key list + the
// i18n lookup. The TypeScript keys themselves stay as English term
// identifiers so call sites (`<Tooltip term="severity" />`) remain
// language-neutral.

import i18next from "@/i18n";

export type GlossaryKey =
  | "CWE"
  | "STRIDE"
  | "property"
  | "subgraph"
  | "verdict"
  | "severity"
  | "phase 03"
  | "phase 04"
  | "bug bounty scope"
  | "trust boundary"
  | "dead code"
  | "DISPUTED_FP"
  | "CONFIRMED_VULNERABILITY";

const GLOSSARY_KEYS: readonly GlossaryKey[] = [
  "CWE",
  "STRIDE",
  "property",
  "subgraph",
  "verdict",
  "severity",
  "phase 03",
  "phase 04",
  "bug bounty scope",
  "trust boundary",
  "dead code",
  "DISPUTED_FP",
  "CONFIRMED_VULNERABILITY",
];

function tryLookup(key: string): string | undefined {
  const i18nKey = `glossary.${key}`;
  const value = i18next.t(i18nKey);
  if (typeof value !== "string") return undefined;
  // i18next returns the key itself on miss — guard so we can fall back.
  if (value === i18nKey) return undefined;
  return value;
}

/** Lookup with case-insensitive fallback so callers can pass casual spellings. */
export function lookupGlossary(term: string): string | undefined {
  const direct = tryLookup(term);
  if (direct !== undefined) return direct;
  const lower = term.toLowerCase();
  for (const key of GLOSSARY_KEYS) {
    if (key.toLowerCase() === lower) {
      return tryLookup(key);
    }
  }
  return undefined;
}

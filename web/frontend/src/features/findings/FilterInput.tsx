// FilterInput — free-text DSL search box that complements the chip-based
// FilterBar. Mirrors `speca-cli`'s `/` filter prompt (SPECA_CLI_SPEC §5.4.1):
//   severity:high verdict:CONFIRMED_VULNERABILITY prop:PROP-6a4* foo
//
// State lives in the URL via `q=` so a filtered list is link-shareable in
// the same way as the chip filters. We debounce URL writes by 200 ms to
// avoid flooding the history stack while the user types.
//
// The chip-based FilterBar still works alongside this input — both layers
// are AND-combined in `FindingsListPage`. The DSL is the more general of
// the two; we keep chips for one-click affordance and discoverability.

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useT } from "@/i18n/useT";

import styles from "./FilterInput.module.css";
import type { ParsedFilter } from "./filterDsl";

export interface FilterInputProps {
  /** Pre-parsed view of the current URL query — used to render
   * "unknown key" hints. The parent feeds this so it never goes out of
   * sync with the value the page is actually filtering on. */
  parsed: ParsedFilter;
}

export function FilterInput({ parsed }: FilterInputProps) {
  const t = useT();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlValue = searchParams.get("q") ?? "";
  const [draft, setDraft] = useState<string>(urlValue);

  // Keep the input controlled against the URL: if some other surface
  // edits `q` (e.g. a "clear filter" button), we want the box to mirror
  // it without losing the cursor when the user is typing themselves.
  const lastUrlRef = useRef(urlValue);
  useEffect(() => {
    if (urlValue !== lastUrlRef.current) {
      lastUrlRef.current = urlValue;
      setDraft(urlValue);
    }
  }, [urlValue]);

  // Debounce URL writes — typing "severity:high" should not push 12
  // history entries.
  useEffect(() => {
    if (draft === urlValue) return;
    const handle = window.setTimeout(() => {
      const next = new URLSearchParams(searchParams);
      if (draft.trim() === "") {
        next.delete("q");
      } else {
        next.set("q", draft);
      }
      lastUrlRef.current = draft;
      setSearchParams(next, { replace: true });
    }, 200);
    return () => window.clearTimeout(handle);
    // We deliberately omit `searchParams` from deps — the URL is rewritten
    // by this effect itself; depending on it would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft]);

  const hasUnknown = parsed.unknownKeys.length > 0;

  return (
    <div className={styles.wrap} role="search">
      <label className={styles.label} htmlFor="filter-dsl-input">
        {t("findings.filter.dsl_label")}
      </label>
      <div className={styles.inputRow}>
        <input
          id="filter-dsl-input"
          type="search"
          className={styles.input}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setDraft("");
            }
          }}
          placeholder={t("findings.filter.dsl_placeholder")}
          autoComplete="off"
          spellCheck={false}
          data-testid="filter-dsl-input"
          aria-describedby="filter-dsl-help"
        />
        {draft !== "" && (
          <button
            type="button"
            className={styles.clearBtn}
            aria-label={t("findings.filter.dsl_clear_aria")}
            onClick={() => setDraft("")}
            data-testid="filter-dsl-clear"
          >
            ×
          </button>
        )}
      </div>
      <p id="filter-dsl-help" className={styles.help}>
        {t("findings.filter.dsl_help")}
      </p>
      {hasUnknown ? (
        <p className={styles.warning} role="status">
          {t("findings.filter.dsl_unknown_keys", {
            keys: parsed.unknownKeys.join(", "),
          })}
        </p>
      ) : null}
    </div>
  );
}

export default FilterInput;

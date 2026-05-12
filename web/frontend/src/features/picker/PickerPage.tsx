// Project Picker page — three entry points → shared NewRunDraft → R2.
//
// Layout: a 3-column grid (desktop) or stacked column (mobile). The
// columns are decoupled — each one mounts a small subcomponent so the
// other slices (B chat handoff, R2 review form) can plug in without
// rewriting this file.
//
// The "Ask Claude" panel is intentionally inert in this slice: the
// chat-open state still lives in `AppShell` `useState`, so a global
// trigger would require a new Zustand slice + AppShell modification.
// We surface the affordance as disabled with a hover-hint instead, per
// the slice spec.

import { useT } from "@/i18n/useT";

import { FromUrlForm } from "./FromUrlForm";
import { SavedTargetsList } from "./SavedTargetsList";
import styles from "./PickerPage.module.css";

// R2 is the destination for every entry point. It does not exist yet —
// the navigation may land on a 404 until R2 merges, which is the
// expected smoke-test contract for this slice.
const REVIEW_PATH = "/runs/new/review";

export default function PickerPage() {
  const t = useT();

  return (
    <section className={styles.page} data-testid="picker-page">
      <header className={styles.header}>
        <h1 className={styles.title}>{t("picker.page.title")}</h1>
        <p className={styles.subtitle}>{t("picker.page.subtitle")}</p>
      </header>

      <div className={styles.grid}>
        <article className={styles.card} aria-labelledby="picker-saved-title">
          <h2 id="picker-saved-title" className={styles.cardTitle}>
            {t("picker.page.saved")}
          </h2>
          <SavedTargetsList reviewPath={REVIEW_PATH} />
        </article>

        <article
          className={styles.card}
          aria-labelledby="picker-from-url-title"
        >
          <h2 id="picker-from-url-title" className={styles.cardTitle}>
            {t("picker.page.from_url")}
          </h2>
          <FromUrlForm reviewPath={REVIEW_PATH} />
        </article>

        <article
          className={styles.card}
          aria-labelledby="picker-ask-claude-title"
        >
          <h2 id="picker-ask-claude-title" className={styles.cardTitle}>
            {t("picker.page.ask_claude")}
          </h2>
          <p className={styles.askClaudeDescription}>
            {t("picker.ask_claude.description")}
          </p>
          <button
            type="button"
            className={styles.askClaudeButton}
            disabled
            title={
              // v0 chat panel lives in AppShell useState; this slice
              // does not own a global toggle. The right-side chat
              // button in the header is the supported affordance.
              "右上の chat ボタンから開いてください"
            }
            aria-disabled="true"
            data-testid="ask-claude-open"
          >
            {t("picker.ask_claude.open_chat")}
          </button>
        </article>
      </div>
    </section>
  );
}

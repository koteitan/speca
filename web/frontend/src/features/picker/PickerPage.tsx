// Project Picker page — three entry points → shared NewRunDraft → R2.
//
// Layout: a 3-column grid (desktop) or stacked column (mobile). The
// columns are decoupled — each one mounts a small subcomponent so the
// other slices (B chat handoff, R2 review form) can plug in without
// rewriting this file.
//
// The "Ask Claude" panel opens the right-side chat panel via the global
// chatUiSlice, mirroring what the header chat toggle does.

import { Link } from "react-router-dom";

import { useT } from "@/i18n/useT";
import { useChatUi } from "@/store/chatUiSlice";

import { FromUrlForm } from "./FromUrlForm";
import { SavedTargetsList } from "./SavedTargetsList";
import styles from "./PickerPage.module.css";

// R2 is the destination for every entry point. It does not exist yet —
// the navigation may land on a 404 until R2 merges, which is the
// expected smoke-test contract for this slice.
const REVIEW_PATH = "/runs/new/review";

export default function PickerPage() {
  const t = useT();
  const openChat = useChatUi((s) => s.setOpen);

  return (
    <section className={styles.page} data-testid="picker-page">
      <header className={styles.header}>
        <div className={styles.headerRow}>
          <h1 className={styles.title}>{t("picker.page.title")}</h1>
          <Link
            to="/runs/new/wizard"
            className={styles.wizardLink}
            data-testid="picker-open-wizard"
          >
            {t("picker.page.guided_wizard")}
          </Link>
        </div>
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
            onClick={() => openChat(true)}
            data-testid="ask-claude-open"
          >
            {t("picker.ask_claude.open_chat")}
          </button>
        </article>
      </div>
    </section>
  );
}

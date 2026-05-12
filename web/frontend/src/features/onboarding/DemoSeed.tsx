// First-launch demo banner.
//
// Section 4.10.7 of `docs/UI_DESIGN.md`: "デモプロジェクトを 1 つ
// pre-install" — surface a read-only litecoin card so the Saved targets
// list is never blank on first run. v0 cannot actually launch a run, so
// clicking the card opens a modal that explains the v1 limitation
// instead of dispatching anything.
//
// The component is *header-rank*: it only renders if `/api/picker/saved`
// returns a `source: "demo"` entry. Once a real run lands and pushes the
// demo seed out (it never does in v0, but the contract is forward-safe
// for v1+ when users dismiss the demo), this banner disappears.

import { useState } from "react";

import { useSavedTargets } from "../picker/useSavedTargets";
import styles from "./DemoSeed.module.css";

export function DemoSeed() {
  const { data, isPending, isError } = useSavedTargets();
  const [modalOpen, setModalOpen] = useState(false);

  // Strict gating: we render the banner only when the API has answered
  // *and* the demo entry is actually present. Anything else (loading,
  // error, no demo) → render nothing so the surrounding view doesn't
  // shift around.
  if (isPending || isError || !data) {
    return null;
  }
  const demo = data.find((entry) => entry.source === "demo");
  if (!demo) {
    return null;
  }

  return (
    <>
      <button
        type="button"
        className={styles.card}
        onClick={() => setModalOpen(true)}
      >
        <span className={styles.label}>サンプル</span>
        <span className={styles.title}>{demo.target_repo}</span>
        <span className={styles.note}>read-only preview</span>
      </button>

      {modalOpen ? (
        <div
          className={styles.modalBackdrop}
          role="dialog"
          aria-modal="true"
          aria-labelledby="demo-seed-modal-title"
          onClick={() => setModalOpen(false)}
        >
          <div
            className={styles.modal}
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id="demo-seed-modal-title" className={styles.modalTitle}>
              v1 で起動可能
            </h2>
            <p className={styles.modalBody}>
              {demo.target_repo} は v0 では read-only preview のみです。
              v1 で audit run の起動に対応します。
            </p>
            <button
              type="button"
              className={styles.modalClose}
              onClick={() => setModalOpen(false)}
            >
              OK
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}

export default DemoSeed;

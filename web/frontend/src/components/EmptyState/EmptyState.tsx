// Reusable empty-state card.
//
// Section 4.10.1 of `docs/UI_DESIGN.md` ("空状態に 次の一歩 を必ず表示")
// makes this a load-bearing primitive: every list view in v0 must show
// a non-blank empty state with an action. Keeping a single component
// means every slice gets the same look-and-feel for free.

import type { ReactNode } from "react";

import styles from "./EmptyState.module.css";

export interface EmptyStateAction {
  label: string;
  onClick: () => void;
}

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  action?: EmptyStateAction;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className={styles.wrapper} role="status">
      <div className={styles.card}>
        <h2 className={styles.title}>{title}</h2>
        {description ? (
          <p className={styles.description}>{description}</p>
        ) : null}
        {action ? (
          <button
            type="button"
            className={styles.action}
            onClick={action.onClick}
          >
            {action.label}
          </button>
        ) : null}
      </div>
    </div>
  );
}

export default EmptyState;

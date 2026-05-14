// Inline approval card for side-effecting chat tools (Slice C3).
//
// Rendered inside the chat transcript when the backend emits a
// ``tool_approval_required`` SSE event. The user picks Approve or Cancel
// here; their choice is POSTed to ``/chat/tool_approve`` (on a separate
// connection from the suspended SSE stream) which un-blocks the backend
// runtime and lets the tool either execute or be declined.
//
// v1 caveats:
//   - Edit-input UI is not implemented; ``edited_input`` is always sent
//     as ``undefined``. The user picks approve-as-proposed or cancel.
//   - "expired" comes from the backend's ``error{reason:"approval_timeout"}``
//     translated by the parent; the card just renders the static message.

import { useMemo } from "react";

import { useT } from "@/i18n/useT";
import styles from "./ApprovalCard.module.css";

export type ApprovalCardStatus =
  | "pending"
  | "approving"
  | "cancelling"
  | "resolved"
  | "expired";

export type ApprovalCardToolName = "launch_pipeline" | "stop_pipeline";

export interface ApprovalCardProps {
  toolCallId: string;
  name: ApprovalCardToolName;
  /** Raw tool input proposed by the model. */
  input: Record<string, unknown>;
  /** Optional preview block from the backend (``_render_preview``). */
  preview?: Record<string, unknown>;
  onApprove: () => void;
  onCancel: () => void;
  status: ApprovalCardStatus;
  errorMessage?: string;
}

/** Stringify a single preview value for display. */
function fmtValue(v: unknown): string {
  if (v == null || v === "") return "—";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "string" || typeof v === "number") return String(v);
  if (Array.isArray(v)) return v.map((x) => String(x)).join(", ");
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

interface FieldRow {
  labelKey: string;
  value: unknown;
}

function launchFields(input: Record<string, unknown>): FieldRow[] {
  return [
    { labelKey: "chat.approval.preview.bug_bounty_url", value: input.bug_bounty_url },
    { labelKey: "chat.approval.preview.target_repo", value: input.target_repo },
    { labelKey: "chat.approval.preview.target_ref", value: input.target_ref },
    {
      labelKey: "chat.approval.preview.contract_addresses",
      value: input.contract_addresses,
    },
    { labelKey: "chat.approval.preview.spec_urls", value: input.spec_urls },
    { labelKey: "chat.approval.preview.keywords", value: input.keywords },
    { labelKey: "chat.approval.preview.workers", value: input.workers },
    { labelKey: "chat.approval.preview.max_concurrent", value: input.max_concurrent },
    {
      labelKey: "chat.approval.preview.push_to_remote",
      value: input.push_to_remote,
    },
  ];
}

function stopFields(input: Record<string, unknown>): FieldRow[] {
  return [{ labelKey: "chat.approval.preview.run_id", value: input.run_id }];
}

export function ApprovalCard({
  toolCallId,
  name,
  input,
  preview,
  onApprove,
  onCancel,
  status,
  errorMessage,
}: ApprovalCardProps) {
  const t = useT();

  // Prefer backend preview.fields when present (it normalises e.g. defaults
  // for ``workers`` / ``max_concurrent``), otherwise fall back to ``input``.
  const fieldSource = useMemo<Record<string, unknown>>(() => {
    if (
      preview &&
      typeof preview === "object" &&
      "fields" in preview &&
      preview.fields &&
      typeof preview.fields === "object"
    ) {
      return preview.fields as Record<string, unknown>;
    }
    return input;
  }, [preview, input]);

  // ``resolved`` is a soft signal — the parent unmounts the card once the
  // ``tool_use_result`` arrives, but we still gate buttons defensively in
  // case re-render races set status before unmount.
  if (status === "resolved") {
    return null;
  }

  const isLaunch = name === "launch_pipeline";
  const titleKey = isLaunch
    ? "chat.approval.title_launch"
    : "chat.approval.title_stop";
  const rows = isLaunch ? launchFields(fieldSource) : stopFields(fieldSource);

  const disabled =
    status === "approving" || status === "cancelling" || status === "expired";

  const rootClass = `${styles.card} ${
    isLaunch ? styles.cardLaunch : styles.cardStop
  } ${status === "expired" ? styles.cardExpired : ""}`;

  return (
    <div
      className={rootClass}
      role="group"
      aria-label={t(titleKey)}
      data-testid={`approval-card-${name}`}
      data-tool-call-id={toolCallId}
    >
      <div className={styles.header}>
        <span className={styles.icon} aria-hidden="true">
          {isLaunch ? "▶" : "■"}
        </span>
        <span className={styles.title}>{t(titleKey)}</span>
        <span className={styles.awaiting}>{t("chat.approval.awaiting")}</span>
      </div>

      <dl className={styles.body}>
        {rows.map((row) => (
          <div className={styles.row} key={row.labelKey}>
            <dt className={styles.label}>{t(row.labelKey)}</dt>
            <dd className={styles.value}>{fmtValue(row.value)}</dd>
          </div>
        ))}
      </dl>

      {status === "expired" && (
        <p className={styles.expiredMessage} role="alert">
          {t("chat.approval.expired")}
        </p>
      )}

      {errorMessage && status !== "expired" && (
        <p className={styles.errorMessage} role="alert">
          {errorMessage}
        </p>
      )}

      <div className={styles.footer}>
        <button
          type="button"
          className={`${styles.button} ${styles.primary}`}
          onClick={onApprove}
          disabled={disabled}
          data-testid="approval-approve"
        >
          {status === "approving" ? (
            <>
              <span className={styles.spinner} aria-hidden="true" />
              {t("chat.approval.approving")}
            </>
          ) : (
            t("chat.approval.approve")
          )}
        </button>
        <button
          type="button"
          className={`${styles.button} ${styles.secondary}`}
          onClick={onCancel}
          disabled={disabled}
          data-testid="approval-cancel"
        >
          {status === "cancelling" ? (
            <>
              <span className={styles.spinner} aria-hidden="true" />
              {t("chat.approval.cancelling")}
            </>
          ) : (
            t("chat.approval.cancel")
          )}
        </button>
      </div>
    </div>
  );
}

export default ApprovalCard;

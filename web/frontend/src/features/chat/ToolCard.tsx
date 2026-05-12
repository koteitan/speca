import { useT } from "@/i18n/useT";

import styles from "./ToolCard.module.css";
import type { ToolCallStatus } from "./types";

/**
 * Render one tool_use card inline in the chat transcript.
 *
 * **Read-only by default.** v0 only exposed ``read_run_status`` /
 * ``list_findings`` / ``read_finding`` — none of these needed user
 * approval, and ``requiresApproval`` was typed ``never``.
 *
 * Slice C3 (v1) introduces side-effecting tools (``launch_pipeline`` /
 * ``stop_pipeline``) that *do* need approval. The prop type was loosened
 * to ``boolean | undefined`` — but the active rendering path for v1
 * lives in ``ChatPanel`` (a transient system meta row promotes to an
 * ``<ApprovalCard>``), so flipping ``requiresApproval`` here is a
 * compile-only hook for future inline-style integrations.
 */
export interface ToolCardProps {
  toolName: string;
  input: Record<string, unknown>;
  result?: Record<string, unknown>;
  status: ToolCallStatus;
  /** Marks a side-effecting tool that needs an approval gate.
   *  v1 callers leave this ``undefined`` — Slice C3 renders the
   *  approval card via the system meta row in ``ChatPanel`` instead. */
  requiresApproval?: boolean;
}

/** Compact one-line summary of the tool's input object for the header. */
function summarise(input: Record<string, unknown>, emptyLabel: string): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(input)) {
    parts.push(`${k}=${formatValue(v)}`);
    if (parts.join(", ").length > 80) break;
  }
  return parts.join(", ") || emptyLabel;
}

function formatValue(v: unknown): string {
  if (v == null) return "null";
  if (typeof v === "string") return v.length > 32 ? `"${v.slice(0, 30)}…"` : `"${v}"`;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return JSON.stringify(v).slice(0, 40);
}

/** Pretty-print the result. Errors bubble up as a single line; data dumps
 * are JSON-prettified and clipped to keep the chat bubble bounded. */
function summariseResult(result: Record<string, unknown> | undefined): string {
  if (!result) return "";
  if ("error" in result) {
    const tool = "tool" in result ? ` (${String(result.tool)})` : "";
    return `error: ${String(result.error)}${tool}`;
  }
  const text = JSON.stringify(result, null, 2);
  return text.length > 2000 ? text.slice(0, 2000) + "\n…(truncated)" : text;
}

export function ToolCard({
  toolName,
  input,
  result,
  status,
  requiresApproval,
}: ToolCardProps) {
  const t = useT();

  const statusLabel: Record<ToolCallStatus, string> = {
    running: t("chat.bubble.tool_status_running"),
    done: t("chat.bubble.tool_status_done"),
    error: t("chat.bubble.tool_status_error"),
  };

  // Slice C3: side-effect tool waiting on approval. v1 never sets this
  // (the ApprovalCard is rendered via the system meta row in ChatPanel)
  // — kept here so a future caller can opt into an inline render
  // without re-plumbing the type.
  if (requiresApproval) {
    return (
      <div
        className={styles.card}
        role="group"
        aria-label={t("chat.bubble.tool_approval_required_aria", {
          name: toolName,
        })}
        data-testid={`tool-card-${toolName}-pending`}
      >
        <div className={styles.header}>
          <span className={styles.icon} aria-hidden="true">
            !
          </span>
          <span className={styles.name}>{toolName}</span>
          <span className={styles.status}>
            {t("chat.bubble.tool_awaiting_approval")}
          </span>
        </div>
      </div>
    );
  }

  const inputSummary = summarise(input, t("chat.bubble.tool_no_input"));
  const resultText = summariseResult(result);

  return (
    <div
      className={`${styles.card} ${styles[`status_${status}`] ?? ""}`}
      role="group"
      aria-label={t("chat.bubble.tool_call_aria", { name: toolName })}
      data-testid={`tool-card-${toolName}`}
    >
      <div className={styles.header}>
        <span className={styles.icon} aria-hidden="true">
          ⚙
        </span>
        <span className={styles.name}>{toolName}</span>
        <span className={styles.status}>{statusLabel[status]}</span>
      </div>
      <div className={styles.input}>{inputSummary}</div>
      {resultText && (
        <pre className={styles.result}>
          <code>{resultText}</code>
        </pre>
      )}
    </div>
  );
}

export default ToolCard;

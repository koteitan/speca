import styles from "./ToolCard.module.css";
import type { ToolCallStatus } from "./types";

/**
 * Render one tool_use card inline in the chat transcript.
 *
 * **Read-only by design.** v0 only exposes ``read_run_status`` /
 * ``list_findings`` / ``read_finding`` — none of these need user
 * approval. The ``requiresApproval`` prop is typed ``never`` so any
 * future attempt to render an approval gate fails at compile time;
 * see slice E spec § 3 (the third defense gate).
 */
export interface ToolCardProps {
  toolName: string;
  input: Record<string, unknown>;
  result?: Record<string, unknown>;
  status: ToolCallStatus;
  /** Reserved for a future side-effecting tool. v0 must NOT use it. */
  requiresApproval?: never;
}

const STATUS_LABEL: Record<ToolCallStatus, string> = {
  running: "running",
  done: "done",
  error: "error",
};

/** Compact one-line summary of the tool's input object for the header. */
function summarise(input: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(input)) {
    parts.push(`${k}=${formatValue(v)}`);
    if (parts.join(", ").length > 80) break;
  }
  return parts.join(", ") || "(no input)";
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

export function ToolCard({ toolName, input, result, status }: ToolCardProps) {
  const inputSummary = summarise(input);
  const resultText = summariseResult(result);

  return (
    <div
      className={`${styles.card} ${styles[`status_${status}`] ?? ""}`}
      role="group"
      aria-label={`Tool call ${toolName}`}
      data-testid={`tool-card-${toolName}`}
    >
      <div className={styles.header}>
        <span className={styles.icon} aria-hidden="true">
          ⚙
        </span>
        <span className={styles.name}>{toolName}</span>
        <span className={styles.status}>{STATUS_LABEL[status]}</span>
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

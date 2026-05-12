import { Link, useParams } from "react-router-dom";

import { OpenInVSCode } from "@/components/OpenInVSCode";
import { useIntegrationsPaths } from "@/features/integrations/useIntegrationsStatus";

import { PhaseRow } from "./PhaseRow";
import { StatusIcon } from "./StatusIcon";
import type { RunDetail } from "./types";
import { useRunDetail } from "./useRuns";
import styles from "./RunDetailPage.module.css";

/** Format ISO timestamp as a localised string. */
function formatStarted(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function durationSeconds(run: RunDetail): number | null {
  if (!run.ended_at) return null;
  const start = Date.parse(run.started_at);
  const end = Date.parse(run.ended_at);
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return Math.max(0, (end - start) / 1000);
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds - m * 60);
  return `${m}m ${s}s`;
}

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const { data, isLoading, isError, error } = useRunDetail(runId);
  // Slice G — the SPA learns the absolute repo root via the backend's
  // integrations/paths endpoint so we can hand it to <OpenInVSCode>.
  const { data: paths } = useIntegrationsPaths();

  if (isLoading) {
    return (
      <section className={styles.page}>
        <p className={styles.empty}>Loading…</p>
      </section>
    );
  }

  if (isError || !data) {
    return (
      <section className={styles.page}>
        <div className={styles.error} role="alert">
          Failed to load run {runId}: {String((error as Error)?.message ?? "not found")}
        </div>
      </section>
    );
  }

  const dur = durationSeconds(data);

  return (
    <section className={styles.page} data-testid="run-detail-page">
      <nav className={styles.breadcrumbs} aria-label="Breadcrumb">
        <Link to="/runs" className={styles.breadcrumbLink}>
          ← All runs
        </Link>
      </nav>

      <header className={styles.header}>
        <h1 className={styles.title}>
          <StatusIcon status={data.status} />
          <span>{data.run_id}</span>
        </h1>
        <div className={styles.meta}>
          <span className={styles.metaItem}>
            target: <code>{data.target_slug ?? "—"}</code>
          </span>
          {data.branch_name ? (
            <span className={styles.metaItem}>
              branch: <code>{data.branch_name}</code>
            </span>
          ) : null}
          <span className={styles.metaItem}>
            started: {formatStarted(data.started_at)}
          </span>
          <span className={styles.metaItem}>
            duration: {formatDuration(dur)}
          </span>
          <span className={styles.metaItem}>
            cost: ${data.cost_usd_total.toFixed(2)}
          </span>
        </div>
        <div className={styles.actions} role="toolbar" aria-label="Run actions">
          {paths ? (
            <OpenInVSCode
              path={paths.repo_root}
              label="VSCode で開く"
              variant="button"
            />
          ) : null}
          <button
            type="button"
            className={styles.actionButton}
            disabled
            title="v1 で実装"
            aria-disabled="true"
          >
            Stop
          </button>
          <button
            type="button"
            className={styles.actionButton}
            disabled
            title="v1 で実装"
            aria-disabled="true"
          >
            Re-run failed phases
          </button>
          <button
            type="button"
            className={styles.actionButton}
            disabled
            title="v1 で実装"
            aria-disabled="true"
          >
            Open in GitHub
          </button>
        </div>
      </header>

      <div className={styles.phases}>
        {data.phases.length === 0 ? (
          <p className={styles.empty}>No phases recorded for this run.</p>
        ) : (
          data.phases.map((phase) => (
            <PhaseRow
              key={phase.phase_id}
              phase={phase}
              logsPath={paths ? `${paths.repo_root}/outputs/logs` : null}
            />
          ))
        )}
      </div>
    </section>
  );
}

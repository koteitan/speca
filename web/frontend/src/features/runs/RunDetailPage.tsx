import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { OpenInVSCode } from "@/components/OpenInVSCode";
import { useIntegrationsPaths } from "@/features/integrations/useIntegrationsStatus";
import { ApiError } from "@/lib/api";
import { useT } from "@/i18n/useT";

import { BudgetGauge } from "./BudgetGauge";
import { PhaseRow } from "./PhaseRow";
import { RerunDialog } from "./RerunDialog";
import { StatusIcon } from "./StatusIcon";
import type { RunDetail } from "./types";
import { useCancelRun, useRerunPhases } from "./useRunActions";
import { useRunDetail } from "./useRuns";
import { useRunStream } from "./useRunStream";
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

/**
 * Format an `ApiError` body for the error bar. We mirror Slice S1's
 * approach: try to lift `detail.message` / `detail.error` out of a
 * FastAPI structured envelope so the bar is readable, then fall back to
 * the raw body / HTTP status if the envelope is unparseable. Returning
 * a plain string keeps the page free of envelope-specific JSX.
 */
function formatActionError(err: unknown): string {
  if (err instanceof ApiError) {
    try {
      const parsed = JSON.parse(err.body) as {
        detail?: { error?: string; message?: string } | string;
      };
      const detail = parsed.detail;
      if (detail && typeof detail === "object") {
        if (detail.message) return detail.message;
        if (detail.error) return detail.error;
      }
      if (typeof detail === "string") return detail;
    } catch {
      // Body wasn't JSON — fall through to the raw envelope.
    }
    return err.body || `HTTP ${err.status}`;
  }
  if (err instanceof Error) return err.message;
  return String(err);
}

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const { data, isLoading, isError, error } = useRunDetail(runId);
  // Slice G — the SPA learns the absolute repo root via the backend's
  // integrations/paths endpoint so we can hand it to <OpenInVSCode>.
  const { data: paths } = useIntegrationsPaths();
  const t = useT();

  // Slice D1 — only subscribe to the live stream while the run is
  // flagged as `running`. For terminal runs we keep the v0 REST-only
  // behaviour so we don't burn a socket just to render a snapshot.
  const isLive = data?.status === "running";
  const stream = useRunStream(runId, { enabled: Boolean(isLive) });

  // Slice D2 — write actions. Mutations live above the dialog so we can
  // also gate the buttons on `isPending` (prevents double-submit while
  // the supervisor is still acknowledging the first POST).
  const cancelMutation = useCancelRun(runId);
  const rerunMutation = useRerunPhases(runId);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [rerunDialogOpen, setRerunDialogOpen] = useState(false);

  // Whether any phase is in a state Re-run actually targets. The button
  // text reads "Re-run failed phases", so we keep it disabled when
  // nothing failed/cancelled — opening the dialog with zero pre-checked
  // items is confusing. This matches the explicit `!hasFailedOrCancelledPhase`
  // guard from the slice spec.
  const hasFailedOrCancelledPhase = useMemo(
    () =>
      (data?.phases ?? []).some(
        (p) => p.status === "failed" || p.status === "cancelled",
      ),
    [data?.phases],
  );

  if (isLoading) {
    return (
      <section className={styles.page}>
        <p className={styles.empty}>{t("runs.detail.loading")}</p>
      </section>
    );
  }

  if (isError || !data) {
    return (
      <section className={styles.page}>
        <div className={styles.error} role="alert">
          {t("runs.detail.load_failed", {
            runId: runId ?? "",
            error: String(
              (error as Error)?.message ?? t("runs.detail.not_found"),
            ),
          })}
        </div>
      </section>
    );
  }

  const dur = durationSeconds(data);

  return (
    <section className={styles.page} data-testid="run-detail-page">
      <nav
        className={styles.breadcrumbs}
        aria-label={t("runs.detail.breadcrumb_aria")}
      >
        <Link to="/runs" className={styles.breadcrumbLink}>
          {t("runs.detail.breadcrumb_back")}
        </Link>
      </nav>

      <header className={styles.header}>
        <h1 className={styles.title}>
          <StatusIcon status={data.status} />
          <span>{data.run_id}</span>
        </h1>
        <div className={styles.meta}>
          <span className={styles.metaItem}>
            {t("runs.detail.meta_target")}{" "}
            <code>{data.target_slug ?? t("common.none")}</code>
          </span>
          {data.branch_name ? (
            <span className={styles.metaItem}>
              {t("runs.detail.meta_branch")} <code>{data.branch_name}</code>
            </span>
          ) : null}
          <span className={styles.metaItem}>
            {t("runs.detail.meta_started")} {formatStarted(data.started_at)}
          </span>
          <span className={styles.metaItem}>
            {t("runs.detail.meta_duration")} {formatDuration(dur)}
          </span>
          <span className={styles.metaItem}>
            {t("runs.detail.meta_cost")} ${data.cost_usd_total.toFixed(2)}
          </span>
          {/* Slice D3 — Budget gauge mirroring CLI spec §5.3.3. The
           * RunDetail payload does not yet carry `max_budget_usd` (it
           * lives on the spec side, not the run snapshot), so we pass
           * `cap={null}` for now. A follow-up PR will surface the cap
           * once it is threaded into RunDetail. */}
          <span className={styles.metaItem}>
            <BudgetGauge spent={data.cost_usd_total} cap={null} />
          </span>
          {isLive ? (
            <span
              className={styles.metaItem}
              data-testid="run-live-badge"
              aria-live="polite"
              aria-label={t("runs.detail.live_badge_aria")}
            >
              <span
                className={`${styles.liveBadge} ${
                  stream.givenUp
                    ? styles.liveBadgeError
                    : stream.connected
                      ? styles.liveBadgeOk
                      : styles.liveBadgeWarn
                }`}
              >
                {stream.givenUp
                  ? t("runs.detail.live.disconnected")
                  : stream.connected
                    ? t("runs.detail.live.connected")
                    : t("runs.detail.live.reconnecting", {
                        n: stream.reconnectAttempt || 1,
                      })}
              </span>
            </span>
          ) : null}
          {isLive && stream.droppedCount > 0 ? (
            <span
              className={styles.metaItem}
              title={t("runs.detail.logs_dropped_title")}
            >
              {t("runs.detail.live.logs_dropped", { n: stream.droppedCount })}
            </span>
          ) : null}
        </div>
        <div
          className={styles.actions}
          role="toolbar"
          aria-label={t("runs.detail.actions_aria")}
        >
          {paths ? (
            <OpenInVSCode
              path={paths.repo_root}
              label={t("runs.detail.open_vscode_label")}
              variant="button"
            />
          ) : null}
          <button
            type="button"
            className={styles.actionButton}
            onClick={() => setCancelDialogOpen(true)}
            disabled={data.status !== "running" || cancelMutation.isPending}
            data-testid="run-detail-stop"
          >
            {cancelMutation.isPending
              ? t("runs.detail.cancel.in_progress")
              : t("runs.detail.actions.stop")}
          </button>
          <button
            type="button"
            className={styles.actionButton}
            onClick={() => setRerunDialogOpen(true)}
            disabled={
              data.status === "running" ||
              rerunMutation.isPending ||
              !hasFailedOrCancelledPhase
            }
            data-testid="run-detail-rerun"
          >
            {rerunMutation.isPending
              ? t("runs.detail.rerun.in_progress")
              : t("runs.detail.actions.rerun_failed")}
          </button>
          <button
            type="button"
            className={styles.actionButton}
            disabled
            title={t("runs.detail.open_github_title")}
            aria-disabled="true"
          >
            {t("runs.detail.open_github_label")}
          </button>
        </div>
      </header>

      {cancelMutation.isError ? (
        <div
          className={styles.error}
          role="alert"
          data-testid="run-detail-cancel-error"
        >
          {formatActionError(cancelMutation.error)}
        </div>
      ) : null}
      {rerunMutation.isError ? (
        <div
          className={styles.error}
          role="alert"
          data-testid="run-detail-rerun-error"
        >
          {formatActionError(rerunMutation.error)}
        </div>
      ) : null}

      <div className={styles.phases}>
        {data.phases.length === 0 ? (
          <p className={styles.empty}>{t("runs.detail.phases_empty")}</p>
        ) : (
          data.phases.map((phase) => (
            <PhaseRow
              key={phase.phase_id}
              phase={phase}
              logsPath={paths ? `${paths.repo_root}/outputs/logs` : null}
              logs={isLive ? stream.logsByPhase[phase.phase_id] : undefined}
              isLive={Boolean(isLive)}
            />
          ))
        )}
      </div>

      <ConfirmDialog
        open={cancelDialogOpen}
        title={t("runs.detail.cancel.confirm.title")}
        description={t("runs.detail.cancel.confirm.description")}
        destructive
        onConfirm={() => {
          setCancelDialogOpen(false);
          cancelMutation.mutate();
        }}
        onCancel={() => setCancelDialogOpen(false)}
      />
      <RerunDialog
        open={rerunDialogOpen}
        phases={data.phases}
        onConfirm={(selected) => {
          setRerunDialogOpen(false);
          rerunMutation.mutate({ phases: selected, force: true });
        }}
        onCancel={() => setRerunDialogOpen(false)}
      />
    </section>
  );
}

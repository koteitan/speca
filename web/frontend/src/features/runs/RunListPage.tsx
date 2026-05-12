import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { OpenInVSCode } from "@/components/OpenInVSCode";
import { useIntegrationsPaths } from "@/features/integrations/useIntegrationsStatus";

import type { RunStatus, RunSummary } from "./types";
import { StatusIcon } from "./StatusIcon";
import { useRunList } from "./useRuns";
import styles from "./RunListPage.module.css";

// All run statuses we want to expose as filter chips, in display order.
// The "all" pseudo-status is handled by toggling the active chip off,
// not by a dedicated state — keeps the reducer trivial.
const STATUS_CHIPS: RunStatus[] = ["ok", "running", "failed", "cancelled"];

// Columns we let the user sort by. The actual sort keys are baked into
// the comparator below so this list only drives the header rendering.
type SortKey = "started_at" | "target_slug" | "status" | "cost_usd_total";

interface SortState {
  key: SortKey;
  /** `desc` is the most useful default (newest/biggest first). */
  direction: "asc" | "desc";
}

const DEFAULT_SORT: SortState = { key: "started_at", direction: "desc" };

/** Format the relative time as a short "5m ago" style string. */
function formatRelative(iso: string, now: number = Date.now()): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const delta = Math.max(0, now - t);
  const seconds = Math.floor(delta / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/**
 * Compute `ended - started` in seconds. Returns `null` if either
 * timestamp is missing/unparseable — the UI then renders an em-dash.
 */
function durationSeconds(run: RunSummary): number | null {
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

function formatCost(usd: number): string {
  return `$${usd.toFixed(2)}`;
}

/** Compare two RunSummary rows by the active sort column. */
function compareRuns(a: RunSummary, b: RunSummary, sort: SortState): number {
  const sign = sort.direction === "asc" ? 1 : -1;
  switch (sort.key) {
    case "started_at":
      return sign * (Date.parse(a.started_at) - Date.parse(b.started_at));
    case "target_slug":
      return sign * (a.target_slug ?? "").localeCompare(b.target_slug ?? "");
    case "status":
      return sign * a.status.localeCompare(b.status);
    case "cost_usd_total":
      return sign * (a.cost_usd_total - b.cost_usd_total);
    default:
      return 0;
  }
}

export default function RunListPage() {
  const { data, isLoading, isError, error } = useRunList();
  // Slice G — repo root drives the per-row "Open in VSCode" icon.
  const { data: paths } = useIntegrationsPaths();
  const [statusFilter, setStatusFilter] = useState<RunStatus | null>(null);
  const [targetQuery, setTargetQuery] = useState("");
  const [sort, setSort] = useState<SortState>(DEFAULT_SORT);

  const rows = useMemo(() => {
    const all = data ?? [];
    const filtered = all.filter((run) => {
      if (statusFilter && run.status !== statusFilter) return false;
      if (targetQuery.trim()) {
        const needle = targetQuery.trim().toLowerCase();
        const haystack = `${run.target_slug ?? ""} ${run.run_id}`.toLowerCase();
        if (!haystack.includes(needle)) return false;
      }
      return true;
    });
    return [...filtered].sort((a, b) => compareRuns(a, b, sort));
  }, [data, statusFilter, targetQuery, sort]);

  const toggleSort = (key: SortKey) => {
    setSort((prev) => {
      if (prev.key !== key) return { key, direction: "desc" };
      return {
        key,
        direction: prev.direction === "desc" ? "asc" : "desc",
      };
    });
  };

  const indicator = (key: SortKey) =>
    sort.key === key ? (sort.direction === "desc" ? " ↓" : " ↑") : "";

  return (
    <section className={styles.page} data-testid="run-list-page">
      <header className={styles.header}>
        <h1 className={styles.title}>Runs</h1>
        <button
          type="button"
          className={styles.newRunButton}
          disabled
          title="v1 で実装"
          aria-disabled="true"
        >
          + New run
        </button>
      </header>

      <div className={styles.filters} role="toolbar" aria-label="Filters">
        {STATUS_CHIPS.map((status) => {
          const active = statusFilter === status;
          return (
            <button
              key={status}
              type="button"
              className={`${styles.chip} ${active ? styles.chipActive : ""}`}
              aria-pressed={active}
              onClick={() =>
                setStatusFilter((prev) => (prev === status ? null : status))
              }
            >
              <StatusIcon status={status} /> {status}
            </button>
          );
        })}
        <input
          type="search"
          className={styles.searchInput}
          placeholder="Filter by target / run id"
          value={targetQuery}
          onChange={(e) => setTargetQuery(e.target.value)}
          aria-label="Filter by target"
        />
      </div>

      {isLoading ? (
        <p className={styles.muted}>Loading…</p>
      ) : isError ? (
        <div className={styles.error} role="alert">
          Failed to load runs: {String((error as Error)?.message ?? "unknown error")}
        </div>
      ) : rows.length === 0 ? (
        <div className={styles.empty}>
          <p>
            新規 audit はまだありません。
            <br />
            <code>uv run python3 scripts/run_phase.py ...</code> で 1 件作るか、v1 で UI から起動可能。
          </p>
        </div>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col" onClick={() => toggleSort("status")}>
                Status{indicator("status")}
              </th>
              <th scope="col">Run</th>
              <th scope="col" onClick={() => toggleSort("target_slug")}>
                Target{indicator("target_slug")}
              </th>
              <th scope="col" onClick={() => toggleSort("started_at")}>
                Started{indicator("started_at")}
              </th>
              <th scope="col">Duration</th>
              <th scope="col" onClick={() => toggleSort("cost_usd_total")}>
                Cost{indicator("cost_usd_total")}
              </th>
              {/* Slice G: per-row "Open in VSCode" icon. Header left blank
                  on purpose so the column reads as an action affordance. */}
              <th scope="col" aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {rows.map((run) => {
              const dur = durationSeconds(run);
              return (
                <tr key={run.run_id} data-testid={`run-row-${run.run_id}`}>
                  <td>
                    <StatusIcon status={run.status} />
                  </td>
                  <td>
                    <Link className={styles.runLink} to={`/runs/${run.run_id}`}>
                      {run.run_id}
                    </Link>
                  </td>
                  <td>{run.target_slug ?? "—"}</td>
                  <td className={styles.muted}>
                    {formatRelative(run.started_at)}
                  </td>
                  <td className={styles.muted}>{formatDuration(dur)}</td>
                  <td className={styles.muted}>{formatCost(run.cost_usd_total)}</td>
                  <td className={styles.actionCell}>
                    {paths ? (
                      <OpenInVSCode
                        path={paths.repo_root}
                        label="VSCode でリポジトリを開く"
                        variant="icon"
                      />
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}

// FindingsListPage — `/runs/<runId>/findings`.
//
// Three sections, top to bottom:
//   1. Banner explaining `data_source: current_outputs` (v0 caveat)
//   2. FilterBar — severity/verdict/phase chips, URL-synced
//   3. Sortable table — five columns, click-sortable headers
//
// Sort is local because the server returns a small dataset (<1k rows in
// the litecoin sample). The default is severity-ascending; clicking the
// same header toggles direction. We deliberately do NOT persist the sort
// to the URL — it's a workspace concern, not a shareable filter.

import { useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { useIntegrationsPaths } from "@/features/integrations/useIntegrationsStatus";

import { FilterBar } from "./FilterBar";
import { FindingRow } from "./FindingRow";
import { useFindings } from "./useFindings";
import styles from "./FindingsListPage.module.css";

import {
  SEVERITY_RANK,
  type Finding,
  type FindingQuery,
  type Phase,
  type Severity,
} from "./types";

type SortKey = "severity" | "property_id" | "verdict" | "file" | "phase";
type SortDir = "asc" | "desc";

interface SortState {
  key: SortKey;
  dir: SortDir;
}

const HEADERS: { key: SortKey; label: string; className: string }[] = [
  { key: "severity", label: "Severity", className: "severityCol" },
  { key: "property_id", label: "Property ID", className: "idCol" },
  { key: "verdict", label: "Verdict", className: "verdictCol" },
  { key: "file", label: "File", className: "fileCol" },
  { key: "phase", label: "Phase", className: "phaseCol" },
];

function compare(a: Finding, b: Finding, key: SortKey, dir: SortDir): number {
  let cmp = 0;
  switch (key) {
    case "severity":
      cmp = SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity];
      break;
    case "property_id":
      cmp = a.property_id.localeCompare(b.property_id);
      break;
    case "verdict":
      cmp = (a.verdict ?? "").localeCompare(b.verdict ?? "");
      break;
    case "file":
      cmp = (a.file ?? "").localeCompare(b.file ?? "");
      break;
    case "phase":
      cmp = a.phase.localeCompare(b.phase);
      break;
  }
  // Stable tie-break by property_id so two findings with the same severity
  // don't bounce around as the user toggles other columns.
  if (cmp === 0 && key !== "property_id") {
    cmp = a.property_id.localeCompare(b.property_id);
  }
  return dir === "asc" ? cmp : -cmp;
}

export function FindingsListPage() {
  const { runId } = useParams<{ runId: string }>();
  const [searchParams] = useSearchParams();
  const [sort, setSort] = useState<SortState>({ key: "severity", dir: "asc" });

  const query: FindingQuery = useMemo(() => {
    const sev = searchParams.get("severity");
    const verd = searchParams.get("verdict");
    const ph = searchParams.get("phase");
    return {
      severity: (sev ?? undefined) as Severity | undefined,
      verdict: verd ?? undefined,
      phase: (ph ?? undefined) as Phase | undefined,
    };
  }, [searchParams]);

  const { data, error, isLoading } = useFindings(runId, query);
  // Slice G — threaded down into FindingRow so each row can render an
  // "Open in VSCode" icon pointing at <repo>/target_workspace/<file>.
  const { data: paths } = useIntegrationsPaths();

  const sortedFindings = useMemo(() => {
    if (!data) return [];
    const copy = [...data.data];
    copy.sort((a, b) => compare(a, b, sort.key, sort.dir));
    return copy;
  }, [data, sort]);

  const handleSort = (key: SortKey) => {
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "asc" },
    );
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h2 className={styles.title}>Findings</h2>
        <p className={styles.runLabel}>
          Run <code>{runId ?? "—"}</code>
        </p>
      </header>

      {data && (
        <div className={styles.banner} role="status">
          <strong>Data source: current <code>outputs/</code> (v0).</strong>{" "}
          per-run 表示は v1 で対応。表示中の finding は {data.meta.count} 件。
        </div>
      )}

      <FilterBar />

      {isLoading && <div className={styles.state}>Loading findings…</div>}

      {error && (
        <div className={styles.error}>
          findings の取得に失敗しました: {error.message}
        </div>
      )}

      {!isLoading && !error && sortedFindings.length === 0 && (
        <div className={styles.empty}>
          この run に表示できる finding はありません。
          <code>outputs/</code> に <code>03_PARTIAL_*.json</code> /{" "}
          <code>04_PARTIAL_*.json</code> があるか確認してください。
        </div>
      )}

      {sortedFindings.length > 0 && (
        <div className={styles.table} role="table" aria-label="Findings">
          <div className={styles.thead} role="row">
            {HEADERS.map((h) => (
              <button
                key={h.key}
                type="button"
                role="columnheader"
                aria-sort={
                  sort.key === h.key
                    ? sort.dir === "asc"
                      ? "ascending"
                      : "descending"
                    : "none"
                }
                onClick={() => handleSort(h.key)}
                className={`${styles.th} ${styles[h.className]}`}
              >
                {h.label}
                {sort.key === h.key && (
                  <span className={styles.sortArrow}>
                    {sort.dir === "asc" ? "▲" : "▼"}
                  </span>
                )}
              </button>
            ))}
          </div>
          <div className={styles.tbody}>
            {sortedFindings.map((f) => (
              <FindingRow
                key={f.property_id}
                finding={f}
                runId={runId ?? ""}
                repoRoot={paths?.repo_root ?? null}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default FindingsListPage;

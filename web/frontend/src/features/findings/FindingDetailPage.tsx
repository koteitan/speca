// FindingDetailPage — `/runs/<runId>/findings/<propertyId>`.
//
// Layout:
//   1. Header: property_id + severity + verdict + phase
//   2. Code path row — IMPORTANT: keep the `data-testid="finding-code-path"`
//      on the file::line element so Slice G can locate it to attach
//      <OpenInVSCode>.
//   3. Sections: evidence_snippet, proof_trace, gates_passed (Phase 04),
//      reviewer_notes. Each section is hidden if its source field is empty.

import { useParams, Link } from "react-router-dom";

import { OpenInVSCode } from "@/components/OpenInVSCode";
import { useIntegrationsPaths } from "@/features/integrations/useIntegrationsStatus";

import { parseLineStart } from "./parseLineRange";
import { SeverityChip } from "./SeverityChip";
import { VerdictChip } from "./VerdictChip";
import { useFinding } from "./useFindings";
import styles from "./FindingDetailPage.module.css";

export function FindingDetailPage() {
  const { runId, propertyId } = useParams<{
    runId: string;
    propertyId: string;
  }>();
  const { data, error, isLoading } = useFinding(runId, propertyId);
  // Slice G — repo root is required to build the absolute path for the
  // "open in VSCode" icon next to the code location row.
  const { data: paths } = useIntegrationsPaths();

  if (isLoading) {
    return <div className={styles.state}>Loading finding…</div>;
  }
  if (error) {
    return (
      <div className={styles.error}>
        finding の取得に失敗しました: {error.message}
        <div className={styles.backLink}>
          <Link to={`/runs/${encodeURIComponent(runId ?? "")}/findings`}>
            ← findings 一覧へ戻る
          </Link>
        </div>
      </div>
    );
  }
  if (!data) {
    return <div className={styles.state}>finding が見つかりませんでした。</div>;
  }

  const codeLocation =
    data.file && data.line_range
      ? `${data.file}::${data.line_range}`
      : data.file ?? null;

  // VSCode wants an absolute path; we synthesise it from
  //   <repo_root>/target_workspace/<finding.file>
  // exactly as documented in UI_DESIGN.md §4.10.5. If target_workspace is
  // missing on disk the VSCode CLI is best-effort, which is fine for v0.
  const vscodeTargetPath =
    paths && data.file
      ? `${paths.repo_root}/target_workspace/${data.file}`
      : null;
  const vscodeLine = parseLineStart(data.line_range);

  return (
    <article className={styles.page}>
      <div className={styles.backLink}>
        <Link to={`/runs/${encodeURIComponent(runId ?? "")}/findings`}>
          ← findings 一覧へ戻る
        </Link>
      </div>

      <header className={styles.header}>
        <h2 className={styles.title}>
          <code>{data.property_id}</code>
        </h2>
        <div className={styles.chipRow}>
          <SeverityChip severity={data.severity} />
          <VerdictChip verdict={data.verdict} />
          <span className={styles.phaseTag}>Phase {data.phase}</span>
        </div>
      </header>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Code location</h3>
        {codeLocation ? (
          <div className={styles.codePathRow}>
            <div
              className={styles.codePath}
              data-testid="finding-code-path"
              data-file={data.file ?? ""}
              data-line-range={data.line_range ?? ""}
            >
              <code>{codeLocation}</code>
            </div>
            {vscodeTargetPath ? (
              <OpenInVSCode
                path={vscodeTargetPath}
                line={vscodeLine ?? undefined}
                label="VSCode で開く"
                variant="icon"
              />
            ) : null}
          </div>
        ) : (
          <div className={styles.empty}>
            (location not resolved for this finding)
          </div>
        )}
      </section>

      {data.evidence_snippet && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Evidence snippet</h3>
          <pre className={styles.snippet}>{data.evidence_snippet}</pre>
        </section>
      )}

      {data.proof_trace && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Proof trace</h3>
          <pre className={styles.preserve}>{data.proof_trace}</pre>
        </section>
      )}

      {data.phase === "04" && data.gates_passed.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Gates passed</h3>
          <ul className={styles.gates}>
            {data.gates_passed.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </section>
      )}

      {data.reviewer_notes && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Reviewer notes</h3>
          <pre className={styles.preserve}>{data.reviewer_notes}</pre>
        </section>
      )}
    </article>
  );
}

export default FindingDetailPage;

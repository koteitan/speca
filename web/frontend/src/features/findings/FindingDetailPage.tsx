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
import { useT } from "@/i18n/useT";

import { parseLineStart } from "./parseLineRange";
import { SeverityChip } from "./SeverityChip";
import { VerdictChip } from "./VerdictChip";
import { useFinding } from "./useFindings";
import styles from "./FindingDetailPage.module.css";

export function FindingDetailPage() {
  const t = useT();
  const { runId, propertyId } = useParams<{
    runId: string;
    propertyId: string;
  }>();
  const { data, error, isLoading } = useFinding(runId, propertyId);
  // Slice G — repo root is required to build the absolute path for the
  // "open in VSCode" icon next to the code location row.
  const { data: paths } = useIntegrationsPaths();

  if (isLoading) {
    return <div className={styles.state}>{t("findings.detail.loading")}</div>;
  }
  if (error) {
    return (
      <div className={styles.error}>
        {t("findings.detail.load_failed", { error: error.message })}
        <div className={styles.backLink}>
          <Link to={`/runs/${encodeURIComponent(runId ?? "")}/findings`}>
            {t("findings.detail.back_link")}
          </Link>
        </div>
      </div>
    );
  }
  if (!data) {
    return <div className={styles.state}>{t("findings.detail.not_found")}</div>;
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
          {t("findings.detail.back_link")}
        </Link>
      </div>

      <header className={styles.header}>
        <h2 className={styles.title}>
          <code>{data.property_id}</code>
        </h2>
        <div className={styles.chipRow}>
          <SeverityChip severity={data.severity} />
          <VerdictChip verdict={data.verdict} />
          <span className={styles.phaseTag}>
            {t("findings.detail.phase_label", { phase: data.phase })}
          </span>
        </div>
      </header>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>
          {t("findings.detail.code_location_title")}
        </h3>
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
                label={t("findings.detail.open_in_vscode")}
                variant="icon"
              />
            ) : null}
          </div>
        ) : (
          <div className={styles.empty}>
            {t("findings.detail.code_location_unresolved")}
          </div>
        )}
      </section>

      {data.evidence_snippet && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>
            {t("findings.detail.evidence_snippet_title")}
          </h3>
          <pre className={styles.snippet}>{data.evidence_snippet}</pre>
        </section>
      )}

      {data.proof_trace && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>
            {t("findings.detail.proof_trace_title")}
          </h3>
          <pre className={styles.preserve}>{data.proof_trace}</pre>
        </section>
      )}

      {data.phase === "04" && data.gates_passed.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>
            {t("findings.detail.gates_passed_title")}
          </h3>
          <ul className={styles.gates}>
            {data.gates_passed.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </section>
      )}

      {data.reviewer_notes && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>
            {t("findings.detail.reviewer_notes_title")}
          </h3>
          <pre className={styles.preserve}>{data.reviewer_notes}</pre>
        </section>
      )}
    </article>
  );
}

export default FindingDetailPage;

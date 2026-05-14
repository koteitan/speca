// DiagnosticsPage — `/diagnostics`.
//
// Web-UI counterpart of `speca doctor` (see docs/SPECA_CLI_SPEC.md §6 /
// §11 M1). Renders one chip per tool with status OK / MISSING / OUTDATED
// / UNKNOWN. When every probe is green, surface a primary CTA into the
// new-audit flow. When something is missing, render an inline install
// hint so the user can copy a command without leaving the page.
//
// Section ordering deliberately groups the *runtime* tools (Node / uv /
// git) first, then the *Claude / GitHub* integrations (claude / gh /
// code), then auth state. This matches how a first-run user encounters
// each requirement in the CLI spec.

import { useMemo, type ReactElement, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useT } from "@/i18n/useT";

import styles from "./DiagnosticsPage.module.css";
import type { DiagnosticsReport, ToolStatus, ToolStatusValue } from "./types";
import { useDiagnostics, useInvalidateDiagnostics } from "./useDiagnostics";

// Friendly install commands for each tool. We deliberately ship them as
// static strings so the SPA does not need to call a separate endpoint
// just to render the hint — the canonical reference lives in the CLI
// spec §6/§10 and is rarely revised.
const INSTALL_HINTS: Record<string, { command: string; url?: string }> = {
  node: {
    command: "winget install OpenJS.NodeJS.LTS  # or: nvm install --lts",
    url: "https://nodejs.org/",
  },
  uv: {
    command:
      'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"',
    url: "https://docs.astral.sh/uv/",
  },
  git: {
    command: "winget install Git.Git  # or: brew install git",
    url: "https://git-scm.com/",
  },
  claude: {
    command: "npm install -g @anthropic-ai/claude-code",
    url: "https://docs.claude.com/en/docs/claude-code",
  },
  gh: {
    command: "winget install GitHub.cli  # or: brew install gh",
    url: "https://cli.github.com/",
  },
  code: {
    command:
      "Install VSCode, then run `Shell Command: Install 'code' command in PATH` from the command palette.",
    url: "https://code.visualstudio.com/",
  },
};

const TOOL_ORDER: ReadonlyArray<keyof DiagnosticsReport> = [
  "node",
  "uv",
  "git",
  "claude",
  "gh",
  "code",
];

function chipClass(status: ToolStatusValue): string {
  switch (status) {
    case "ok":
      return styles.chipOk;
    case "missing":
      return styles.chipMissing;
    case "outdated":
      return styles.chipOutdated;
    case "unknown":
    default:
      return styles.chipUnknown;
  }
}

function Chip({ status }: { status: ToolStatusValue }): ReactElement {
  const t = useT();
  const label =
    status === "ok"
      ? t("diagnostics.status.ok")
      : status === "missing"
        ? t("diagnostics.status.missing")
        : status === "outdated"
          ? t("diagnostics.status.outdated")
          : t("diagnostics.status.unknown");

  return (
    <span
      className={`${styles.chip} ${chipClass(status)}`}
      data-testid={`diagnostics-chip-${status}`}
      aria-label={label}
    >
      {label}
    </span>
  );
}

function ToolRow({
  toolKey,
  status,
}: {
  toolKey: string;
  status: ToolStatus;
}): ReactElement {
  const t = useT();
  // `meta` carries the small grey sub-line next to the chip. Examples:
  //   - "v22.4.1 (min 20.0.0)"
  //   - "not installed"
  //   - "installed, login required"
  let meta: ReactNode = null;
  if (!status.installed) {
    meta = t("diagnostics.meta.not_installed");
  } else if (status.status === "outdated") {
    const min =
      typeof status.details?.min_version === "string"
        ? (status.details.min_version as string)
        : "";
    meta = (
      <>
        {status.version ? <code>{status.version}</code> : null}
        {min ? <> · {t("diagnostics.meta.min_required", { version: min })}</> : null}
      </>
    );
  } else if (status.status === "unknown") {
    meta = t("diagnostics.meta.version_unknown");
  } else if (status.version) {
    meta = <code>{status.version}</code>;
    // For `gh`, additionally surface auth state
    if (toolKey === "gh") {
      const authed = status.details?.authed;
      if (authed === false) {
        meta = (
          <>
            <code>{status.version}</code> · {t("diagnostics.meta.gh_unauthed")}
          </>
        );
      } else if (authed === true) {
        meta = (
          <>
            <code>{status.version}</code> · {t("diagnostics.meta.gh_authed")}
          </>
        );
      }
    }
  }

  return (
    <li className={styles.row} data-testid={`diagnostics-row-${toolKey}`}>
      <span className={styles.toolName}>
        {t(`diagnostics.tool.${toolKey}`)}
      </span>
      <span className={styles.toolMeta}>{meta}</span>
      <Chip status={status.status} />
    </li>
  );
}

function AuthRow({
  report,
}: {
  report: DiagnosticsReport;
}): ReactElement {
  const t = useT();
  const ok = report.auth.logged_in || report.api_key_configured;
  const status: ToolStatusValue = ok ? "ok" : "missing";

  const meta = report.auth.logged_in
    ? report.auth.method === "oauth"
      ? t("diagnostics.auth.method_oauth")
      : t("diagnostics.auth.method_api_key")
    : report.api_key_configured
      ? t("diagnostics.auth.env_api_key")
      : t("diagnostics.auth.none");

  return (
    <li className={styles.row} data-testid="diagnostics-row-auth">
      <span className={styles.toolName}>{t("diagnostics.tool.auth")}</span>
      <span className={styles.toolMeta}>{meta}</span>
      <Chip status={status} />
    </li>
  );
}

function InstallHints({
  report,
}: {
  report: DiagnosticsReport;
}): ReactElement | null {
  const t = useT();
  const missing = useMemo(
    () =>
      TOOL_ORDER.filter((key) => {
        const tool = report[key];
        if (!tool || typeof tool !== "object" || !("status" in tool)) return false;
        return (tool as ToolStatus).status !== "ok";
      }),
    [report],
  );

  if (missing.length === 0) return null;

  return (
    <section
      className={styles.section}
      data-testid="diagnostics-install-hints"
      aria-label={t("diagnostics.install.section_title")}
    >
      <h2 className={styles.sectionTitle}>
        {t("diagnostics.install.section_title")}
      </h2>
      <p className={styles.sectionHint}>{t("diagnostics.install.hint")}</p>
      <div className={styles.installHints}>
        {missing.map((key) => {
          const hint = INSTALL_HINTS[key as string];
          if (!hint) return null;
          return (
            <div
              key={key as string}
              className={styles.installHint}
              data-testid={`diagnostics-install-${key as string}`}
            >
              <span className={styles.installHintTool}>
                {t(`diagnostics.tool.${key as string}`)}
              </span>
              <code className={styles.installCommand}>{hint.command}</code>
              {hint.url ? (
                <a
                  className={styles.installLink}
                  href={hint.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("diagnostics.install.docs_link")} →
                </a>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Summary({
  report,
}: {
  report: DiagnosticsReport;
}): ReactElement {
  const t = useT();
  const toolsAllOk = TOOL_ORDER.every(
    (key) => (report[key] as ToolStatus).status === "ok",
  );
  const authOk = report.auth.logged_in || report.api_key_configured;
  const allOk = toolsAllOk && authOk;

  return (
    <div
      className={`${styles.summary} ${
        allOk ? styles.summaryOk : styles.summaryAttention
      }`}
      data-testid="diagnostics-summary"
    >
      <h2 className={styles.summaryHeadline}>
        {allOk
          ? t("diagnostics.summary.all_ok_title")
          : t("diagnostics.summary.attention_title")}
      </h2>
      <p className={styles.summaryHint}>
        {allOk
          ? t("diagnostics.summary.all_ok_hint")
          : t("diagnostics.summary.attention_hint")}
      </p>
      <div className={styles.summaryActions}>
        {allOk ? (
          <Link
            to="/runs/new"
            className={styles.primaryLink}
            data-testid="diagnostics-cta-new-run"
          >
            {t("diagnostics.summary.cta_new_run")}
          </Link>
        ) : null}
      </div>
    </div>
  );
}

export function DiagnosticsPage(): ReactElement {
  const t = useT();
  const { data, isPending, isError, error, isFetching } = useDiagnostics();
  const invalidate = useInvalidateDiagnostics();

  return (
    <section className={styles.page} data-testid="diagnostics-page">
      <header className={styles.header}>
        <h1 className={styles.title}>{t("diagnostics.page.title")}</h1>
        <p className={styles.subtitle}>{t("diagnostics.page.subtitle")}</p>
      </header>

      {isPending ? (
        <p className={styles.muted}>{t("diagnostics.loading")}</p>
      ) : isError || !data ? (
        <div className={styles.error}>
          {t("diagnostics.load_failed", {
            error: error?.message ?? "unknown",
          })}
        </div>
      ) : (
        <>
          <Summary report={data} />

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>
              {t("diagnostics.section.environment")}
            </h2>
            <ul className={styles.list}>
              {TOOL_ORDER.map((key) => (
                <ToolRow
                  key={key as string}
                  toolKey={key as string}
                  status={data[key] as ToolStatus}
                />
              ))}
              <AuthRow report={data} />
            </ul>
          </section>

          <InstallHints report={data} />

          <button
            type="button"
            className={styles.refreshButton}
            onClick={() => invalidate()}
            disabled={isFetching}
            data-testid="diagnostics-refresh"
          >
            {isFetching
              ? t("diagnostics.refresh_in_progress")
              : t("diagnostics.refresh")}
          </button>
        </>
      )}
    </section>
  );
}

export default DiagnosticsPage;

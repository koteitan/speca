// WizardPage — step-by-step "guided" mode for `New audit` setup.
//
// Mirrors `speca init` (SPECA_CLI_SPEC §3.1 / §11 M2): one question per
// screen, with a back-button trail. The wizard writes into the same
// shared NewRunDraft slice that the raw NewRunForm uses, so when the
// user reaches the final step they can either:
//   - launch directly from the wizard (no separate review screen), or
//   - bounce into the existing `/runs/new/review` form for advanced
//     tweaks (workers / max_concurrent / push_to_remote)
//
// Layout-wise this is *not* a modal — it lives at its own route
// (/runs/new/wizard) so the URL is shareable and the browser back
// button bisects step by step.

import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import ErrorModal from "@/components/ErrorModal/ErrorModal";
import { Spinner } from "@/components/Spinner/Spinner";
import { useT } from "@/i18n/useT";
import { parseErrorEnvelope } from "@/lib/errorEnvelope";
import { useNewRunDraft } from "@/store/newRunDraftSlice";

import type { LaunchSpec, ProjectType } from "./types";
import { useLaunchRun } from "./useLaunchRun";
import styles from "./WizardPage.module.css";

// Step ids — kept as a const tuple so TypeScript narrows the index type
// without us having to maintain a parallel enum.
const STEPS = [
  "project_type",
  "target_repo",
  "target_ref",
  "scope",
  "spec_urls",
  "review",
] as const;
type StepId = (typeof STEPS)[number];

const TARGET_REPO_RE = /^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/;

function buildLaunchSpec(
  draft: ReturnType<typeof useNewRunDraft.getState>,
): LaunchSpec {
  const opt = (v: string): string | undefined => {
    const trimmed = v.trim();
    return trimmed === "" ? undefined : trimmed;
  };
  return {
    project_type: draft.project_type,
    bug_bounty_url: opt(draft.bug_bounty_url),
    target_repo: draft.target_repo.trim(),
    target_ref: opt(draft.target_ref),
    contract_addresses: opt(draft.contract_addresses),
    spec_urls: opt(draft.spec_urls),
    keywords: opt(draft.keywords),
    workers: draft.workers,
    max_concurrent: draft.max_concurrent,
    push_to_remote: draft.push_to_remote,
  };
}

export default function WizardPage() {
  const t = useT();
  const navigate = useNavigate();
  const launch = useLaunchRun();

  // Each field subscribed individually so a patch from any step
  // re-renders only the visible step body, not the whole wizard.
  const project_type = useNewRunDraft((s) => s.project_type);
  const bug_bounty_url = useNewRunDraft((s) => s.bug_bounty_url);
  const target_repo = useNewRunDraft((s) => s.target_repo);
  const target_ref = useNewRunDraft((s) => s.target_ref);
  const contract_addresses = useNewRunDraft((s) => s.contract_addresses);
  const spec_urls = useNewRunDraft((s) => s.spec_urls);
  const patch = useNewRunDraft((s) => s.patch);
  const clearDraft = useNewRunDraft((s) => s.clear);

  const [stepIdx, setStepIdx] = useState(0);
  const [errorModalOpen, setErrorModalOpen] = useState(false);
  const errorEnvelope = useMemo(
    () => (launch.error ? parseErrorEnvelope(launch.error) : null),
    [launch.error],
  );
  const stepId: StepId = STEPS[stepIdx];

  const isContract = project_type === "smart_contract";

  // Per-step validity. The "Next" button mirrors this. We don't gate
  // on every optional field — only on what `LaunchSpec` actually needs.
  const validity = useMemo(() => {
    const repoOk = TARGET_REPO_RE.test(target_repo.trim());
    const urlOk =
      bug_bounty_url.trim() === "" ||
      (() => {
        try {
          const u = new URL(bug_bounty_url.trim());
          return u.protocol === "http:" || u.protocol === "https:";
        } catch {
          return false;
        }
      })();
    return {
      project_type: Boolean(project_type),
      target_repo: repoOk,
      target_ref: true,
      scope: urlOk,
      spec_urls: true,
      review: repoOk && urlOk,
    };
  }, [project_type, target_repo, bug_bounty_url]);

  const canAdvance = validity[stepId];

  const onLaunch = () => {
    if (!validity.review || launch.isPending) return;
    const spec = buildLaunchSpec(useNewRunDraft.getState());
    launch.mutate(spec, {
      onSuccess: (data) => {
        navigate(`/runs/${data.run_id}`);
        queueMicrotask(() => clearDraft());
      },
      onError: () => setErrorModalOpen(true),
    });
  };

  const next = () => {
    if (!canAdvance) return;
    if (stepIdx < STEPS.length - 1) setStepIdx(stepIdx + 1);
  };
  const back = () => {
    if (stepIdx > 0) setStepIdx(stepIdx - 1);
  };

  return (
    <section className={styles.page} data-testid="wizard-page">
      <header className={styles.header}>
        <Link to="/runs/new" className={styles.backLink}>
          {t("picker.wizard.cancel_link")}
        </Link>
        <h1 className={styles.title}>{t("picker.wizard.title")}</h1>
        <p className={styles.subtitle}>{t("picker.wizard.subtitle")}</p>
      </header>

      <ol className={styles.stepDots} aria-label={t("picker.wizard.steps_aria")}>
        {STEPS.map((id, idx) => (
          <li
            key={id}
            className={`${styles.stepDot} ${idx === stepIdx ? styles.stepDotActive : ""} ${
              idx < stepIdx ? styles.stepDotDone : ""
            }`}
            aria-current={idx === stepIdx ? "step" : undefined}
          >
            <span className={styles.stepDotIdx}>{idx + 1}</span>
            <span className={styles.stepDotLabel}>
              {t(`picker.wizard.step_${id}_short`)}
            </span>
          </li>
        ))}
      </ol>

      <div className={styles.card}>
        {stepId === "project_type" && (
          <fieldset className={styles.field}>
            <legend className={styles.question}>
              {t("picker.wizard.q_project_type")}
            </legend>
            <p className={styles.hint}>{t("picker.wizard.hint_project_type")}</p>
            <div className={styles.choiceRow}>
              {(["smart_contract", "web_app", "library", "other"] as ProjectType[]).map(
                (pt) => (
                  <label key={pt} className={styles.choice}>
                    <input
                      type="radio"
                      name="project_type"
                      value={pt}
                      checked={project_type === pt}
                      onChange={() => patch({ project_type: pt })}
                      data-testid={`wizard-pt-${pt}`}
                    />
                    <span>{t(`picker.new_run_form.project_type_${pt}`)}</span>
                  </label>
                ),
              )}
            </div>
          </fieldset>
        )}

        {stepId === "target_repo" && (
          <label className={styles.field}>
            <span className={styles.question}>
              {t("picker.wizard.q_target_repo")}
            </span>
            <p className={styles.hint}>{t("picker.wizard.hint_target_repo")}</p>
            <input
              type="text"
              className={styles.input}
              value={target_repo}
              onChange={(e) => patch({ target_repo: e.target.value })}
              placeholder="owner/repo"
              autoComplete="off"
              spellCheck={false}
              autoFocus
              data-testid="wizard-target-repo"
            />
            {target_repo.trim() !== "" && !validity.target_repo ? (
              <p className={styles.error}>
                {t("picker.new_run_form.error_invalid_target_repo")}
              </p>
            ) : null}
          </label>
        )}

        {stepId === "target_ref" && (
          <label className={styles.field}>
            <span className={styles.question}>
              {t("picker.wizard.q_target_ref")}
            </span>
            <p className={styles.hint}>{t("picker.wizard.hint_target_ref")}</p>
            <input
              type="text"
              className={styles.input}
              value={target_ref}
              onChange={(e) => patch({ target_ref: e.target.value })}
              placeholder={t("picker.new_run_form.label_target_ref_placeholder")}
              autoComplete="off"
              spellCheck={false}
              autoFocus
              data-testid="wizard-target-ref"
            />
          </label>
        )}

        {stepId === "scope" && (
          <div className={styles.field}>
            <span className={styles.question}>{t("picker.wizard.q_scope")}</span>
            <p className={styles.hint}>{t("picker.wizard.hint_scope")}</p>
            <label className={styles.subField}>
              <span className={styles.subLabel}>
                {t("picker.new_run_form.label_bug_bounty_url")}
                <span className={styles.optional}>
                  {" "}({t("picker.new_run_form.optional_suffix")})
                </span>
              </span>
              <input
                type="url"
                className={styles.input}
                value={bug_bounty_url}
                onChange={(e) => patch({ bug_bounty_url: e.target.value })}
                autoComplete="off"
                spellCheck={false}
                data-testid="wizard-bug-bounty-url"
              />
              {bug_bounty_url.trim() !== "" && !validity.scope ? (
                <p className={styles.error}>
                  {t("picker.new_run_form.error_invalid_url")}
                </p>
              ) : null}
            </label>
            <label className={styles.subField}>
              <span className={styles.subLabel}>
                {isContract
                  ? t("picker.new_run_form.label_contract_addresses")
                  : t("picker.new_run_form.label_in_scope_assets")}
              </span>
              <textarea
                className={styles.textarea}
                value={contract_addresses}
                onChange={(e) => patch({ contract_addresses: e.target.value })}
                rows={3}
                spellCheck={false}
                autoComplete="off"
                placeholder={
                  isContract
                    ? t("picker.new_run_form.placeholder_contract_addresses")
                    : t("picker.new_run_form.placeholder_in_scope_assets")
                }
                data-testid="wizard-contracts"
              />
            </label>
          </div>
        )}

        {stepId === "spec_urls" && (
          <label className={styles.field}>
            <span className={styles.question}>
              {t("picker.wizard.q_spec_urls")}
            </span>
            <p className={styles.hint}>{t("picker.wizard.hint_spec_urls")}</p>
            <textarea
              className={styles.textarea}
              value={spec_urls}
              onChange={(e) => patch({ spec_urls: e.target.value })}
              rows={4}
              spellCheck={false}
              autoComplete="off"
              placeholder={t("picker.wizard.placeholder_spec_urls")}
              data-testid="wizard-spec-urls"
            />
          </label>
        )}

        {stepId === "review" && (
          <div className={styles.field}>
            <span className={styles.question}>
              {t("picker.wizard.q_review")}
            </span>
            <p className={styles.hint}>{t("picker.wizard.hint_review")}</p>
            <dl className={styles.summary} data-testid="wizard-summary">
              <dt>{t("picker.new_run_form.label_project_type")}</dt>
              <dd>{t(`picker.new_run_form.project_type_${project_type}`)}</dd>
              <dt>{t("picker.new_run_form.label_target_repo")}</dt>
              <dd>
                <code>{target_repo}</code>
              </dd>
              <dt>{t("picker.new_run_form.label_target_ref")}</dt>
              <dd>
                <code>{target_ref || "HEAD"}</code>
              </dd>
              {bug_bounty_url ? (
                <>
                  <dt>{t("picker.new_run_form.label_bug_bounty_url")}</dt>
                  <dd className={styles.url}>{bug_bounty_url}</dd>
                </>
              ) : null}
              {contract_addresses ? (
                <>
                  <dt>
                    {isContract
                      ? t("picker.new_run_form.label_contract_addresses")
                      : t("picker.new_run_form.label_in_scope_assets")}
                  </dt>
                  <dd>
                    <pre className={styles.pre}>{contract_addresses}</pre>
                  </dd>
                </>
              ) : null}
              {spec_urls ? (
                <>
                  <dt>{t("picker.new_run_form.label_spec_urls")}</dt>
                  <dd>
                    <pre className={styles.pre}>{spec_urls}</pre>
                  </dd>
                </>
              ) : null}
            </dl>
            <p className={styles.advancedHint}>
              {t("picker.wizard.advanced_hint")}{" "}
              <Link to="/runs/new/review" data-testid="wizard-to-advanced">
                {t("picker.wizard.advanced_link")}
              </Link>
              .
            </p>
            {launch.error ? (
              <div className={styles.launchError} role="alert">
                {t("picker.new_run_form.launch_failed")}{" "}
                {launch.error.message}
              </div>
            ) : null}
          </div>
        )}
      </div>

      <nav className={styles.nav} aria-label={t("picker.wizard.nav_aria")}>
        <button
          type="button"
          className={styles.secondary}
          onClick={back}
          disabled={stepIdx === 0 || launch.isPending}
          data-testid="wizard-back"
        >
          {t("picker.wizard.back")}
        </button>
        {stepId !== "review" ? (
          <button
            type="button"
            className={styles.primary}
            onClick={next}
            disabled={!canAdvance}
            data-testid="wizard-next"
          >
            {t("picker.wizard.next")}
          </button>
        ) : (
          <button
            type="button"
            className={styles.primary}
            onClick={onLaunch}
            disabled={!validity.review || launch.isPending}
            data-testid="wizard-launch"
          >
            {launch.isPending ? (
              <>
                <Spinner size="sm" />
                <span>{t("picker.new_run_form.submit_pending")}</span>
              </>
            ) : (
              <span>{t("picker.new_run_form.submit")}</span>
            )}
          </button>
        )}
      </nav>
      <ErrorModal
        open={errorModalOpen}
        envelope={errorEnvelope}
        onRetry={() => {
          setErrorModalOpen(false);
          launch.reset();
        }}
        onClose={() => setErrorModalOpen(false)}
      />
    </section>
  );
}

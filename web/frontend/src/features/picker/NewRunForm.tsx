// New Run review & launch form (Slice R2).
//
// The Project Picker (R1) lands here with a shared `useNewRunDraft`
// pre-fill (from saved entry, fetched URL, or chat handoff). This form
// is fully controlled by that Zustand store — every field reads from
// the slice and writes back via `patch(...)`, so:
//   - the persisted draft is the single source of truth (no local
//     useState mirror that could drift),
//   - reloading the page restores values via the slice's TTL storage,
//   - the back navigation to `/runs/new` does not lose user edits.
//
// On submit we call `POST /api/runs` via `useLaunchRun`. The 202
// response is mapped to a `/runs/<run_id>` navigation. The draft is
// cleared in a microtask after navigate so the now-unmounted form does
// not flicker, and a subsequent visit to `/runs/new/review` starts
// empty — preventing accidental re-launches against the same spec.
//
// Backend error envelopes are surfaced inline per the slice spec:
//   - 422 invalid_target_repo / invalid_workspace_input / ref_not_found
//   - 502 clone_failed / worktree_failed
//   - 503 anthropic_unreachable (placeholder; not raised here today)
//   - anything else is shown raw inside a <pre> so the user has a
//     copy/paste-able report for the operator.

import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Spinner } from "@/components/Spinner/Spinner";
import { useT } from "@/i18n/useT";
import { ApiError } from "@/lib/api";
import { useNewRunDraft } from "@/store/newRunDraftSlice";

import type { LaunchSpec } from "./types";
import { useLaunchRun } from "./useLaunchRun";
import styles from "./NewRunForm.module.css";

const TARGET_REPO_RE = /^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/;

// Cheap client-side `http(s)://` guard. Backend re-validates with
// Pydantic's `HttpUrl`, so this is a UX gate only — we want to disable
// Launch on a typo without round-tripping to the network.
function isValidUrl(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return false;
  try {
    const url = new URL(trimmed);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function isValidTargetRepo(value: string): boolean {
  return TARGET_REPO_RE.test(value.trim());
}

// Parse a FastAPI `{detail: ...}` envelope from the raw ApiError body.
// Returns `null` if the body is not JSON, or the detail field if it is.
// Detail can be a plain string (legacy 404) or our canonical object.
interface ErrorDetail {
  error?: string;
  message?: string;
  [key: string]: unknown;
}

function parseErrorDetail(err: ApiError): ErrorDetail | string | null {
  try {
    const parsed = JSON.parse(err.body) as { detail?: unknown };
    if (parsed.detail === undefined || parsed.detail === null) return null;
    if (typeof parsed.detail === "string") return parsed.detail;
    if (typeof parsed.detail === "object") return parsed.detail as ErrorDetail;
    return null;
  } catch {
    return null;
  }
}

// Build a draft -> LaunchSpec payload. Empty strings become `undefined`
// so the backend's `Optional[str]` fields stay None rather than being
// stored as literal `""` (which would survive into state.json).
function buildLaunchSpec(draft: ReturnType<typeof useNewRunDraft.getState>): LaunchSpec {
  const opt = (v: string): string | undefined => {
    const trimmed = v.trim();
    return trimmed === "" ? undefined : trimmed;
  };
  return {
    bug_bounty_url: draft.bug_bounty_url.trim(),
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

export default function NewRunForm() {
  const t = useT();
  const navigate = useNavigate();
  const launch = useLaunchRun();

  // Subscribe to every field individually so a `patch({...})` from any
  // input re-renders the form. Reading the whole state via `useNewRunDraft()`
  // would also work but couples re-renders to every action method ref.
  const bug_bounty_url = useNewRunDraft((s) => s.bug_bounty_url);
  const target_repo = useNewRunDraft((s) => s.target_repo);
  const target_ref = useNewRunDraft((s) => s.target_ref);
  const contract_addresses = useNewRunDraft((s) => s.contract_addresses);
  const spec_urls = useNewRunDraft((s) => s.spec_urls);
  const keywords = useNewRunDraft((s) => s.keywords);
  const workers = useNewRunDraft((s) => s.workers);
  const max_concurrent = useNewRunDraft((s) => s.max_concurrent);
  const push_to_remote = useNewRunDraft((s) => s.push_to_remote);
  const patch = useNewRunDraft((s) => s.patch);
  const clearDraft = useNewRunDraft((s) => s.clear);

  // Track whether each validated field has been touched so we don't
  // shout at the user about empty inputs on first paint. We still gate
  // Launch on validity regardless of touch.
  const [touched, setTouched] = useState<{ url?: boolean; repo?: boolean }>({});

  const urlValid = isValidUrl(bug_bounty_url);
  const repoValid = isValidTargetRepo(target_repo);

  const launchDisabled = !urlValid || !repoValid || launch.isPending;

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setTouched({ url: true, repo: true });
    if (launchDisabled) return;

    const spec = buildLaunchSpec(useNewRunDraft.getState());
    launch.mutate(spec, {
      onSuccess: (data) => {
        navigate(`/runs/${data.run_id}`);
        // Clear draft *after* navigate so a stale read in the unmounting
        // tree cannot snapshot the wiped state. queueMicrotask keeps it
        // synchronous-enough for the next render to see a clean store
        // (preventing accidental re-launches against the same spec).
        queueMicrotask(() => {
          clearDraft();
        });
      },
    });
  };

  const launchErrorBlock = (() => {
    const err = launch.error;
    if (!err) return null;
    const detail = parseErrorDetail(err);
    let label: string | null = null;
    if (detail && typeof detail === "object") {
      const code = detail.error;
      const msg = detail.message ?? "";
      if (code === "clone_failed") {
        label = `${t("picker.new_run_form.launch_failed")} ${t(
          "picker.new_run_form.error_clone_failed",
        )} ${msg}`.trim();
      } else if (
        code === "invalid_target_repo" ||
        code === "invalid_workspace_input"
      ) {
        label = `${t("picker.new_run_form.launch_failed")} ${t(
          "picker.new_run_form.error_invalid_target_repo",
        )}`;
      } else if (code === "ref_not_found") {
        label = `${t("picker.new_run_form.launch_failed")} ${t(
          "picker.new_run_form.error_ref_not_found",
        )} ${msg}`.trim();
      } else if (code === "worktree_failed") {
        label = `${t("picker.new_run_form.launch_failed")} ${t(
          "picker.new_run_form.error_clone_failed",
        )} ${msg}`.trim();
      } else if (code === "anthropic_unreachable") {
        label = `${t("picker.new_run_form.launch_failed")} ${t(
          "picker.new_run_form.error_anthropic",
        )}`;
      }
    } else if (typeof detail === "string") {
      label = `${t("picker.new_run_form.launch_failed")} ${detail}`;
    }
    return (
      <div className={styles.launchError} role="alert" data-testid="launch-error">
        <span>
          {label ?? `${t("picker.new_run_form.launch_failed")} HTTP ${err.status}`}
        </span>
        {label === null ? (
          <pre className={styles.launchErrorRaw}>{err.body || err.message}</pre>
        ) : null}
      </div>
    );
  })();

  return (
    <section className={styles.page} data-testid="new-run-form">
      <header className={styles.header}>
        <Link to="/runs/new" className={styles.back} data-testid="new-run-back">
          {t("picker.new_run_form.back")}
        </Link>
        <h1 className={styles.title}>{t("picker.new_run_form.title")}</h1>
      </header>

      <form onSubmit={onSubmit} noValidate>
      <div className={styles.form}>
        <label className={styles.field}>
          <span className={styles.label}>
            {t("picker.new_run_form.label_bug_bounty_url")}
          </span>
          <span className={styles.control}>
            <input
              type="url"
              className={styles.input}
              value={bug_bounty_url}
              onChange={(e) => patch({ bug_bounty_url: e.target.value })}
              onBlur={() => setTouched((p) => ({ ...p, url: true }))}
              autoComplete="off"
              spellCheck={false}
              data-testid="new-run-bug-bounty-url"
            />
            {touched.url && !urlValid ? (
              <p className={styles.error}>
                {t("picker.new_run_form.error_invalid_url")}
              </p>
            ) : null}
          </span>
        </label>

        <label className={styles.field}>
          <span className={styles.label}>
            {t("picker.new_run_form.label_target_repo")}
          </span>
          <span className={styles.control}>
            <input
              type="text"
              className={styles.input}
              value={target_repo}
              onChange={(e) => patch({ target_repo: e.target.value })}
              onBlur={() => setTouched((p) => ({ ...p, repo: true }))}
              autoComplete="off"
              spellCheck={false}
              data-testid="new-run-target-repo"
            />
            {touched.repo && !repoValid ? (
              <p className={styles.error}>
                {t("picker.new_run_form.error_invalid_target_repo")}
              </p>
            ) : null}
          </span>
        </label>

        <label className={styles.field}>
          <span className={styles.label}>
            {t("picker.new_run_form.label_target_ref")}
          </span>
          <span className={styles.control}>
            <input
              type="text"
              className={styles.input}
              value={target_ref}
              onChange={(e) => patch({ target_ref: e.target.value })}
              placeholder={t("picker.new_run_form.label_target_ref_placeholder")}
              autoComplete="off"
              spellCheck={false}
              data-testid="new-run-target-ref"
            />
          </span>
        </label>

        <label className={styles.field}>
          <span className={styles.label}>
            {t("picker.new_run_form.label_contract_addresses")}
          </span>
          <span className={styles.control}>
            <textarea
              className={styles.textarea}
              value={contract_addresses}
              onChange={(e) => patch({ contract_addresses: e.target.value })}
              rows={3}
              spellCheck={false}
              autoComplete="off"
              data-testid="new-run-contracts"
            />
          </span>
        </label>

        <label className={styles.field}>
          <span className={styles.label}>
            {t("picker.new_run_form.label_spec_urls")}
          </span>
          <span className={styles.control}>
            <textarea
              className={styles.textarea}
              value={spec_urls}
              onChange={(e) => patch({ spec_urls: e.target.value })}
              rows={2}
              spellCheck={false}
              autoComplete="off"
              data-testid="new-run-spec-urls"
            />
          </span>
        </label>

        <label className={styles.field}>
          <span className={styles.label}>
            {t("picker.new_run_form.label_keywords")}
          </span>
          <span className={styles.control}>
            <input
              type="text"
              className={styles.input}
              value={keywords}
              onChange={(e) => patch({ keywords: e.target.value })}
              autoComplete="off"
              spellCheck={false}
              data-testid="new-run-keywords"
            />
          </span>
        </label>

        <label className={styles.field}>
          <span className={styles.label}>
            {t("picker.new_run_form.label_workers")}
          </span>
          <span className={styles.control}>
            <input
              type="number"
              className={styles.number}
              value={workers}
              min={1}
              max={32}
              onChange={(e) => {
                const v = Number.parseInt(e.target.value, 10);
                patch({ workers: Number.isFinite(v) ? v : 1 });
              }}
              data-testid="new-run-workers"
            />
          </span>
        </label>

        <label className={styles.field}>
          <span className={styles.label}>
            {t("picker.new_run_form.label_max_concurrent")}
          </span>
          <span className={styles.control}>
            <input
              type="number"
              className={styles.number}
              value={max_concurrent}
              min={1}
              max={256}
              onChange={(e) => {
                const v = Number.parseInt(e.target.value, 10);
                patch({ max_concurrent: Number.isFinite(v) ? v : 1 });
              }}
              data-testid="new-run-max-concurrent"
            />
          </span>
        </label>

        <span className={styles.label}>
          {t("picker.new_run_form.label_push_to_remote")}
        </span>
        <span className={styles.control}>
          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              className={styles.checkbox}
              checked={push_to_remote}
              onChange={(e) => patch({ push_to_remote: e.target.checked })}
              data-testid="new-run-push-to-remote"
            />
            <span>{t("picker.new_run_form.label_push_to_remote")}</span>
          </label>
        </span>
      </div>

      <div className={styles.footer}>
        <p className={styles.estimate}>
          {t("picker.new_run_form.estimated_cost")}
        </p>

        {launchErrorBlock}

        <div className={styles.actions}>
          <button
            type="submit"
            className={styles.submit}
            disabled={launchDisabled}
            data-testid="new-run-launch"
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
        </div>
      </div>
      </form>
    </section>
  );
}

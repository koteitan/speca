// Centered login card.
//
// Two paths to authenticated state:
//   1. "Continue with claude.ai" — spawns the `claude auth login` CLI in a
//      new console; the user completes OAuth in their browser and the SPA
//      polls /api/auth/status every 2s to flip to the dashboard.
//   2. API key — `<input type="password">` + Sign in. The raw key only
//      lives in component state for the duration of the form; on success
//      it is cleared and the user is redirected to `/`.
//
// Why no Zustand for the key value: it would persist across re-mounts and
// risk leaking into devtools / localStorage hydration in future slices.
// React local state + an explicit reset is the smallest blast radius.

import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useT } from "@/i18n/useT";

import { ApiError } from "../../lib/api";
import { useAuthStatus, useLoginWithApiKey, useStartOAuth } from "./useAuth";

import styles from "./LoginScreen.module.css";

export default function LoginScreen() {
  const t = useT();
  const navigate = useNavigate();
  const loginMutation = useLoginWithApiKey();
  const oauthMutation = useStartOAuth();

  const [apiKey, setApiKey] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [oauthHint, setOauthHint] = useState<string | null>(null);

  // Poll status every 2s while OAuth is in progress so the SPA flips to the
  // dashboard the moment `claude auth login` writes credentials.json.
  const authStatus = useAuthStatus({ polling: oauthMutation.isSuccess });

  useEffect(() => {
    if (oauthMutation.isSuccess && authStatus.data?.logged_in) {
      navigate("/");
    }
  }, [oauthMutation.isSuccess, authStatus.data?.logged_in, navigate]);

  const trimmedKey = apiKey.trim();
  const canSubmit = trimmedKey.length > 0 && !loginMutation.isPending;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    setErrorMessage(null);

    try {
      await loginMutation.mutateAsync({ key: trimmedKey });
      // Clear the key from React state so it does not live longer than
      // necessary. The server-side cache is already primed by useAuth.ts.
      setApiKey("");
      navigate("/");
    } catch (err) {
      const message =
        err instanceof ApiError
          ? t("login.error_signin_http", {
              status: err.status,
              body: err.body || err.message,
            })
          : err instanceof Error
            ? err.message
            : t("login.error_signin_unknown");
      setErrorMessage(message);
    }
  }

  async function handleOAuth() {
    setErrorMessage(null);
    setOauthHint(null);
    try {
      const result = await oauthMutation.mutateAsync();
      setOauthHint(result.hint ?? t("login.oauth_hint_default"));
    } catch (err) {
      const message =
        err instanceof ApiError
          ? t("login.error_oauth_http", {
              status: err.status,
              body: err.body || err.message,
            })
          : err instanceof Error
            ? err.message
            : t("login.error_oauth_unknown");
      setErrorMessage(message);
    }
  }

  return (
    <div className={styles.screen}>
      <section
        className={styles.card}
        aria-labelledby="login-title"
      >
        <header>
          <h1 id="login-title" className={styles.title}>
            {t("login.title")}
          </h1>
          <p className={styles.subtitle}>{t("login.subtitle")}</p>
        </header>

        <button
          type="button"
          className={styles.oauthButton}
          onClick={handleOAuth}
          disabled={oauthMutation.isPending || oauthMutation.isSuccess}
          aria-busy={oauthMutation.isPending}
        >
          {oauthMutation.isPending
            ? t("login.oauth_button_pending")
            : oauthMutation.isSuccess
              ? t("login.oauth_button_success")
              : t("login.oauth_button_idle")}
        </button>
        {oauthHint !== null && (
          <p className={styles.oauthHint} role="status">
            {oauthHint}
          </p>
        )}

        <div className={styles.divider} role="separator">
          {t("login.divider")}
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="speca-api-key">
              {t("login.api_key_label")}
            </label>
            <input
              id="speca-api-key"
              className={styles.input}
              type="password"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              placeholder={t("login.api_key_placeholder")}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              disabled={loginMutation.isPending}
              aria-invalid={errorMessage !== null}
              aria-describedby={
                errorMessage ? "speca-login-error" : undefined
              }
            />
          </div>

          {errorMessage !== null && (
            <p
              id="speca-login-error"
              className={styles.error}
              role="alert"
              style={{ marginTop: "var(--nyx-space-5)" }}
            >
              {errorMessage}
            </p>
          )}

          <button
            type="submit"
            className={styles.submit}
            disabled={!canSubmit}
            style={{ marginTop: "var(--nyx-space-6)" }}
          >
            {loginMutation.isPending
              ? t("login.submit_pending")
              : t("login.submit_idle")}
          </button>
        </form>
      </section>
    </div>
  );
}

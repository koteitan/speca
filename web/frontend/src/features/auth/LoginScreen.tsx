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
import {
  useAuthStatus,
  useLoginWithApiKey,
  usePasteOAuthCode,
  useStartOAuth,
  useStartPasteOAuth,
} from "./useAuth";

import styles from "./LoginScreen.module.css";

export default function LoginScreen() {
  const t = useT();
  const navigate = useNavigate();
  const loginMutation = useLoginWithApiKey();
  const oauthMutation = useStartOAuth();
  // CLI spec §4.5.1 paste-code OAuth — inline flow that keeps the user
  // in the web UI for the whole dance. Falls back to ``useStartOAuth``
  // (spawn-new-console) when the inline path errors.
  const startPasteOAuth = useStartPasteOAuth();
  const pasteOAuthCode = usePasteOAuthCode();
  const [pasteSessionId, setPasteSessionId] = useState<string | null>(null);
  const [pasteAuthUrl, setPasteAuthUrl] = useState<string | null>(null);
  const [pasteCode, setPasteCode] = useState("");

  const [apiKey, setApiKey] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [oauthHint, setOauthHint] = useState<string | null>(null);

  // Poll status every 2s while EITHER OAuth surface is mid-flight so the
  // dashboard appears the moment credentials.json updates on disk.
  const authStatus = useAuthStatus({
    polling:
      oauthMutation.isSuccess ||
      pasteSessionId !== null ||
      pasteOAuthCode.isSuccess,
  });

  useEffect(() => {
    if (authStatus.data?.logged_in) {
      navigate("/");
    }
  }, [authStatus.data?.logged_in, navigate]);

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

  async function handleStartPasteOAuth() {
    setErrorMessage(null);
    setPasteCode("");
    try {
      const result = await startPasteOAuth.mutateAsync();
      setPasteSessionId(result.session_id);
      setPasteAuthUrl(result.auth_url);
      if (result.auth_url && typeof window !== "undefined") {
        window.open(result.auth_url, "_blank", "noopener,noreferrer");
      }
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

  async function handleSubmitPasteCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pasteSessionId) return;
    const trimmed = pasteCode.trim();
    if (!trimmed) return;
    setErrorMessage(null);
    try {
      const result = await pasteOAuthCode.mutateAsync({
        session_id: pasteSessionId,
        code: trimmed,
      });
      if (result.error) {
        setErrorMessage(result.error);
        return;
      }
      // The auth-status polling effect above navigates to "/" once the
      // credentials file is updated; nothing further to do here.
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
          onClick={handleStartPasteOAuth}
          disabled={
            startPasteOAuth.isPending || pasteSessionId !== null ||
            pasteOAuthCode.isSuccess
          }
          aria-busy={startPasteOAuth.isPending}
          data-testid="login-paste-oauth-start"
        >
          {startPasteOAuth.isPending
            ? t("login.paste_oauth.button_pending")
            : t("login.paste_oauth.button_idle")}
        </button>

        {pasteSessionId ? (
          <form
            className={styles.pasteFlow}
            onSubmit={handleSubmitPasteCode}
            data-testid="login-paste-oauth-form"
          >
            {pasteAuthUrl ? (
              <p className={styles.pasteHint}>
                {t("login.paste_oauth.url_prefix")}{" "}
                <a
                  href={pasteAuthUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.pasteLink}
                >
                  {t("login.paste_oauth.open_in_browser")}
                </a>
              </p>
            ) : (
              <p className={styles.pasteHint}>
                {t("login.paste_oauth.no_url_yet")}
              </p>
            )}
            <label className={styles.label} htmlFor="speca-paste-code">
              {t("login.paste_oauth.code_label")}
            </label>
            <input
              id="speca-paste-code"
              className={styles.input}
              type="text"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              placeholder={t("login.paste_oauth.code_placeholder")}
              value={pasteCode}
              onChange={(e) => setPasteCode(e.target.value)}
              disabled={pasteOAuthCode.isPending}
              data-testid="login-paste-oauth-code"
            />
            <button
              type="submit"
              className={styles.submit}
              disabled={pasteOAuthCode.isPending || pasteCode.trim().length === 0}
              data-testid="login-paste-oauth-submit"
            >
              {pasteOAuthCode.isPending
                ? t("login.paste_oauth.submit_pending")
                : t("login.paste_oauth.submit_idle")}
            </button>
          </form>
        ) : null}

        <details className={styles.pasteFallback}>
          <summary>{t("login.paste_oauth.fallback_summary")}</summary>
          <button
            type="button"
            className={styles.oauthButton}
            onClick={handleOAuth}
            disabled={oauthMutation.isPending || oauthMutation.isSuccess}
            aria-busy={oauthMutation.isPending}
            style={{ marginTop: "var(--nyx-space-3)" }}
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
        </details>

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

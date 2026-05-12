// Centered login card.
//
// Two paths to authenticated state:
//   1. "Continue with claude.ai" — v0 stub, button is `disabled` with a
//      tooltip explaining that the OAuth flow lands in v1. We do NOT call
//      the stub endpoint from this button.
//   2. API key — `<input type="password">` + Sign in. The raw key only
//      lives in component state for the duration of the form; on success
//      it is cleared and the user is redirected to `/`.
//
// Why no Zustand for the key value: it would persist across re-mounts and
// risk leaking into devtools / localStorage hydration in future slices.
// React local state + an explicit reset is the smallest blast radius.

import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { useLoginWithApiKey } from "./useAuth";

import styles from "./LoginScreen.module.css";

export default function LoginScreen() {
  const navigate = useNavigate();
  const loginMutation = useLoginWithApiKey();

  const [apiKey, setApiKey] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
          ? `Sign in failed (HTTP ${err.status}): ${err.body || err.message}`
          : err instanceof Error
            ? err.message
            : "Sign in failed for an unknown reason.";
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
            Sign in to SPECA
          </h1>
          <p className={styles.subtitle}>
            Local web UI — credentials never leave your machine.
          </p>
        </header>

        <button
          type="button"
          className={styles.oauthButton}
          disabled
          title="v0 では未対応、v1 で実装"
          aria-disabled="true"
        >
          Continue with claude.ai (Pro/Max)
        </button>

        <div className={styles.divider} role="separator">
          or use API key
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="speca-api-key">
              Anthropic API key
            </label>
            <input
              id="speca-api-key"
              className={styles.input}
              type="password"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              placeholder="sk-ant-..."
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
            {loginMutation.isPending ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </div>
  );
}

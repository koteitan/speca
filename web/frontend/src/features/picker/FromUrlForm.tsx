// "From URL" entry of the Project Picker (Slice R1, panel B).
//
// Submits a bug-bounty URL (+ optional comma-separated contract list) to
// the B3 endpoint, then stuffs the response into the shared draft and
// navigates to R2. On error we either offer a retry hint (transient
// Anthropic failure) or continue with an empty draft toward R2 so the
// user can fill the form manually — the picker is not a hard gate.

import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { Spinner } from "@/components/Spinner/Spinner";
import { useT } from "@/i18n/useT";
import { useNewRunDraft } from "@/store/newRunDraftSlice";

import { useFetchUrl } from "./useFetchUrl";
import styles from "./FromUrlForm.module.css";

export interface FromUrlFormProps {
  reviewPath: string;
}

// Cheap client-side URL guard. Backend re-validates with Pydantic's
// `HttpUrl`, so this is just a UX nicety — we want to disable the submit
// button without spending a network round trip on a typo.
function isValidUrl(value: string): boolean {
  if (!value.trim()) return false;
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function FromUrlForm({ reviewPath }: FromUrlFormProps) {
  const t = useT();
  const navigate = useNavigate();
  const fetchUrl = useFetchUrl();
  const applyFromUrl = useNewRunDraft((s) => s.applyFromUrl);
  const clearDraft = useNewRunDraft((s) => s.clear);

  const [url, setUrl] = useState("");
  const [contracts, setContracts] = useState("");

  const submitDisabled = fetchUrl.isPending || !isValidUrl(url);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitDisabled) return;
    fetchUrl.mutate(
      {
        bug_bounty_url: url.trim(),
        contract_addresses: contracts.trim() || null,
      },
      {
        onSuccess: (data) => {
          applyFromUrl(data);
          navigate(reviewPath);
        },
        onError: (err) => {
          // `invalid_scope_response` — backend reached Anthropic but the
          // response was unparseable. We still continue to R2 with an
          // empty draft so the user can fill the form by hand.
          if (err.code === "invalid_scope_response") {
            clearDraft();
            navigate(reviewPath);
          }
          // `anthropic_unreachable` / unknown — keep the user on this
          // form, the error block below renders the actionable message.
        },
      },
    );
  };

  const errorMessage = (() => {
    const err = fetchUrl.error;
    if (!err) return null;
    if (err.code === "anthropic_unreachable") {
      return t("picker.from_url.error_anthropic");
    }
    if (err.code === "invalid_scope_response") {
      return t("picker.from_url.error_parse");
    }
    return err.message;
  })();

  return (
    <form className={styles.form} onSubmit={onSubmit}>
      <label className={styles.field}>
        <span className={styles.label}>
          {t("picker.from_url.label_bug_bounty_url")}
        </span>
        <input
          type="url"
          className={styles.input}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={t("picker.from_url.placeholder_bug_bounty")}
          required
          autoComplete="off"
          spellCheck={false}
          data-testid="from-url-input"
        />
      </label>

      <label className={styles.field}>
        <span className={styles.label}>
          {t("picker.from_url.label_contract_addresses")}
        </span>
        <textarea
          className={styles.textarea}
          value={contracts}
          onChange={(e) => setContracts(e.target.value)}
          rows={2}
          placeholder="0x..., 0x..."
          spellCheck={false}
          autoComplete="off"
          data-testid="from-url-contracts"
        />
      </label>

      <div className={styles.actions}>
        <button
          type="submit"
          className={styles.submit}
          disabled={submitDisabled}
          data-testid="from-url-submit"
        >
          {fetchUrl.isPending ? (
            <>
              <Spinner size="sm" />
              <span className={styles.submitLabel}>
                {t("picker.from_url.submit")}
              </span>
            </>
          ) : (
            <span className={styles.submitLabel}>
              {t("picker.from_url.submit")}
            </span>
          )}
        </button>
      </div>

      {errorMessage ? (
        <p className={styles.errorMessage} role="alert">
          {errorMessage}
        </p>
      ) : null}
    </form>
  );
}

export default FromUrlForm;

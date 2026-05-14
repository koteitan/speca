// <OpenInVSCode>
//
// Single common control for the multi-placement "Open in VSCode" CTA
// described in UI_DESIGN.md §4.10.5. Three visual variants (`button`,
// `icon`, `menuitem`) share the same disabled / click / accessibility
// behaviour:
//
//   * `code.installed === false` => disabled + tooltip via `title`
//   * click => fire the `useOpenInVSCode` mutation (fire-and-forget,
//     success / failure surface via `window.alert` for v0)
//   * focus-visible outline is enforced by the CSS module — every variant
//     inherits it from `.button`
//
// Slice G is responsible for *placing* this control around the app; we
// only expose the contract.

import { useId, type ReactElement } from "react";

import { useIntegrationsStatus } from "@/features/integrations/useIntegrationsStatus";
import { useT } from "@/i18n/useT";

import styles from "./OpenInVSCode.module.css";
import { useOpenInVSCode } from "./useOpenInVSCode";

export type OpenInVSCodeVariant = "button" | "icon" | "menuitem";

export interface OpenInVSCodeProps {
  /** Absolute filesystem path to open. Required. */
  path: string;
  /** 1-based line number; when present we pass `code -g <path>:<line>`. */
  line?: number;
  /**
   * Visible label and (for the icon variant) the screen-reader name. Defaults
   * to the localized "Open in VSCode" string.
   */
  label?: string;
  /** Pick a visual treatment. Defaults to `button`. */
  variant?: OpenInVSCodeVariant;
  /** Extra class for the wrapping button (rare; mostly Slice G escape hatch). */
  className?: string;
}

// Tiny inline SVG so we don't need an icon font. Stroke uses currentColor
// so the icon picks up the same colour as adjacent text via the CSS module.
function VSCodeGlyph(): ReactElement {
  return (
    <svg
      className={styles.icon}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M2 4.5l4-2.5v12l-4-2.5V4.5z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <path
        d="M6 6.5l8-4.5v12l-8-4.5V6.5z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function OpenInVSCode(props: OpenInVSCodeProps): ReactElement {
  const t = useT();
  const defaultLabel = t("integrations.open_in_vscode.default_label");
  const { path, line, label = defaultLabel, variant = "button", className } = props;
  const status = useIntegrationsStatus();
  const mutation = useOpenInVSCode();
  const titleId = useId();

  // While the status query is loading we keep the control enabled-but-pending
  // rather than disabled: the user clicking a button that just rendered should
  // feel responsive. The mutation itself will report a useful error if `code`
  // is not present on the server side.
  const codeInstalled = status.data?.code.installed ?? true;
  const disabled = !codeInstalled || mutation.isPending;
  const tooltip = !codeInstalled
    ? t("integrations.open_in_vscode.missing_hint")
    : mutation.isPending
      ? t("integrations.open_in_vscode.launching")
      : `${label} (${path}${line ? `:${line}` : ""})`;

  const variantClass =
    variant === "icon"
      ? styles.variantIcon
      : variant === "menuitem"
        ? styles.variantMenuitem
        : styles.variantButton;

  const classes = [styles.button, variantClass, className]
    .filter(Boolean)
    .join(" ");

  const ariaProps =
    variant === "icon"
      ? { "aria-label": label }
      : { "aria-describedby": titleId };

  const handleClick = (): void => {
    if (disabled) return;
    mutation.mutate({ path, line });
  };

  return (
    <button
      type="button"
      className={classes}
      disabled={disabled}
      onClick={handleClick}
      title={tooltip}
      {...ariaProps}
    >
      <VSCodeGlyph />
      {variant !== "icon" && <span className={styles.label}>{label}</span>}
      {variant !== "icon" && (
        <span id={titleId} hidden>
          {tooltip}
        </span>
      )}
    </button>
  );
}

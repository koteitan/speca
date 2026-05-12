// One-shot theme bootstrap.
//
// Applies the resolved theme attribute on `<html>` at boot and keeps it
// in sync with both the user's selection (Zustand) and the OS
// preference (matchMedia). Side-effect only — nothing to render.

import { resolveTheme, useTheme, type EffectiveTheme } from "@/store/themeSlice";

function apply(effective: EffectiveTheme): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = effective;
  document.documentElement.style.colorScheme = effective;
}

export function initTheme(): void {
  if (typeof window === "undefined") return;

  // Initial paint — read whatever Zustand hydrated from localStorage.
  apply(resolveTheme(useTheme.getState().mode));

  // Re-apply whenever the user picks a different mode.
  useTheme.subscribe((state) => {
    apply(resolveTheme(state.mode));
  });

  // Re-apply when the OS theme flips while we're on "system".
  const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
  if (mq) {
    const handler = () => {
      if (useTheme.getState().mode === "system") {
        apply(resolveTheme("system"));
      }
    };
    // addEventListener is the modern API; addListener stays for Safari < 14.
    mq.addEventListener?.("change", handler);
  }
}

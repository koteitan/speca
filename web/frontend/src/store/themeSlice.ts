// themeSlice — light / dark / system theme preference.
//
// Light/dark CSS lives in `styles/tokens.css` keyed off `[data-theme]`.
// This slice owns the active mode, persists the user's preference to
// localStorage, and resolves "system" against `prefers-color-scheme`.
//
// The DOM attribute (`<html data-theme="...">`) is set imperatively from
// a single boot subscription in `themeBootstrap.ts` so React tree
// rerenders are unaffected — the attribute is a presentation detail.

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type ThemeMode = "light" | "dark" | "system";
export type EffectiveTheme = "light" | "dark";

export interface ThemeState {
  /** What the user explicitly selected. */
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
}

export const useTheme = create<ThemeState>()(
  persist(
    (set) => ({
      mode: "system",
      setMode: (mode) => set({ mode }),
    }),
    {
      name: "speca.theme",
      storage: createJSONStorage(() => localStorage),
      version: 1,
    },
  ),
);

/** Resolve the *effective* theme given a stored mode + system preference. */
export function resolveTheme(mode: ThemeMode): EffectiveTheme {
  if (mode === "light" || mode === "dark") return mode;
  if (typeof window === "undefined") return "light";
  const dark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  return dark ? "dark" : "light";
}

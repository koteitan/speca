// authSlice — UI-only auth state.
//
// The source of truth for "am I logged in?" is the TanStack Query cache
// behind `useAuthStatus()` in `features/auth/useAuth.ts`. That hook talks
// to the backend, which talks to `~/.claude/credentials.json` — there is
// no scenario in v0 where Zustand should disagree with that chain.
//
// This slice therefore intentionally holds only ephemeral UI state that
// the server cannot answer: which method the user last tried. It is safe
// to leave unused; later slices can grow it without breaking imports.

import { create } from "zustand";

import type { AuthMethod } from "../features/auth/types";

interface AuthUiState {
  // Last auth method the user actively tried in this browser session.
  // Used (for example) to pre-focus the API-key field on a retry. Not
  // persisted to localStorage — sessions start fresh on reload.
  lastAttemptedMethod: AuthMethod | null;
  setLastAttemptedMethod: (method: AuthMethod | null) => void;
  resetAuthUi: () => void;
}

export const useAuthUiStore = create<AuthUiState>((set) => ({
  lastAttemptedMethod: null,
  setLastAttemptedMethod: (method) => set({ lastAttemptedMethod: method }),
  resetAuthUi: () => set({ lastAttemptedMethod: null }),
}));

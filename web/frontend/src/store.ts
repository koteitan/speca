// Global Zustand store barrel.
//
// Feature slices live in `src/store/<feature>Slice.ts` and are re-exported
// from here so consumers can `import { useFooStore } from "@/store"`. Insert
// the re-export under the anchor below — keep the anchor text verbatim.

// === store slices ===
// authSlice exposes UI-only state (last attempted method, etc.); the
// authoritative login state comes from `useAuthStatus()` in
// `features/auth/useAuth.ts` — do not duplicate server state here.
export { useAuthUiStore } from "./store/authSlice";
export { useNewRunDraft } from "./store/newRunDraftSlice";
export { useChatApprovals } from "./store/chatApprovalsSlice";
export { useChatUi } from "./store/chatUiSlice";
export { useTheme } from "./store/themeSlice";

export {};

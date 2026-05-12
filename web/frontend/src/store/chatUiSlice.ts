// chatUiSlice — global open/close state for the right-side chat panel.
//
// AppShell originally owned this in component-local useState, which meant
// only the chat toggle inside <Header/> could flip it. R1's Picker page
// has an "Open chat" entry that needs to open the panel from outside the
// AppShell subtree, so we hoist the state into a tiny Zustand slice that
// any component can subscribe to or mutate.
//
// In-memory only — chat open/close is a UI affordance, not user data.

import { create } from "zustand";

export interface ChatUiState {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
}

export const useChatUi = create<ChatUiState>((set) => ({
  open: false,
  setOpen: (open) => set({ open }),
  toggle: () => set((state) => ({ open: !state.open })),
}));

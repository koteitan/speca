// New Run draft slice (Slice R1).
//
// Three entry points (Saved targets / From URL / Chat handoff) populate
// a single shared draft that R2 (NewRunForm) will read. Keeping the
// shape flat — one string per form field — means the consumer can spread
// it straight into a controlled <form> in R2 without an extra adapter.
//
// Persistence:
//   - localStorage, key `speca.newRunDraft`, 24h TTL
//   - we drop `origin` from the persisted payload (`partialize`) so a
//     reloaded draft does not lie about where it came from
//   - older snapshots are discarded via `merge` (defaults win) if the
//     stored shape is unexpected — safer than partially hydrating an
//     evolving schema
//
// The slice is intentionally decoupled from the v0 PersistQueryClient
// (which only persists TanStack Query state). Two separate localStorage
// keys keep eviction logic independent.

import { create } from "zustand";
import { persist, type PersistStorage, type StorageValue } from "zustand/middleware";

import type { FetchUrlResponse } from "../features/picker/useFetchUrl";
import type { SavedTarget } from "../features/picker/types";

export type NewRunDraftOrigin = "saved" | "url" | "chat" | "empty";

export interface NewRunDraft {
  bug_bounty_url: string;
  target_repo: string;
  target_ref: string;
  contract_addresses: string;
  spec_urls: string;
  keywords: string;
  workers: number;
  max_concurrent: number;
  push_to_remote: boolean;
  origin: NewRunDraftOrigin;
}

export interface NewRunDraftActions {
  applyFromSaved: (target: SavedTarget) => void;
  applyFromUrl: (scope: FetchUrlResponse) => void;
  applyFromChat: (payload: NewRunDraft) => void;
  patch: (partial: Partial<NewRunDraft>) => void;
  clear: () => void;
}

export type NewRunDraftState = NewRunDraft & NewRunDraftActions;

const STORAGE_KEY = "speca.newRunDraft";
const TTL_MS = 24 * 60 * 60 * 1000;

// Defaults match the orchestrator flag surface: `--workers 4
// --max-concurrent 64`, no push. Everything else is an empty string so
// the R2 form can render placeholders without "undefined" leaks.
export const DEFAULT_DRAFT: NewRunDraft = {
  bug_bounty_url: "",
  target_repo: "",
  target_ref: "",
  contract_addresses: "",
  spec_urls: "",
  keywords: "",
  workers: 4,
  max_concurrent: 64,
  push_to_remote: false,
  origin: "empty",
};

// Custom storage adapter that wraps the default JSON shape with our own
// `savedAt` timestamp so we can enforce a 24h TTL. Zustand's built-in
// persist exposes a `version` field but not a wall-clock expiry, hence
// the manual wrapper. Returning `null` on expiry causes the store to
// fall back to the in-code defaults — exactly what we want.
const ttlStorage: PersistStorage<NewRunDraftState> = {
  getItem: (name) => {
    if (typeof window === "undefined") return null;
    const raw = window.localStorage.getItem(name);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as {
        savedAt?: number;
        value?: StorageValue<NewRunDraftState>;
      };
      if (
        !parsed.savedAt ||
        typeof parsed.savedAt !== "number" ||
        Date.now() - parsed.savedAt > TTL_MS
      ) {
        window.localStorage.removeItem(name);
        return null;
      }
      return parsed.value ?? null;
    } catch {
      window.localStorage.removeItem(name);
      return null;
    }
  },
  setItem: (name, value) => {
    if (typeof window === "undefined") return;
    const wrapper = { savedAt: Date.now(), value };
    window.localStorage.setItem(name, JSON.stringify(wrapper));
  },
  removeItem: (name) => {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(name);
  },
};

export const useNewRunDraft = create<NewRunDraftState>()(
  persist(
    (set) => ({
      ...DEFAULT_DRAFT,

      applyFromSaved: (target) =>
        set({
          ...DEFAULT_DRAFT,
          bug_bounty_url: target.bug_bounty_url ?? "",
          target_repo: target.target_repo,
          target_ref: target.target_ref ?? "",
          origin: "saved",
        }),

      applyFromUrl: (scope) =>
        set({
          ...DEFAULT_DRAFT,
          bug_bounty_url: scope.program_url,
          spec_urls: scope.spec_urls ?? "",
          keywords: scope.keywords ?? "",
          // The picker fetch_url response carries scope contracts but no
          // single target_repo — R2 lets the user paste the repo URL.
          // We forward contract addresses as a comma-joined string so R2
          // can show them prefilled.
          contract_addresses: (scope.in_scope_contracts ?? [])
            .map((c) => c.address)
            .filter(Boolean)
            .join(", "),
          origin: "url",
        }),

      applyFromChat: (payload) =>
        set({
          ...payload,
          origin: "chat",
        }),

      patch: (partial) => set((prev) => ({ ...prev, ...partial })),

      clear: () => set({ ...DEFAULT_DRAFT }),
    }),
    {
      name: STORAGE_KEY,
      storage: ttlStorage,
      // Persist field values only — never the action references (they
      // are recreated on every boot) and never the `origin` discriminator
      // (it must be re-derived from the entry point on the next session).
      partialize: (state) =>
        ({
          bug_bounty_url: state.bug_bounty_url,
          target_repo: state.target_repo,
          target_ref: state.target_ref,
          contract_addresses: state.contract_addresses,
          spec_urls: state.spec_urls,
          keywords: state.keywords,
          workers: state.workers,
          max_concurrent: state.max_concurrent,
          push_to_remote: state.push_to_remote,
        }) as unknown as NewRunDraftState,
      // If the persisted snapshot is missing or has a foreign shape,
      // fall back to defaults rather than partially-hydrating into an
      // inconsistent state.
      merge: (persisted, current) => {
        if (!persisted || typeof persisted !== "object") return current;
        return { ...current, ...(persisted as Partial<NewRunDraftState>) };
      },
    },
  ),
);

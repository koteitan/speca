/**
 * Default keybinds for speca-cli. Each action maps to one or more key
 * descriptors that the keybinds layer matches against `useInput` events.
 *
 * Key descriptor grammar:
 *   - A single printable character: `"q"`, `"j"`, `"/"`
 *   - An Ink modifier name: `"escape"`, `"return"`, `"tab"`,
 *     `"upArrow"`, `"downArrow"`, `"leftArrow"`, `"rightArrow"`,
 *     `"backspace"`, `"delete"`, `"pageUp"`, `"pageDown"`
 *   - A `ctrl+<key>` chord: `"ctrl+c"`, `"ctrl+l"` (case-insensitive on the
 *     letter portion).
 *
 * Action names are kebab-case and used both as the key in `config.toml`
 * (`[keybinds]` table) and as the `action` argument to `useKeybind`.
 */

/**
 * Closed list of action names. Anything not listed here is a typo and should
 * fail to type-check at the `useKeybind` call site.
 *
 * Add a new action by appending to this tuple AND populating
 * `DEFAULT_KEYBINDS` below — the `Record<KeybindAction, string[]>` typing
 * forces the two to stay in sync.
 */
export const KEYBIND_ACTIONS = [
  // Quit / cancel — present on every screen.
  "exit",
  // Dismiss a modal without quitting.
  "cancel",
  // Confirm a modal action.
  "confirm",
  // Trigger an optional retry on an error modal.
  "retry",
  // Generic navigation.
  "up",
  "down",
  "left",
  "right",
  "pageUp",
  "pageDown",
  // Pipeline dashboard (M3) — show / hide log pane.
  "toggle-log",
  // Pipeline dashboard (M3) — graceful stop (SIGTERM via handle.stop).
  // Shares the "s" key with sort-mode; safe because each subcommand only
  // subscribes to the action it cares about.
  "stop-graceful",
  // Pipeline dashboard (M3) — force-kill (SIGKILL via handle.kill).
  // Shares the "f" key with filter-mode (same caveat as stop-graceful).
  "stop-force",
  // Finding browser (M4) — enter filter-edit mode.
  "filter-mode",
  // Finding browser (M4) — cycle sort key.
  "sort-mode",
  // Finding browser (M4) — enter text-search edit mode.
  "search-mode",
  // Finding browser (M4) — load / refresh the code peek for the selection.
  "code-peek",
  // Finding browser (M4) — reload the underlying glob from disk.
  "reload",
  // Ask Claude (M5) — focus the chat input.
  "focus-chat",
  // Ask Claude (M5) — start a new session (drop session.json + claude session id).
  "new-session",
  // Ask Claude (M5) — open the context modal showing the injected finding.
  "show-context",
  // Help overlay (any screen).
  "help",
] as const;

export type KeybindAction = (typeof KEYBIND_ACTIONS)[number];

export function isKeybindAction(value: string): value is KeybindAction {
  return (KEYBIND_ACTIONS as readonly string[]).includes(value);
}

export const DEFAULT_KEYBINDS: Record<KeybindAction, string[]> = {
  exit: ["q", "ctrl+c"],
  cancel: ["escape"],
  confirm: ["return"],
  retry: ["r"],
  up: ["upArrow", "k"],
  down: ["downArrow", "j"],
  left: ["leftArrow", "h"],
  right: ["rightArrow", "l"],
  pageUp: ["pageUp"],
  pageDown: ["pageDown"],
  "toggle-log": ["l"],
  "stop-graceful": ["s"],
  "stop-force": ["f"],
  "filter-mode": ["f"],
  "sort-mode": ["s"],
  "search-mode": ["/"],
  "code-peek": ["c"],
  reload: ["r"],
  "focus-chat": ["i"],
  "new-session": ["n"],
  "show-context": ["c"],
  help: ["?"],
};

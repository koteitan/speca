// Public barrel for ConfirmDialog.
//
// Slice S1 (Fork) and the planned D2 (Cancel / Re-run) both import from
// this barrel so the component path stays stable even if we later split
// the focus-trap logic into its own helper module.

export { ConfirmDialog } from "./ConfirmDialog";
export type { ConfirmDialogProps } from "./ConfirmDialog";
export { default } from "./ConfirmDialog";

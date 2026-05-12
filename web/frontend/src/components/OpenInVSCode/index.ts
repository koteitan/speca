// Public barrel for the OpenInVSCode component.
//
// Slice G consumers should import from this barrel rather than reaching into
// the individual files so that we are free to refactor the internal layout
// (e.g. split the icon into its own module) without breaking call sites.

export { OpenInVSCode } from "./OpenInVSCode";
export type {
  OpenInVSCodeProps,
  OpenInVSCodeVariant,
} from "./OpenInVSCode";
export { useOpenInVSCode } from "./useOpenInVSCode";
export type {
  OpenInVSCodePayload,
  OpenInVSCodeResponse,
} from "./useOpenInVSCode";

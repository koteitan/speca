// Ambient declaration for CSS Modules so `import styles from "./X.module.css"`
// type-checks under `tsc --noEmit`. Vite handles the runtime; this only
// teaches TypeScript that the import returns a string-keyed map.
//
// Scoped to this feature folder to keep edits exclusive to the auth slice.

declare module "*.module.css" {
  const classes: Readonly<Record<string, string>>;
  export default classes;
}

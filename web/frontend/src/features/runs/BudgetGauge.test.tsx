// Slice D3 — smoke test for BudgetGauge.
//
// The frontend does not currently ship a test runner (no `vitest` in
// devDependencies, no `npm test` script in package.json). Per the slice
// brief, we keep this file as an *import-only smoke* so:
//
//   * `tsc --noEmit` (run as part of `npm run build`) still validates
//     that the component, its CSS module, and its i18n keys compile.
//   * When a test runner is added later, this file is one rename away
//     from a real assertion suite — no scaffolding work needed.
//
// We deliberately avoid pulling in `@testing-library/react` or
// `react-dom/server` here so the build doesn't grow a dev-time
// dependency just to satisfy a placeholder.

import { BudgetGauge } from "./BudgetGauge";

// Touch the import in a way the bundler / `noUnusedLocals` won't strip.
// The result is intentionally discarded — we only care that the
// component is constructible as a value.
export const __smokeBudgetGauge = typeof BudgetGauge;

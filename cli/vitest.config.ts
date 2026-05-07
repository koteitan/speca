import { defineConfig } from "vitest/config";

/**
 * Coverage gate scoped to the pure libs (`src/lib/**`). Components
 * (Ink-rendered TSX) are exercised by render tests but contribute noisy
 * branch counts that don't reflect real risk; we'd rather pin a tight
 * threshold on the reducers / parsers / loaders that drive every screen.
 */
export default defineConfig({
  test: {
    coverage: {
      provider: "v8",
      include: ["src/lib/**/*.ts"],
      exclude: [
        // Auto-generated (covered indirectly by the contract test).
        "src/lib/schemas/generated/**",
        // Type-only re-exports.
        "src/lib/keybinds/match.ts",
      ],
      reporter: ["text", "json-summary", "lcov"],
      thresholds: {
        lines: 85,
        statements: 85,
        functions: 85,
        branches: 75,
      },
    },
  },
});

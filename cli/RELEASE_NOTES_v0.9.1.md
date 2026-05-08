# speca-cli v0.9.1

Patch release on the 0.9.x soak line.

```bash
npx speca-cli@latest doctor
```

## Highlights

- **All `ErrorKind`s now have a real caller.** v0.9.0 shipped the
  `errors-reporter` infrastructure but four kinds — `auth-expired`,
  `schema-mismatch`, `stale-resume`, `subprocess-crash` — had no code path
  firing them. v0.9.1 wires them all up:
  - `speca run` refuses to spawn when the active OAuth token is past its
    `expires_at` (`auth-expired`), or when `outputs/TARGET_INFO.json` was
    rewritten meaningfully later than the newest
    `outputs/01b_PARTIAL_*.json` without `--force` (`stale-resume`, with a
    60-second grace window for back-to-back `init` + `run`).
  - `speca browse` now exits with a parseable
    `[ERROR kind=schema-mismatch] …` line when every matched partial fails
    loader validation, instead of dropping into a zero-row TUI.
  - `speca run`'s spawn-error handler reports `kind=subprocess-crash` on
    both headless and TUI paths.
- **Unknown phase-id heads-up.** `speca run` warns to stderr when
  `--phase` / `--target` carry an id outside `KNOWN_PHASE_IDS`. Forks may
  legitimately add phases via custom orchestrator configs, so the unknown
  id is forwarded — the warn just removes the surprise factor.
- **`KNOWN_VERDICTS` closed-set type.** Call sites that hand-write a
  verdict literal can now opt into `KnownVerdict`; a typo'd verdict fails
  to compile.
- **Post-publish smoke job.** `release.yml` now spins up a clean ubuntu
  runner after every successful `npm publish`, installs the freshly-
  published version from the registry, and runs `speca version` /
  `speca help` / `speca doctor` plus an `npx` route check. Catches
  tarball / bin-shim / dependency-pinning regressions the in-tree tests
  can't see.
- **Git-build install path** documented in `cli/README.md` and root
  `README.md` for contributors testing unreleased branches
  (`git clone && npm install && npm run build`, plus `npm link`).

## Tests

- 290 vitest cases (was 256 in v0.9.0) — +34 cases covering the new
  surfaces: errors-reporter (×13), preflight detectors (×10), browse
  error-kinds (×2), run pre-flight + phase warn (×5), verdict closed-set
  (×2), `speca ask` multi-turn chain (×2, closes [#31]).

## Issues closed

- [#28](https://github.com/NyxFoundation/speca/issues/28) — `ErrorKind`
  callers + run pre-flight checks
- [#31](https://github.com/NyxFoundation/speca/issues/31) — `speca ask`
  multi-turn chain coverage

## Install / upgrade

```bash
# Always-fresh
npx speca-cli@latest <command>

# Pin to this release
npx speca-cli@0.9.1 <command>

# Global install
npm install -g speca-cli
```

Requires **Node 20+**. For the audit pipeline you also need `uv`, `git`,
and `claude` (`speca doctor` checks all of them).

## Documentation

- [`cli/README.md`](https://github.com/NyxFoundation/speca/blob/main/cli/README.md) — usage guide
- [`cli/CHANGELOG.md`](https://github.com/NyxFoundation/speca/blob/main/cli/CHANGELOG.md) — full v0.9.1 entry
- [`cli/TESTING.md`](https://github.com/NyxFoundation/speca/blob/main/cli/TESTING.md) — manual test recipe
- [`docs/SPECA_CLI_SPEC.md`](https://github.com/NyxFoundation/speca/blob/main/docs/SPECA_CLI_SPEC.md) — design spec

---

**Full changelog:** https://github.com/NyxFoundation/speca/blob/main/cli/CHANGELOG.md

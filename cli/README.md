# speca-cli

> v0.9.0 (soft launch ahead of v1.0.0 GA) — TUI front-end for the
> [SPECA](https://github.com/NyxFoundation/speca) specification-anchored
> security-audit pipeline.

```bash
npx speca-cli@latest doctor    # one-shot environment check
npm install -g speca-cli       # global install
```

`speca auth login` → `speca init` → `speca run --target 04` is the typical
first-run loop.

## Documentation

End-user documentation, command reference, and the typical workflow live on
the SPECA documentation site:

→ **[https://nyx.foundation/speca/](https://nyx.foundation/speca/)**

Quick links:

- [インストール](https://nyx.foundation/speca/docs/getting-started/installation) · [クイックスタート](https://nyx.foundation/speca/docs/getting-started/quickstart)
- [監査ウォークスルー](https://nyx.foundation/speca/docs/tutorial/audit-walkthrough)
- [パイプライン概要](https://nyx.foundation/speca/docs/pipeline/overview)

## Internal references

- Implementation spec: [`docs/SPECA_CLI_SPEC.md`](../docs/SPECA_CLI_SPEC.md)
- Asciinema demo recordings: [`asciinema/`](asciinema/)
- Schema sync (Pydantic → JSON Schema): [`src/lib/schemas/generated/`](src/lib/schemas/generated/)
- Tests: `npm test` (vitest); coverage: `npm run test:coverage`
- Type-check: `npm run typecheck`
- Build: `npm run build`

## License

MIT — see the project's top-level [`LICENSE`](../LICENSE).

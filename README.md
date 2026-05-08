<p align="center">
  <img src="assets/speca_logo.png" alt="SPECA logo" width="240" />
</p>

<h1 align="center">SPECA: A Specification-to-Checklist Agentic Auditing Framework</h1>

<p align="center">
  <a href="https://arxiv.org/abs/2604.26495"><img src="https://img.shields.io/badge/arXiv-2604.26495-b31b1b.svg" alt="arXiv"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://github.com/NyxFoundation/speca/actions"><img src="https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
</p>

> **Paper:** Masato Kamba, Hirotake Murakami, Akiyoshi Sannai. *Beyond Code Reasoning: A Specification-Anchored Audit Framework for Expert-Augmented Security Verification.* arXiv preprint [arXiv:2604.26495](https://arxiv.org/abs/2604.26495), 2026.

**SPECA** is a specification-anchored security audit framework that derives explicit, typed security properties from natural-language specifications and audits implementations through structured **proof-attempt** reasoning. Where code-driven auditors look for known bug patterns, SPECA invents a property vocabulary from the spec and asks each implementation to prove the invariants — turning specification-level violations into detectable, traceable findings.

📖 **Documentation:** [https://speca.pages.dev/](https://speca.pages.dev/)<br>
🧪 **Dataset (audit findings):** [`NyxFoundation/vulnerability-reports`](https://huggingface.co/datasets/NyxFoundation/vulnerability-reports) on HuggingFace<br>
📦 **CLI on npm:** [`speca-cli`](https://www.npmjs.com/package/speca-cli)

## Headline results

- **Sherlock Ethereum Fusaka Audit Contest** (366 submissions, 10 implementations): SPECA recovers **all 15 in-scope H/M/L** vulnerabilities and discovers **4 novel bugs confirmed by developer fix commits**, including a cryptographic invariant violation missed by all 366 contest auditors.
- **RepoAudit C/C++ benchmark** (15 projects, 35 ground-truth bugs): SPECA matches the best published precision (**88.9%** with Sonnet 4.5) while surfacing **12 author-validated candidates beyond ground truth** — 2 confirmed by upstream maintainers.
- **All false positives** in deep analysis (N=16) trace to **three interpretable root causes** mapped to specific pipeline phases — not the usual "the model thought this was a bug" opacity.

## Quick start

```bash
# Bootstrap with the TUI (recommended)
npx speca-cli@latest doctor    # check toolchain
npx speca-cli@latest init       # create BUG_BOUNTY_SCOPE.json + TARGET_INFO.json
npx speca-cli@latest run --target 04

# Or run the orchestrator directly
git clone https://github.com/NyxFoundation/speca.git && cd speca
npm install -g @anthropic-ai/claude-code
uv sync && bash scripts/setup_mcp.sh
uv run python3 scripts/run_phase.py --target 04 --workers 4
```

Outputs land in `outputs/<phase>_PARTIAL_*.json`. Browse with `speca-cli browse outputs/04_PARTIAL_*.json`.

Full setup details → **[Installation](https://speca.pages.dev/docs/getting-started/installation)** · **[Quickstart (5 min)](https://speca.pages.dev/docs/getting-started/quickstart)**.

## Documentation

All detailed documentation is unified on the documentation site at
[https://speca.pages.dev/](https://speca.pages.dev/). Source
markdown lives under [`website/docs/`](website/docs/). The site is
bilingual — Japanese is the default locale; English is selectable via
the locale dropdown.

| Topic | Page |
|---|---|
| What SPECA is and why | [Beginner's guide](https://speca.pages.dev/docs/guide/what-is-speca) · [How it works](https://speca.pages.dev/docs/guide/how-it-works) · [FAQ](https://speca.pages.dev/docs/guide/faq) |
| Hands-on tutorial | [Audit walkthrough](https://speca.pages.dev/docs/tutorial/audit-walkthrough) |
| Pipeline phases | [Overview](https://speca.pages.dev/docs/pipeline/overview) → [01a Spec discovery](https://speca.pages.dev/docs/pipeline/01a-spec-discovery) → [01b Subgraph](https://speca.pages.dev/docs/pipeline/01b-subgraph-extraction) → [01e Property](https://speca.pages.dev/docs/pipeline/01e-property-generation) → [02c Code resolution](https://speca.pages.dev/docs/pipeline/02c-code-resolution) → [Audit map](https://speca.pages.dev/docs/pipeline/audit-map) → [Review](https://speca.pages.dev/docs/pipeline/review) |
| Concepts | [Spec-driven auditing](https://speca.pages.dev/docs/concepts/spec-driven) · [Proof-attempt](https://speca.pages.dev/docs/concepts/proof-attempt) · [Gate review](https://speca.pages.dev/docs/concepts/gate-review) · [Bug-bounty scope](https://speca.pages.dev/docs/concepts/bug-bounty-scope) |
| Operations (datasets / benchmarks) | [Overview](https://speca.pages.dev/docs/operations/overview) · [Refresh dataset](https://speca.pages.dev/docs/operations/dataset-refresh) · [Release artifacts](https://speca.pages.dev/docs/operations/release-artifacts) · [RQ1](https://speca.pages.dev/docs/operations/benchmark-rq1) · [RQ2](https://speca.pages.dev/docs/operations/benchmark-rq2a) · [RQ2b](https://speca.pages.dev/docs/operations/benchmark-rq2b) |
| Project layout | [Project structure](https://speca.pages.dev/docs/project-structure) |
| References | [Paper (Fusaka)](https://speca.pages.dev/docs/references/paper-fusaka) · [Paper (multi-impl)](https://speca.pages.dev/docs/references/paper-multi-impl) |

## Repository layout

```
speca/
├── scripts/             # Orchestrator + phase entry points + datasets/ pipeline
├── prompts/             # Per-phase worker prompts
├── benchmarks/          # RQ1 / RQ2 / RQ2b harnesses + paper figures
├── cli/                 # speca-cli (Node + Ink TUI)
├── website/             # Docusaurus documentation source (deployed at speca.pages.dev)
├── tests/               # pytest suite
└── outputs/             # Phase outputs (gitignored)
```

## Contributing

Issues and pull requests welcome. Please follow the conventions documented in
[`AGENTS.md`](AGENTS.md) (if present) and [`CLAUDE.md`](CLAUDE.md). Topic
branches off `main`; CI runs the test suite on every push.

```bash
uv run python3 -m pytest tests/ -v --tb=short
```

For onboarding a new target, you typically only need to write a `BUG_BOUNTY_SCOPE.json` and `TARGET_INFO.json` — no code change required. See [Bug-bounty scope](https://speca.pages.dev/docs/concepts/bug-bounty-scope) for the schema.

## Citation

```bibtex
@misc{kamba2026speca,
  title         = {Beyond Code Reasoning: A Specification-Anchored Audit Framework for Expert-Augmented Security Verification},
  author        = {Kamba, Masato and Murakami, Hirotake and Sannai, Akiyoshi},
  year          = {2026},
  eprint        = {2604.26495},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CR},
  url           = {https://arxiv.org/abs/2604.26495}
}
```

## License

SPECA is released under the [MIT License](LICENSE).

> **Disclaimer.** SPECA is a research artifact. Findings produced by the pipeline are *candidate* vulnerabilities and **must** be validated by a human auditor before being reported to a vendor or bug-bounty program. The maintainers make no warranty as to the completeness or correctness of any audit produced by this software.

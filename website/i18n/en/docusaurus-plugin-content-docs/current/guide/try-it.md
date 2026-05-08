---
sidebar_position: 3
---

# Try it now

A 5-minute walkthrough for trying SPECA.

## Prerequisites

- Node.js 20 or later
- The Python environment manager `uv` ([install](https://docs.astral.sh/uv/getting-started/installation/))
- Git
- Claude Code CLI ([install](https://claude.ai/download); a free tier is available, but a Claude Pro or Max subscription is recommended for running audits)

## Step by step

### 1. Clone the repository

```bash
git clone https://github.com/NyxFoundation/speca.git
cd speca
```

### 2. Set up the Python environment

```bash
uv sync
```

Installs the Python packages required by the project.

### 3. Build the CLI tool

```bash
cd cli
npm install
npm run build
cd ..
```

Builds the Node.js command-line tool (speca-cli).

### 4. Verify your environment

```bash
node cli/dist/cli.js doctor
```

Checks whether each dependency — Node.js, Python, and the Claude API — is correctly configured. If any error appears, follow the message displayed to fix the issue.

### 5. Initialize the project configuration

```bash
node cli/dist/cli.js init
```

Interactively prompts for the URL of the target repository, the security scope, and similar information. This generates `outputs/TARGET_INFO.json` and `outputs/BUG_BOUNTY_SCOPE.json`. These two files serve as the inputs to the entire pipeline.

### 6. Run the audit

```bash
node cli/dist/cli.js run --target 04
```

Executes Phase 01a through Phase 04 in sequence. The run takes anywhere from a few minutes to several tens of minutes. Progress is shown in the terminal in real time.

### 7. Review the results

```bash
node cli/dist/cli.js browse
```

Displays the candidate vulnerabilities that were detected. Each entry includes its code location, the security property, a severity, and a verdict.

## Troubleshooting

### The run ends with "Empty results"

`outputs/BUG_BOUNTY_SCOPE.json` may be missing or empty. Check the following.

- Did you run `speca init` to generate the configuration file?
- Does the target repository's GitHub Issues or Wiki contain specification information?

For more details, see the "specs not found" entry in the [FAQ](faq.md).

### Other errors

Consult the [FAQ](faq.md) or report the issue on [GitHub Issues](https://github.com/NyxFoundation/speca/issues).

## Next steps

- Learn how to read the results in detail: [Concepts](../concepts/spec-driven.md)
- Command reference: [Quickstart](../getting-started/quickstart.md)
- Frequently asked questions: [FAQ](faq.md)

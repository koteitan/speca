# Security Agents

An automated security analysis system using LLMs for comprehensive Bug Bounty research and vulnerability assessment.

## Overview

This system performs multi-phase security analysis for blockchain projects, specifically designed for Bug Bounty programs. It uses LLMs with WebSearch capabilities to analyze Bug Bounty scopes, technical specifications, and generate attack scenarios.

## Security Audit GitOps Workflow

This repository uses a **GitOps** approach to manage security audits for multiple target repositories. Each target has its own dedicated branch in this repository, which acts as the configuration source and the "baseline" for findings.

### Architecture

1.  **Config Branch**: A branch named `audit/<target_name>` (e.g., `audit/geth`) exists in this repo. It contains a customized `.github/workflows/audit.yml`.
2.  **Trigger**:
    *   **Schedule**: Runs daily (`cron`).
    *   **Manual**: `workflow_dispatch`.
    *   **Config Update**: Pushing to `audit/*` branch.
3.  **Process**:
    *   Clones the Target Repository.
    *   Runs Claude-based security audit.
    *   Creates a snapshot of findings in a new branch: `runs/<target_name>/<date>_<sha>`.
    *   Opens a **Pull Request** from the snapshot branch to the config branch (`audit/<target_name>`).
4.  **Review**: You can review the PR to see *what has changed* in the security posture (new findings vs previous baseline).

## How to Add a New Audit Target

1.  **Create a Branch**:
    *   Checkout `master` (or start fresh).
    *   Create a new branch: `audit/my-target-repo`.
2.  **Configure**:
    *   Edit `.github/workflows/audit.yml` **in that new branch**.
    *   **Uncomment** the `on: schedule` and `on: push` blocks to enable automation.
    *   Update the `env` section:
        ```yaml
        env:
          TARGET_REPO: "owner/my-target-repo"
          TARGET_REF: "main"
          # ... other settings
        ```
3.  **Push**:
    *   Push the branch: `git push origin audit/my-target-repo`.
    *   The CI will immediately run.
4.  **Wait for PR**:
    *   After the audit completes, a PR will be created targeting your branch `audit/my-target-repo`.
    *   This PR contains the initial audit results in the `outputs/` directory.

## Requirement

Before using this agent locally, please setup below tools.

- Claude Code or Codex
- [Serena MCP](https://github.com/oraios/serena/blob/main/README.md#running-the-serena-mcp-server)
- Web Search

## How to use

Follow [Hacking Guideline](./HACKING_GUIDELINE.md).
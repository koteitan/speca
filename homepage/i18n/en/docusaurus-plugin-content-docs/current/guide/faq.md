---
sidebar_position: 4
---

# Frequently asked questions

## My audit ends with "Empty results"

`outputs/BUG_BOUNTY_SCOPE.json` may be missing or empty. Verify that you ran `speca init` to generate the configuration file. Also check whether the target repository has specification information (a GitHub bug bounty page, Issues, Wiki, etc.); if not, create the JSON file by hand.

## Can I use it without a Claude subscription?

The Claude Code CLI itself can be installed for free, but running an audit invokes the Claude API and incurs usage charges. Subscribing to Claude Pro or Max keeps the monthly cost fixed. See [Claude.ai](https://claude.ai) for details.

## My target is not Solidity. Can I still use SPECA?

Yes. SPECA supports multiple languages including Go, Rust, Nim, TypeScript, and C. Any system governed by a specification can be audited, regardless of language.

## I get a large number of results and cannot tell which are important

Each finding has a `severity` and a `verdict`. `CONFIRMED_VULNERABILITY` is the highest-confidence result; `CONFIRMED_POTENTIAL` indicates a potential risk; and `DISPUTED_FP` may be a false positive. Use the `browse` command's filter options (such as `--severity high`) to narrow the list.

## I see an error saying "specs not found"

`outputs/TARGET_INFO.json` or `outputs/BUG_BOUNTY_SCOPE.json` does not exist or is empty. Check the following.

- Did you run `speca init` to create the configuration files?
- Is there specification information on the target repository's bug bounty scope page, Issues, or Wiki?
- Create the JSON files by hand if necessary.

For details, see the [Quickstart](../getting-started/quickstart.md).

## How long does an audit take?

It depends on the size and complexity of the codebase, but a small repository typically takes 5-15 minutes, while a large project can take an hour or more. The `run` command displays progress in real time, so you can do other work in parallel.

## Other questions?

Please ask on [GitHub Issues](https://github.com/NyxFoundation/speca/issues).

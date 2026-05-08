---
sidebar_position: 1
---

# What is this?

SPECA is a tool that automatically checks whether the code you have written behaves "as the specification says it should."

## How it differs from traditional code-analysis tools

Static analyzers and linters (such as eslint) check "rules about how code is written" — for example, "are variable types correct?" or "are there any unused variables?" These are useful, but they do not verify "the behavior prescribed by the specification."

SPECA reasons in the opposite direction. It first reads the specification, decides "this is the kind of processing required here," and then compares it against the implemented code to look for "mismatches." The starting point is what the specification requires, not what the code looks like.

## A specification-first mindset

Suppose, for instance, the specification of some system states: "Access to confidential data is permitted only after user authentication." SPECA verifies this through the following steps.

1. Read the specification and recognize that this is an important security requirement.
2. Locate which parts of the code implement this requirement.
3. Try to prove that the order "authentication → data access" is preserved on every execution path.
4. If any portion (a gap) cannot be proven, report it as a candidate vulnerability.

## Intended audience

- **Security auditors** who want to reduce the manual effort of cross-checking specifications against code.
- **Bug bounty hunters** who want to find implementation gaps efficiently in large codebases.
- **Development teams** who want to periodically confirm that their software is implemented in accordance with its requirements.

## Next steps

For a more detailed look at the mechanics, continue to [How it works](how-it-works.md).

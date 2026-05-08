---
sidebar_position: 1
---

# Why we went spec-driven

## What code-only tools miss

Before building SPECA, the first prototype I wrote was an ordinary "look at the code and find bugs" style. The approach was to hand a repository to an LLM and say "find the bugs." The result was an 88% false-positive rate.

What I realized at that moment was that the LLM was enumerating places that "felt suspicious" without any basis to judge whether the code was correct or not. It can only guess from surface-level form. Without grounding, you cannot stop the false positives from piling up.

On the other hand, what was missed? When I checked afterward against the Ethereum Fusaka contest, one of the missed defects was a violation of a mathematical invariant in KZG batch verification. Looking at the code's surface, nothing looks suspicious. What is being violated is "what the equations in the specification require," not a code pattern. The 366 audit submissions also missed it.

Here is another example. In a certain access-control implementation, every function appeared on the surface to have an `onlyOwner` modifier. But the specification said "during the initialization phase only, some operations are callable by anyone." The code did implement that exception, but the definition of when that exception ends diverged between the spec and the implementation. Looking at code alone, you would conclude "modifier present = OK" and stop there.

## Path to the idea of reading the specification

If the code provides no grounding, then bring grounding from somewhere else — that is the starting point.

Specifications contain statements of the form "under these conditions, this processing must be performed." If you formalize them, you can build a list of "things that must be proved." Instead of asking whether the code is correct, change the question to "prove that this condition holds." When parts cannot be proved (proof gaps), those become candidate detections.

What changed with this turn? When a false positive appears, you can explain "why it is a false positive" with grounding. You can trace which property and which phase's judgment was wrong.

## Three situations where spec-driven works

**1. When you want to compare multiple implementations under the same criterion**  
In Ethereum, multiple client implementations exist for the same specification (EIP). With different codebases, ordinary scanning tools cannot make a cross-cutting comparison. SPECA uses properties built from the specification as a common criterion, so it can apply the same conditions to ten implementations and compare them. In Fusaka, we did this against ten implementations.

**2. When you want to check invariants the spec requires**  
Requirements of the kind "this function must always satisfy this precondition" are mostly not written in the code as comments. Read the specification and they are written there. SPECA extracts them as properties and verifies them.

**3. When you want to analyze the cause of false positives**  
SPECA's false positives could be classified into three kinds: "trust-boundary misunderstanding," "code misreading," and "spec misinterpretation." Once you know the kind, you also know where in the prompt or filter to fix. False positives that come without grounding are hard to improve, because you do not know where to fix.

## Limits of spec-driven

Honest disclaimers.

It cannot be used on projects that have no specification. With only code, no documentation, and no issues, SPECA cannot find a foothold.

It is also difficult when the specification itself contains bugs. If the spec is wrong, the properties built from it are also wrong. "Verifying that the implementation matches the spec" presupposes that the spec is correct.

In addition, when a specification is too ambiguous, the quality of the properties Phase 01e generates degrades. Wording like "handle appropriately" or "implement safely" makes it hard to construct verifiable conditions.

Even so, when the target system has a specification and it is reasonably concrete, we believe this direction is effective.

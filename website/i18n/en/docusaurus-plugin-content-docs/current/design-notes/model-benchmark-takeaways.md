---
sidebar_position: 2
title: Notes on model selection — reading the paper's RQ2 ablation
---

# Notes on model selection — reading the paper's RQ2 ablation

:::note
This is hirorogo's personal interpretation, not the official view of Nyx Foundation or the paper authors. The numbers themselves, as published in the paper (arXiv:2604.26495), are accurate; the takeaways drawn from them (which model fits which situation, what is interesting) are subjective.
:::

"Newer model = better" is intuitively right most of the time, but reading the RQ2 ablation in SPECA's paper, there are movements in the numbers that this alone does not explain. Here is my reading.

## Looking at the RQ2 ablation table

RQ2 in the paper is a per-model performance comparison on the RepoAudit C/C++ benchmark. The model in charge of Phases 4-6 (verification phases) is swapped out, and accuracy, cost, and number of findings are measured.

| Model | Precision | F1 | Cost | Novel findings |
|--------|------|-----|--------|---------|
| Claude Sonnet 4.5 (SPECA recommended) | 88.9% | 0.94 | $81.05 ($1.69/bug) | 12 |
| Claude 3.7 Sonnet | 88.9% | 0.94 | $23.85 | — |
| Claude Sonnet 4 (previous generation) | 81.2% | — | $100.68 | 18 |
| Claude 3.5 Sonnet (public baseline) | 78.4% | — | $38.10 | — |
| o3-mini | 80.0% | — | $4.50 | — |
| DeepSeek R1 | 72.7% | — | $93.51 | 7 |
| Meta Infer (static analysis) | 77.8% | — | — | — |
| Amazon CodeGuru (static analysis) | 0.0% | — | — | — |

The first thing that catches the eye is the range of accuracy. From the highest Sonnet 4.5 / Claude 3.7 Sonnet (88.9%) down to DeepSeek R1 (72.7%) is a 16.2pp gap. "Just plugging a different model into the same pipeline" produces this much difference.

## The stronger the model, the more it respects property scope

This is the part I found interesting.

Sonnet 4.5: 88.9% precision, 12 novel findings. Sonnet 4 (previous generation): 81.2% precision, 18 novel findings. Precision goes down as novel findings go up.

This looks paradoxical, but the paper's interpretation is clear. Stronger models reason while faithfully respecting the property's scope, so they intentionally do not pick up "real bugs in adjacent territory" that lie outside the property's specified range. Weaker models, on the other hand, drift outside the scope and read peripheral code that the property never anticipated. As a side effect, they sometimes incidentally detect real bugs outside the scope.

It is not accurate to say "the weaker model earned the novel findings." The reality is: "because scope adherence is loose, it scanned outside the scope." If you want to deliberately broaden coverage, broadening the property-side scope definition is more reproducible.

The paper expresses this situation as follows.

> "property-generation quality, not model reasoning, as the binding constraint on coverage"

No matter how strong the Phase 4-6 model becomes, coverage cannot extend beyond the range of properties generated in Phases 1-3 — that structural limit shows here.

## DeepSeek R1 dismisses with counterfactual reasoning, on the strict side

DeepSeek R1's numbers are 72.7% precision, 7 novel findings, $93.51 cost. Precision is at the bottom, and cost is second only to Sonnet 4 ($100.68). On cost-performance, it is the worst result.

Another point the paper notes is the difference in judgment on contested bugs (5 borderline cases that RepoAudit flagged as "to be fixed"). Sonnet 4.5 dismissed 4 of 5 as "no exploitation path." Sonnet 4 detected 4 of 5. DeepSeek R1 dismissed all 5.

Using the same pipeline and the same properties, judgments on contested bugs diverge this much across models. I think this shows that there is model-dependent variation in counterfactual-reasoning style (the reasoning of "is there a case where this condition does not hold?"). When dealing with codebases full of contested points, this tendency is worth keeping in mind.

## An unexpected winner on cost-efficiency

Claude 3.7 Sonnet posts the same 88.9% precision and the same F1 of 0.94 as Sonnet 4.5 at $23.85. That is less than 1/3 of Sonnet 4.5's $81.05. The breakdown of novel candidates is not made explicit in the paper, but on precision and F1 alone it is on par.

If you want to prioritize cost without dropping benchmark precision, Claude 3.7 Sonnet is a realistic choice.

The cheapest is o3-mini at $4.50. With 80.0% precision it surpasses the static-analysis baseline Meta Infer (77.8%). For screening use cases where many repositories are processed in bulk, $4.50 is a non-negligible cost difference.

## Opus up front, Sonnet downstream

In SPECA's design, Claude Opus and Claude Sonnet 4.5 split the work. Opus handles knowledge structuring in Phases 1-3. Its job is to read the spec and extract properties. Sonnet 4.5 handles verification in Phases 4-6. Its job is to apply properties built by Opus to implementation code and look for proof gaps.

Within the same Claude family, the front end (which requires precise spec understanding) and the back end (which requires code matching and reasoning) are split. This division aligns with the paper's finding that "the property's quality is what binds coverage." Strengthening the front-end model raises the range and quality of properties, expanding the verification space the back-end model can leverage.

## In one line

Practical guidance to draw from the ablation:

- **For precision, Sonnet 4.5; for cost, Claude 3.7 Sonnet**. Same 88.9% precision at $23.85 vs $81.05.
- **The number of novel findings is more about property scope definition than model strength**. To broaden coverage, revisit the front-end property generation rather than swapping the back-end model.
- **For codebases full of contested bugs, watch DeepSeek R1's tendency to dismiss**. A pattern of dismissing everything may reflect a model-specific tendency rather than a pipeline issue.
- **For screening use, o3-mini ($4.50) is also an option**. 80.0% precision beats the static-analysis baseline.

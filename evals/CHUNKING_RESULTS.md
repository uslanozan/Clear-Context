# Chunked extraction development check

October 27, 2026. Three selected corpus inputs, one final pass per model: altered Curie,
Mars moon-origin uncertainty, and Turkish Cappadocia. Reference answers were not included
in inference. This is a small development check, not a benchmark or a model ranking.

Both models used prompt v2, a 600-character initial target budget, bounded head/neighbor
context, capacity 24 per response, and 4,096 completion tokens. Per-document limits were
24 calls, 32,768 output tokens, and 120 seconds. These limits are provisional.

| Case | Spark 1.3: spans / outcome | Wonder: spans / outcome |
| --- | --- | --- |
| Altered Curie | 62 / partial | 87 / processed |
| Mars moon-origin uncertainty | 6 / processed | 6 / processed |
| Cappadocia, Turkish | 15 / processed | 18 / processed |

Both models included the deliberately altered Chemistry award year, 1921. Spark's first
Curie target had an invalid output and remained explicitly partial. Wonder processed all
target ranges. More spans do not establish better decomposition, truth, or exhaustive
recall; statement granularity, semantic grounding, and duplicate meanings need review.

The runs used 12 Spark and 10 Wonder requests. Individual receipts, input text, exact
source/context positions, interpreted statements, coverage trees and usage remain under
ignored `evals/runs/`. No truth judging or source research was performed.

Earlier tuning attempts exposed two issues: keeping capacity eight per response caused
excessive subdivision, and rejecting every boundary-crossing quote excluded visible,
contiguous source sentences. V2 uses a larger response capacity and allows quotes only
within actually supplied contiguous text windows that overlap target. Context-only or
unseen-gap quotations remain invalid. Raw earlier attempts were retained separately.

Processing status means a model returned a structurally accepted result for each target;
it does not certify that every factual claim was identified. Write-error variants remain
deferred. No automated accuracy score is claimed.

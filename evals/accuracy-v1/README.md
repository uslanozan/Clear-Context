# Accuracy set v1

Thirty short claims with known answers, run once through the app on November 10, 2026
(balanced research, Muse Spark 1.3, the defaults of version 1.0.0, no changes for the test).

- `cases.json`: the claims and their labels: 10 true, 10 false, 7 half-true (one detail is
  wrong; `target` names it) and 3 that no source can settle (an opinion, a dream, a private
  event). 20 are in English and 10 in Turkish. The labels were written by hand from general
  knowledge before the run.
- `scores-2026-11-10.json`: the outcome of each case as `evals/score_accuracy.py` counts it,
  with the detail results, model cost and time. The full reports stay local because they
  quote third-party pages.

Rules: a true claim is correct when a detail is supported and none is contradicted; a false
or half-true claim is correct when a detail is contradicted; an unsettleable claim is
correct when nothing is supported or contradicted. Anything else is unsettled (insufficient
evidence, not assessed, failed run) or wrong. For the false and half-true claims the
contradicted detail was also checked by reading the reports: in every case it was the
labeled one, and the supported details were the true parts.

Result: 28 correct, 2 unsettled, 0 wrong. Both unsettled cases (`T08`, `F06`) lost a correct
judgment because the citation check rejected quotes that differed from the page only by a
non-breaking space or a line break. Model cost was $1.40 in total ($0.05 per claim on
average) and a run took 45 seconds on average.

This is a small set of well-known facts, run once with one model. It shows the method works
on simple claims; it is not a benchmark and says little about long posts, recent events,
images or video.

Rerun with a server in paid mode:

```powershell
.\.venv\Scripts\python.exe evals/run_accuracy.py evals/accuracy-v1/cases.json evals/runs/accuracy-v1/results --budget 8 --execute
.\.venv\Scripts\python.exe evals/score_accuracy.py evals/runs/accuracy-v1/results
```

# Evaluation plan

The specifications in `case-specs.json` describe cases to collect; they are **not** a finished dataset or measured results.

Before scoring any case, attach source URLs, access dates, a human-written bounded claim, expected evidence, and permission/license notes for assets. Use openly licensed or self-created image assets. No fabricated source URLs, citations, or benchmark numbers.

## Initial set

Collect 10 cases covering straightforward support, contradiction, omitted context, image reuse, uncertainty, duplicate reporting, inaccessible sources, misleading excerpts, hostile source instructions, and corrected input.

Use controlled local fixtures for deterministic failure/security scenarios, label them synthetic, and keep real-web examples for the demonstration. A controlled fixture is not evidence of broad real-world accuracy.

## Review dimensions

1. Does claim decomposition preserve the original qualifications?
2. Does each quotation appear in the retrieved source at the stated location?
3. Does the cited evidence support the exact finding?
4. Are image context and event claims assessed independently?
5. Does the system retain uncertainty when the evidence is insufficient?
6. Does it recognize copied sources and access failures?
7. Does a correction trigger an appropriate update?
8. What are the observed latency, tool calls, and model costs?

Record per-case outputs and review notes. Report numerator/denominator counts and failures. Ten cases are a development check, not a validated general accuracy claim. Budget and latency targets will be set after measuring the first working examples.

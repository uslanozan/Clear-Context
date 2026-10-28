# Prompt management

Instructions live in [config/prompts.yaml](../config/prompts.yaml). Only claim extraction
currently calls a model. Evidence evaluation and report validation do not use prompts.

| Setting | Default | Purpose |
| --- | --- | --- |
| `PROMPT_CATALOG_PATH` | `config/prompts.yaml` | Project-relative or absolute catalog path |
| `PROMPT_CLAIM_EXTRACTION` | `v2` | Select an extraction contract version |
| `EXTRACTION_RESPONSE_CAPACITY` | `24` | V2 per-response capacity, not a document claim limit |
| `META_MAX_CLAIMS` | `8` | V1 legacy single-call limit only |

Both versions render `${max_claims}` from their corresponding capacity setting. V1 uses a
single string-list response. V2 uses exact quotes, interpreted statements, context quotes,
ambiguity, and a `has_more` signal within bounded chunk processing. Add future v2-compatible
instruction variants under a new version; v1 remains the explicit legacy contract.

Catalogs are validated at application creation in mock and Meta modes. Invalid templates,
unknown versions, or missing files stop startup. Restart after changing configuration.
There is no hot reload inside an existing provider.

User text is never a template. V2 sends target and context as user-message JSON; its system
instruction treats both as untrusted content. Schemas, source anchoring, chunk decisions,
HTTP guards, and budgets remain Python responsibilities.

Usage records store prompt version and SHA-256 of the rendered system instruction, model,
reported tokens, source range, and call outcome. The hash includes response capacity, not
submitted text. It does not capture every inference parameter; the evaluation runner also
records limits and input hashes. Historical records remain readable.

Use the same cases and budgets when comparing models or prompts. Coverage status `processed`
means all target ranges reached a normal response, not that every claim was found.
See [text analysis](TEXT_ANALYSIS.md) for the implemented contract and limitations.

## Experimental extraction instructions

The same catalog now includes an optional `experiments` mapping. Named entries hold a
`system` instruction, synthetic `few_shot_examples`, and an optional `missing_check`.
These use the local experiment response schema and are not selected by
`PROMPT_CLAIM_EXTRACTION`; the live v1/v2 contracts remain separate. Local runners
read named entries from this catalog. Experiment-local YAML files are historical
snapshots only. The user-facing review is `docs/local/experiments/claim-extraction-bcd-v2/review.html`.

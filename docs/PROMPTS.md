# Prompt management

Model instructions live in [config/prompts.yaml](../config/prompts.yaml). Currently only
`claim_extraction` calls a model. Evidence evaluation remains deterministic and unresolved
without sources; report validation and persistence do not need prompts.

| Setting | Default | Purpose |
| --- | --- | --- |
| `PROMPT_CATALOG_PATH` | `config/prompts.yaml` | YAML file, relative to the project root or absolute |
| `PROMPT_CLAIM_EXTRACTION` | `v1` | Version under `prompts.claim_extraction.versions` |
| `META_MAX_CLAIMS` | `8` | Supplies the `${max_claims}` placeholder and the JSON schema limit |

The catalog is validated at application creation in both mock and Meta modes. Invalid
templates, unknown versions, or a missing file stop startup. Restart the backend after
editing the catalog or settings; there is no hot reload of prompts inside a provider.

The system instruction is rendered once from trusted configuration. Submitted text stays
in a separate user message and is never used as a template. Output schemas, token limits,
exact-substring checks, and evidence validation remain Python responsibilities.

Each successful extraction stores `prompt_version` and `prompt_sha256` with model/token
usage. The hash covers the rendered system instruction, including the configured claim
limit, and contains no submitted text. Existing records without these fields still load.
These fields identify the instruction; they do not capture every inference parameter or
constitute a complete evaluation record.

To compare prompts, add a new version such as `v2`, retain the previous version, select
it in `.env`, and restart. Keep the same reviewed examples and record model, limits, and
results. Changing a prompt is not evidence of improved extraction quality.

Model selection remains independent through `MODEL_CLAIM_EXTRACTION` and the model
catalog. Future model-calling tasks can receive their own validated templates when their
nodes are implemented; the current catalog intentionally contains no placeholder tasks.

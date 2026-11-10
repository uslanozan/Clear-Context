# Models

Catalog: [config/models.yaml](../config/models.yaml). Prices checked November 10, 2026, in USD; access depends on the account. Recommendations are starting points, not benchmark winners. One extraction connectivity smoke test was run October 27; no comparative evaluation exists yet.

## Catalog and prices

Token prices are per **1M tokens**, in input / cached input / output order.

| Model | Candidate use | Price / access |
| --- | --- | --- |
| Muse Wonder | Difficult evidence conflicts, long research and review | $4 / $0.20 / $20 |
| Muse Wonder Full | Advanced development in Muse Code | Subscription only; unavailable to our API backend |
| Muse Spark Open | Open-weight research and source comparison experiment | Self-hosted or partner; provider-specific cost |
| SAM 3.1 | Locate, segment and track objects | $2.50/1,000 images; $0.20/1,000 video frames, minimum 50 frames/request |
| Muse Spark 1.3 | Default extraction, screenshots, research and reports | $1.25 / $0.15 / $4.25 |
| Muse Spark 1.3 Contributor | Same capabilities with explicit training-use permission | $0.10 / $0.002 / $0.20; select countries |
| Muse Voice Transcribe | Optional audio-to-text input | $0.18/audio hour |
| Muse Image 1.0 | Generate/edit visuals; outside verification | $0.01/generated image |
| Muse Glimmer | Optional local-agent experiment | Apache 2.0; self-hosted compute cost |
| Muse Spark 1.2 | Earlier version; audio/comparison baseline | $1.25 / $0.15 / $4.25 |
| Muse Spark 1.2 Contributor | Earlier discounted version with training-use permission | $0.10 / $0.002 / $0.20; select countries |
| Muse Spark 1.1 | Earlier multimodal/computer-use baseline | $1.25 / $0.15 / $4.25 |
| Muse Ember 1.0 | Listed by Meta after the hackathon; not in the catalog and not evaluated here | $0.10 / $0.004 / $0.50 up to 200K input tokens; $0.30 / $0.012 / $1.50 above |

The report shows an estimated model cost from the recorded token counts and these list prices (`GET /api/prices`). It leaves out search services and speech transcription, and free credits may cover it. A balanced run on the earthquake example recorded 49,968 input and 10,127 output tokens with Spark 1.3, about $0.10.

Standard mode does not use content to train Meta models; Contributor permits training use. Default to Standard for uploads. Spark 1.3 has an audio-quality caveat: use transcription or evaluate 1.2 for audio. Text-model web search adds **$2.50/1,000 queries** beyond tokens.

Promotional credit notice: the account dashboard states that content may be used for product improvement while free credits are in use. Do not infer the promotion's data handling solely from a Standard model ID or `store=false`. The first live test used self-created fictional text, not private project or personal data.

## Task choices to evaluate

| Input / task | Start with | Compare when needed | Measure |
| --- | --- | --- | --- |
| Statement/article: extract claims | Spark 1.3 | Wonder | Missing claims, preserved dates/qualifiers |
| User screenshot: text and visual context | Spark 1.3 | Wonder, Spark 1.1 | Text accuracy, caption/image separation |
| Research planning and tool use | Spark 1.3 | Wonder | Useful searches, failures, cost |
| Judge evidence support/contradictions | Spark 1.3 | Wonder | Citation errors, unsupported conclusions, unresolved cases |
| Final report | Spark 1.3 | Wonder | Faithfulness, clarity, latency |
| Audio, if added | Voice Transcribe -> Spark 1.3 | Spark 1.2 directly | Accuracy and total cost |

The judge reviews recorded evidence, not model consensus. Screenshot reasoning and SAM do not establish image provenance; retrieve source evidence separately. Switch defaults only when evaluation justifies it.

## Configuration

Copy [.env.example](../.env.example) to a local `.env`. Choose catalog aliases:

```dotenv
MODEL_DEFAULT=spark_1_3
MODEL_SCREENSHOT=spark_1_3
MODEL_JUDGE=wonder
```

Implemented resolution: non-empty task override -> `MODEL_DEFAULT` -> YAML default. Startup rejects unknown aliases, non-text investigation models, unsupported access methods and Contributor selection without explicit opt-in. No silent fallback. `/api/models` shows configured selections, not live account availability. Mock mode makes no calls; opt-in Meta mode currently calls only the extraction model. Judge/report selections are reserved for later evidence workflows. Image/audio-specific validation will be added with those input types.

Wonder/Spark support text, image, video, audio and PDF input with text output and a 1M context window. Check version caveats and account access before use. Spark Open/Glimmer need verified serving configuration, capabilities and provider API IDs; their aliases are not Meta API IDs. Wonder Full is not API-selectable.

Baseten is the first optional Spark Open comparison; Fireworks/Modal stay optional until an experiment requires them. Applying for credits does not require integrating every service.

## Experiment log

Append actual runs using comparable cases and prompts. Model self-grading alone does not establish quality.

| Date | Task / case set | Model / provider | Citation or extraction errors | Latency | Actual cost | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-27 | Claim extraction; one self-created fictional paragraph | Spark 1.3 / Meta | Two exact-span claims; no verification attempted | Not measured separately | Not reconciled with billing | Connectivity smoke passed; no quality ranking |
| 2026-10-27 | Synthetic Turkish date and quantity, live HTTP workflow | Spark 1.3 / Meta | Two exact-span claims retained the date and quantity | 4.09 s end to end | Not reconciled with billing | This case passed manual inspection |
| 2026-10-27 | Synthetic Turkish conditions and negation, live HTTP workflow | Spark 1.3 / Meta | Three spans retained age/student restriction, Tuesday-only condition, and negation | 4.06 s end to end | Not reconciled with billing | This case passed manual inspection |

The API reported 180 input, 409 output and 0 cached-input tokens. Listed Standard rates imply approximately $0.00196325 in token cost; this is an estimate, not a confirmed billing deduction. Local smoke details are excluded from Git.

The two live HTTP cases used 190/479 and 202/675 input/output tokens respectively, with zero cached-input tokens reported. Their combined listed-rate estimate is $0.0053945, not a confirmed billing deduction. Both persisted reports contained no sources/evidence and only unresolved findings. Two synthetic examples do not establish general extraction accuracy. Local details are excluded from Git.

No billable calls until credits are confirmed or a test budget is authorized. Bound steps, retries and tokens; record usage. Meta's spend alert sends email and does not stop requests.

Sources: [models](https://dev.meta.ai/docs/models), [pricing](https://dev.meta.ai/docs/pricing-rate-limits), [spend alerts](https://dev.meta.ai/help/billing/spend-limit-alert). Update YAML prices and this table together when rates change.

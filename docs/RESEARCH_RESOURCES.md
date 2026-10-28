# Research resources: claim extraction and verification

Notes for Clear Context, reviewed October 28, 2026. These resources inform experiments; they are not implemented requirements or proof of performance on Turkish inputs. Check licenses and attribution before reusing code or data.

## Claim extraction and coverage

- [Towards Effective Extraction and Evaluation of Factual Claims / Claimify (ACL 2025)](https://aclanthology.org/2025.acl-long.348/) — Evaluates whether claims follow from their source, cover verifiable content, and preserve context. The element-level coverage idea is directly relevant when one sentence contains several facts. Its evaluation focuses on LLM-generated responses; transfer to our multilingual inputs requires testing.
- [Claimify implementation overview (Microsoft Research)](https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/) — Describes sentence/context preparation, selecting checkable content, handling ambiguity, and claim decomposition. A useful design reference; no requirement to copy its complete multi-call pipeline.
- [Claimify annotated dataset (Microsoft)](https://huggingface.co/datasets/microsoft/claimify-dataset) — Human annotations for English LLM-answer sentences. Inspect scope and license before using; do not treat it as a ready-made Turkish claim-coverage benchmark.
- [Improving Recall of Large Language Models: A Model Collaboration Approach for Relational Triple Extraction (LREC-COLING 2024)](https://aclanthology.org/2024.lrec-main.778/) — Uses a smaller model to help find candidate entity relations in complex sentences. Relation triples are not identical to our claim task; the authors report remaining omissions/errors and additional inference time.
- [When Can LLMs Actually Correct Their Own Mistakes? (TACL 2024)](https://aclanthology.org/2024.tacl-1.78/) — Reviews self-correction and warns that prompted feedback is not reliably beneficial in every setting. Our source-backed omission check is related, not identical; measure whether it adds correct facts or creates errors.
- [LangExtract (Google)](https://github.com/google/langextract) — LLM-based structured extraction, source alignment, long-document processing, and visualization. It supports multiple extraction passes, which incur additional inference. Alignment does not establish truth or exhaustive extraction; exact and fuzzy matches must be distinguished.
- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172) — Reports position-sensitive performance in long-context tasks. This motivates measuring long inputs and positions, not assuming that any given Muse model fails in the same way.

## Evidence and verification

- [FActScore (EMNLP 2023)](https://aclanthology.org/2023.emnlp-main.741/) and [code](https://github.com/shmsw25/FAcTScore) — Decomposes generated text into atomic statements and assesses support against a knowledge source. Its factual precision metric does not establish extraction completeness; missing evidence does not automatically refute a claim.
- [FEVER: a Large-scale Dataset for Fact Extraction and VERification (NAACL 2018)](https://aclanthology.org/N18-1074/) — English Wikipedia-derived claims with supported, refuted, and not-enough-information labels and evidence annotations. Useful for evaluation design; it does not represent all Turkish, multimodal, or real-web cases.

## Proposed application to Clear Context

1. Evaluate extraction by source entailment, coverage of independently checkable elements, and preservation of context/uncertainty. Keep literal span matching as a separate mechanical check.
2. Review a small set of representative paragraphs, including complete outputs, missed facts, ambiguity, negation, dates, and noisy Turkish text. Reference annotations stay separate from model inputs.
3. Compare first-pass-only, bounded omission checking, and optional LangExtract multiple passes on the same cases. Track false additions, duplicates, missing elements, failures, calls, tokens, and elapsed time. A small pilot is not a general accuracy benchmark.
4. Keep an omission-checking pass optional until it demonstrates a meaningful benefit against cost; do not present processed ranges as proof of complete recall.
5. Prioritize a working source-retrieval and evidence-assessment path. Preserve supported, contradicted, and unresolved outcomes with claim-level provenance; the absence of evidence is not itself evidence of falsity.

## Current experimental boundaries

The local Marmaray omission check found five source-supported additions in one chosen paragraph. This is a useful pilot, not a measured recall improvement: there was no representative sample, negative-control set, or fully reviewed ground truth. Do not infer that LangExtract, a second pass, or a specific Muse model is generally superior from these trials.

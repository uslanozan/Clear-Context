# Web text development corpus v1

Collected on October 27, 2026. **36 inputs from 14 source pages. Collection used no model
calls.** This is a development draft, not a validated benchmark or an exhaustive
claim-extraction gold set.

The first subsequent local extraction baseline used Muse Spark 1.3 and prompt v1: 36
calls, 14 outputs passing current validation, 22 truncated outputs, and 50 accepted literal
claim spans. It retained the eight-claim and 1,024-completion-token limits. No accuracy
or factual-verification score was measured. Run artifacts are local under ignored
`evals/runs/`; the manifest's zero call/run counters describe collection, not later runs.

A subsequent explicit follow-up reran only the 22 truncated inputs at 4,096 completion
tokens with the same model, prompt, and eight-claim limit. All 22 passed current validation
and produced 148 spans. The combined view has 198 spans across 36 unique inputs, with
different completion budgets. This is not evidence of complete or accurate extraction.

| Dimension | Coverage |
| --- | --- |
| Languages | English 26, Turkish 5, Spanish 3, French 2 |
| Lengths | 11 short, 15 medium, 10 long |
| Length boundaries | Short <400 characters; medium 400-1,499; long >=1,500 |
| Selected target labels | 13 `true`, 13 `false`, 6 `unknown` |
| Additional natural passages | 4 interior windows with annotation pending |
| Topics | Music, biology, reefs, manuscripts, scientists, archaeology, geography, architecture, astronomy, earthquakes, water |
| Source types | Collaborative encyclopedia, government science, intergovernmental heritage, a fact-check quoting social media, personal research |

Topics and source types were chosen deliberately. Four interior Wikipedia windows use
seed `20261027`; this is **not a random sample of the web**. Other passages are intact
lead or selected paragraph windows. Original-language wording is retained; HTML markup
and whitespace normalization are recorded separately. Wikipedia revisions are pinned.

## Files and separation

- `inputs.jsonl`: only case ID, language, and submitted text. Send only these inputs to
  the investigation system, without the reference files or mutation hints. IDs are opaque
  and input order is shuffled; descriptive case names live only in the reference records.
- `reference/annotations.jsonl`: original text, source/group IDs, selected target spans,
  provisional labels, rationales, mutations, and collection offsets.
- `reference/sources.json`: source URLs, Wikipedia revisions, access timestamps, selected
  original passages, normalization rules, attribution, and license notes.
- `reference/evidence.json`: short corroborating excerpts inspected during collection.
- `manifest.json`: counts, seed, corpus state, and input-file hash.
- `reference/catalog.md`: readable case list for review.

This file separation is an evaluation convention, not an access-control boundary. A
future harness must explicitly construct inputs without loading labels into model context.
Reference files must not be indexed as research evidence. All current cases are development
data. When creating a held-out split, keep **all variants and windows of a source/group
together**. Related articles and shared evidence also require review for leakage.

## Label meaning

Labels apply to the **selected verification target**, not the entire passage:

- `true`: the collected evidence supports the bounded target.
- `false`: the collected evidence contradicts the bounded target.
- `unknown`: the reference package does not establish support or contradiction, or the
  underlying proposition is explicitly a hypothesis. This is not proof of unknowability.

All annotations are assistant-curated drafts requiring human review. Do not publish an
accuracy score against these labels without adjudicating them. An unreviewed claim is
**unannotated**, not automatically `unknown`. Other claims in a passage may be correct,
incorrect, outdated, ambiguous, or outside the selected annotation scope.

In uncertain cases, `quote` preserves the original wording and `verification_target`
identifies the underlying proposition. For example, an author saying that moons *may*
be captured asteroids is different from establishing that origin as fact. Preserve the
modal qualifier rather than judging the accurate quotation itself false.

The application still uses supported/contradicted/mixed/unresolved findings. This corpus
does not change that API contract or implement confidence scores; target confidence is
currently null. Compound and mixed claims need decomposition before applying three-way labels.

## Controlled changes

Examples include Mozart's age at death, Curie's Nobel year, a reef's country, a region in
Türkiye, a UNESCO inscription date, tower height, Mars' rotation period, an ocean-water
percentage, and probability versus exact prediction. Other variants add unsupported
personal details or change an unverified personal research measurement.

Every edit records the original substring and its location. A known edit does not make
the altered proposition automatically false: an unsupported detail remains `unknown`
until evidence supports or contradicts it. Each target also records an exact input span.
Offsets are zero-based Python Unicode code points, with exclusive ends, in the normalized
input, not HTML byte positions or JavaScript UTF-16 offsets.

The reference case named `earth-flat-quoted` is a real false claim extracted from Full Fact's claim box. It is
**not** an endorsement by Full Fact and is **not** a directly captured Instagram post.
The original social post was not retrieved. The personal research source is included as
an unverified empirical report; its measurements have not been independently reproduced.

## Caveats and next review

- Wikipedia is a source of natural text, not blanket ground truth. For example, the reef
  article and UNESCO use different area and reef-count figures; those were not promoted
  to gold claims merely because they appeared in the passage.
- The four interior windows are intentionally unannotated. Review referents that depend
  on preceding paragraphs, dates, qualifiers, and possible extraction omissions.
- Some targets have primary corroboration; others currently have only their source page.
  Evidence snapshots are excerpts, not a complete offline research index. Search results
  can change, and open-web retrieval may produce evidence that changes a draft label.
- Resolve labels and add exhaustive extraction annotations before comparing models. The
  current corpus supports inspection and future evaluation, not a claim-recall score.
- Media and deterministic security/failure fixtures remain separate work described in
  `evals/case-specs.json`; this text set does not finish those cases.

## Attribution and reuse

The text is not covered by an assumed repository-wide license. Wikipedia excerpts and
adaptations retain attribution to Wikipedia contributors and **CC BY-SA 4.0**, with author
history reachable from each pinned revision. UNESCO's short description and adaptation
retain attribution and **CC BY-SA 3.0 IGO**. Preserve the applicable share-alike terms for
those excerpts and adaptations. Source metadata identifies deliberately modified versions.

NASA, NOAA, and USGS selections contain agency text only; US-government material is
generally public domain in the United States, subject to third-party exceptions and
applicable local law. No logos, images, or third-party credits are copied here. Full Fact
and the personal research page contribute only short attributed quotations; no open
license or blanket permission is claimed for them. Reassess those quotations before
broader redistribution. License URLs and attribution belong with exported samples.

Validate local integrity without network access or inference:

```powershell
.\.venv\Scripts\python.exe evals/validate_corpus.py
```

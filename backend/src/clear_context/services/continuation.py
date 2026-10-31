"""Prepare a continuation: research again the claims a report's budget did not reach.

The earlier report is not changed. The continuation is a new investigation whose report
copies the settled claims, findings, evidence and sources under new IDs (IDs are unique
across investigations) and researches the budget-limited claims again.
"""

from uuid import UUID, uuid4

from clear_context.domain.investigation import InvestigationReport


class NothingToContinue(ValueError):
    pass


def continuation_state(parent: InvestigationReport, text: str) -> dict:
    """Graph input for a continuation of parent; raises NothingToContinue if none is needed."""
    summary = parent.research_summary
    limited = set(summary.budget_limited_claim_ids) if summary else set()
    if not limited:
        raise NothingToContinue("Every research need of this report was within its budget.")
    claim_ids = {claim.id: uuid4() for claim in parent.claims}
    claims = [claim.model_copy(update={"id": claim_ids[claim.id]}) for claim in parent.claims]
    kept_findings = [f for f in parent.findings if f.claim_id not in limited]
    used = {
        evidence_id
        for finding in kept_findings
        for evidence_id in [
            *finding.evidence_ids,
            *(e for c in finding.components for e in [*c.evidence_ids, *c.context_evidence_ids]),
        ]
    }
    evidence_ids, source_ids, evidence = {}, {}, []
    for item in parent.evidence:
        if item.id not in used:
            continue
        evidence_ids[item.id] = uuid4()
        source_ids.setdefault(item.source_id, uuid4())
        evidence.append(
            item.model_copy(
                update={
                    "id": evidence_ids[item.id],
                    "claim_id": claim_ids[item.claim_id],
                    "source_id": source_ids[item.source_id],
                }
            )
        )
    sources = [
        source.model_copy(update={"id": source_ids[source.id]})
        for source in parent.sources
        if source.id in source_ids
    ]

    def remap(ids):
        return [evidence_ids[i] for i in ids]

    findings = [
        finding.model_copy(
            update={
                "id": uuid4(),
                "claim_id": claim_ids[finding.claim_id],
                "evidence_ids": remap(finding.evidence_ids),
                "components": [
                    component.model_copy(
                        update={
                            "evidence_ids": remap(component.evidence_ids),
                            "context_evidence_ids": remap(component.context_evidence_ids),
                            "evidence_relations": {
                                str(evidence_ids[UUID(key)]): relation
                                for key, relation in component.evidence_relations.items()
                            },
                        }
                    )
                    for component in finding.components
                ],
            }
        )
        for finding in kept_findings
    ]
    return {
        "claims": [c for c, old in zip(claims, parent.claims, strict=True) if old.id in limited],
        "all_claims": claims,
        "kept": {"findings": findings, "evidence": evidence, "sources": sources},
        # Claim spans point into the text the parent analyzed.
        "analyzed_text": parent.analyzed_text if parent.analyzed_text is not None else text,
    }

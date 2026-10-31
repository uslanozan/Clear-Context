from clear_context.domain.investigation import InvestigationReport
from clear_context.graph.state import InvestigationState


def merge_continuation(state: InvestigationState) -> dict:
    """Combine the claims researched again with those copied from the earlier report."""
    report = state["report"]
    kept = state["kept"]
    order = {claim.id: index for index, claim in enumerate(state["all_claims"])}
    findings = sorted([*kept["findings"], *report.findings], key=lambda f: order[f.claim_id])
    merged = InvestigationReport(
        investigation_id=report.investigation_id,
        mode=report.mode,
        claims=state["all_claims"],
        sources=[*kept["sources"], *report.sources],
        evidence=[*kept["evidence"], *report.evidence],
        findings=findings,
        limitations=[
            f"Continued from an earlier report: {len(report.claims)} claim(s) researched "
            f"again; {len(kept['findings'])} copied unchanged.",
            *report.limitations,
        ],
        model_usage=report.model_usage,
        # Counts describe this run's research; a further continuation starts from them.
        research_summary=report.research_summary,
    )
    return {"report": merged}

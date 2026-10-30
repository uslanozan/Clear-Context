from clear_context.domain.investigation import InvestigationReport
from clear_context.graph.state import InvestigationState


def validate_report(state: InvestigationState) -> dict:
    data = state["report"].model_dump()
    data["model_usage"] = [*state.get("model_usage", []), *data["model_usage"]]
    data["extraction_coverage"] = state.get("extraction_coverage")
    if state.get("media"):
        data["analyzed_text"] = state.get("analyzed_text", "")
        data["media"] = [item.model_dump() for item in state.get("media_findings", [])]
    report = InvestigationReport.model_validate(data)
    if report.investigation_id != state["investigation_id"]:
        raise ValueError("Report belongs to a different investigation.")
    if report.claims != state["claims"]:
        raise ValueError("Report changed the extracted claims.")
    text = state.get("analyzed_text", state["text"])
    for claim in report.claims:
        for span in [claim.source_span, *claim.context_spans]:
            if span and text[span.start : span.end] != span.text:
                raise ValueError("Claim provenance does not match the original input.")
    if report.extraction_coverage:
        if report.extraction_coverage.status == "partial":
            report.limitations.append(
                "Claim extraction is partial; some input ranges remain unresolved."
            )
        report.limitations.extend(
            "Semantic completeness is not established."
            if note == "Semantic completeness is not established; source research is pending."
            and any(finding.components for finding in report.findings)
            else note
            for note in report.extraction_coverage.notes
        )
    return {"report": report}

from clear_context.domain.investigation import InvestigationReport
from clear_context.graph.state import InvestigationState


def validate_report(state: InvestigationState) -> dict:
    report = InvestigationReport.model_validate(state["report"].model_dump())
    if report.investigation_id != state["investigation_id"]:
        raise ValueError("Report belongs to a different investigation.")
    if report.claims != state["claims"]:
        raise ValueError("Report changed the extracted claims.")
    return {"report": report}

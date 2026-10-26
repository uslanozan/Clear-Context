from clear_context.domain.investigation import InvestigationReport
from clear_context.graph.state import InvestigationState


def validate_report(state: InvestigationState) -> dict:
    data = state["report"].model_dump()
    data["model_usage"] = state.get("model_usage", [])
    report = InvestigationReport.model_validate(data)
    if report.investigation_id != state["investigation_id"]:
        raise ValueError("Report belongs to a different investigation.")
    if report.claims != state["claims"]:
        raise ValueError("Report changed the extracted claims.")
    return {"report": report}

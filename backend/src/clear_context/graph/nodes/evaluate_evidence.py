from langgraph.runtime import Runtime

from clear_context.graph.state import InvestigationContext, InvestigationState


def evaluate_evidence(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict:
    claims = [claim.model_copy(deep=True) for claim in state["claims"]]
    report = runtime.context.provider.evaluate_evidence(state["investigation_id"], claims)
    return {"report": report}

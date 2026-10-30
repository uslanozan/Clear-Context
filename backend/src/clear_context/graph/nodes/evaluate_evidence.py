from langgraph.runtime import Runtime

from clear_context.graph.state import InvestigationContext, InvestigationState


def evaluate_evidence(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict:
    claims = [claim.model_copy(deep=True) for claim in state["claims"]]
    if runtime.context.research is None:
        report = runtime.context.provider.evaluate_evidence(state["investigation_id"], claims)
    else:
        report = runtime.context.research.run(
            state["investigation_id"],
            claims,
            progress=runtime.context.progress,
            mode=runtime.context.research_mode,
        )
    return {"report": report}

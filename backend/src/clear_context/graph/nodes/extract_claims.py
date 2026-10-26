from langgraph.runtime import Runtime

from clear_context.graph.state import InvestigationContext, InvestigationState


def extract_claims(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict:
    result = runtime.context.provider.extract_claims(state["text"])
    if not result.claims:
        raise ValueError("Claim extraction returned no claims.")
    return {"claims": result.claims, "model_usage": result.model_usage}

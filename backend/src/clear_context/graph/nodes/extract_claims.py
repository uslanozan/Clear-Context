from langgraph.runtime import Runtime

from clear_context.graph.state import InvestigationContext, InvestigationState


def extract_claims(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict:
    claims = runtime.context.provider.extract_claims(state["text"])
    if not claims:
        raise ValueError("Claim extraction returned no claims.")
    return {"claims": claims}

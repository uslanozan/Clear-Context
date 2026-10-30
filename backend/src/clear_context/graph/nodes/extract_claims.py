from langgraph.runtime import Runtime

from clear_context.graph.state import InvestigationContext, InvestigationState


def extract_claims(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict:
    text = state.get("analyzed_text", state["text"])
    if not text.strip():
        # An image without readable text or caption has no claims to extract.
        return {"claims": [], "extraction_coverage": None}
    result = runtime.context.provider.extract_claims(text)
    if not result.claims and result.coverage is None:
        raise ValueError("Claim extraction returned no claims.")
    return {
        "claims": result.claims,
        "model_usage": result.model_usage,
        "extraction_coverage": result.coverage,
    }

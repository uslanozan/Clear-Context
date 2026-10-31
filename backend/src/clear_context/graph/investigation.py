from langgraph.graph import END, START, StateGraph

from clear_context.graph.nodes.analyze_media import analyze_media
from clear_context.graph.nodes.evaluate_evidence import evaluate_evidence
from clear_context.graph.nodes.extract_claims import extract_claims
from clear_context.graph.nodes.fetch_links import fetch_links
from clear_context.graph.nodes.merge_continuation import merge_continuation
from clear_context.graph.nodes.validate_report import validate_report
from clear_context.graph.state import InvestigationContext, InvestigationState
from clear_context.providers.link_reader import find_links


def first_step(state: InvestigationState) -> str:
    # A continuation already has its claims and researches them again.
    if state.get("kept") is not None:
        return "evaluate_evidence"
    # Links are read first; their images then join uploaded images.
    if find_links(state["text"]):
        return "fetch_links"
    return "analyze_media" if state.get("media") else "extract_claims"


def build_investigation_graph():
    builder = StateGraph(InvestigationState, context_schema=InvestigationContext)
    builder.add_node("fetch_links", fetch_links)
    builder.add_node("analyze_media", analyze_media)
    builder.add_node("extract_claims", extract_claims)
    builder.add_node("evaluate_evidence", evaluate_evidence)
    builder.add_node("merge_continuation", merge_continuation)
    builder.add_node("validate_report", validate_report)
    builder.add_conditional_edges(
        START,
        first_step,
        ["evaluate_evidence", "fetch_links", "analyze_media", "extract_claims"],
    )
    builder.add_conditional_edges(
        "fetch_links",
        lambda state: "analyze_media" if state.get("media") else "extract_claims",
        ["analyze_media", "extract_claims"],
    )
    builder.add_edge("analyze_media", "extract_claims")
    builder.add_edge("extract_claims", "evaluate_evidence")
    builder.add_conditional_edges(
        "evaluate_evidence",
        lambda state: "merge_continuation" if state.get("kept") is not None else "validate_report",
        ["merge_continuation", "validate_report"],
    )
    builder.add_edge("merge_continuation", "validate_report")
    builder.add_edge("validate_report", END)
    return builder.compile()

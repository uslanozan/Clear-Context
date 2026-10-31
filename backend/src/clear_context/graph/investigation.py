from langgraph.graph import END, START, StateGraph

from clear_context.graph.nodes.analyze_media import analyze_media
from clear_context.graph.nodes.evaluate_evidence import evaluate_evidence
from clear_context.graph.nodes.extract_claims import extract_claims
from clear_context.graph.nodes.fetch_links import fetch_links
from clear_context.graph.nodes.validate_report import validate_report
from clear_context.graph.state import InvestigationContext, InvestigationState
from clear_context.providers.link_reader import find_links


def build_investigation_graph():
    builder = StateGraph(InvestigationState, context_schema=InvestigationContext)
    builder.add_node("fetch_links", fetch_links)
    builder.add_node("analyze_media", analyze_media)
    builder.add_node("extract_claims", extract_claims)
    builder.add_node("evaluate_evidence", evaluate_evidence)
    builder.add_node("validate_report", validate_report)
    # Links are read first; their images then join uploaded images. Text without links or
    # files skips both nodes.
    builder.add_conditional_edges(
        START,
        lambda state: (
            "fetch_links"
            if find_links(state["text"])
            else ("analyze_media" if state.get("media") else "extract_claims")
        ),
        ["fetch_links", "analyze_media", "extract_claims"],
    )
    builder.add_conditional_edges(
        "fetch_links",
        lambda state: "analyze_media" if state.get("media") else "extract_claims",
        ["analyze_media", "extract_claims"],
    )
    builder.add_edge("analyze_media", "extract_claims")
    builder.add_edge("extract_claims", "evaluate_evidence")
    builder.add_edge("evaluate_evidence", "validate_report")
    builder.add_edge("validate_report", END)
    return builder.compile()

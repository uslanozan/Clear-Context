from langgraph.runtime import Runtime

from clear_context.graph.state import InvestigationContext, InvestigationState


def evaluate_evidence(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict:
    claims = [claim.model_copy(deep=True) for claim in state["claims"]]
    if runtime.context.research is None:
        report = runtime.context.provider.evaluate_evidence(state["investigation_id"], claims)
    else:
        extra = (
            {"media": state["media_findings"], "user_text": state["text"]}
            if state.get("media_findings")
            else {}
        )
        read_links = [link for link in state.get("link_findings", []) if link.status == "read"]
        if read_links:
            # The page being checked is not evidence for itself.
            extra["subject_urls"] = [link.url for link in read_links]
            dates = [link.published_on for link in read_links if link.published_on]
            if dates:
                extra["published_on"] = min(dates)
        report = runtime.context.research.run(
            state["investigation_id"],
            claims,
            progress=runtime.context.progress,
            mode=runtime.context.research_mode,
            **extra,
        )
    return {"report": report}

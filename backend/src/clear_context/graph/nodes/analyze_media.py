from pathlib import Path

from langgraph.runtime import Runtime

from clear_context.domain.investigation import MediaAnalysis, MediaFinding, MediaOrigin
from clear_context.graph.state import InvestigationContext, InvestigationState
from clear_context.providers.reverse_image import ReverseImageFailure


def compose_analyzed_text(text: str, findings: list[MediaFinding]) -> str:
    """Join the user's text with text read from images, each block labeled by its source."""
    parts = [text.strip()] if text.strip() else []
    for index, finding in enumerate(findings, 1):
        visible = finding.analysis.visible_text.strip()
        if visible:
            parts.append(f"[Text read from image {index}]\n{visible}")
    return "\n\n".join(parts)


def check_origin(search, data: bytes, mime_type: str) -> MediaOrigin:
    if search is None:
        return MediaOrigin(
            status="not_checked", reason="No reverse image search provider is configured."
        )
    try:
        return search.search(data, mime_type)
    except ReverseImageFailure as error:
        return MediaOrigin(
            status="failed",
            provider=search.name,
            reason=f"Reverse image search did not complete ({error.code}).",
        )


def analyze_media(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict:
    findings, usage = [], []
    for item in state.get("media", []):
        if item["kind"] == "video":
            analysis = MediaAnalysis(
                status="not_analyzed",
                content_type="video",
                note="Video analysis is not connected yet.",
            )
            origin = MediaOrigin(status="not_checked", reason="Video frames are not searched yet.")
        else:
            data = Path(item["path"]).read_bytes()
            analysis, record = runtime.context.media_analyzer.analyze_image(
                data, item["mime_type"], state["text"]
            )
            if record:
                usage.append(record)
            origin = check_origin(runtime.context.reverse_image, data, item["mime_type"])
        findings.append(
            MediaFinding(
                id=item["id"],
                kind=item["kind"],
                mime_type=item["mime_type"],
                filename=item["filename"],
                analysis=analysis,
                origin=origin,
            )
        )
    return {
        "media_findings": findings,
        "analyzed_text": compose_analyzed_text(state["text"], findings),
        "model_usage": usage,
    }

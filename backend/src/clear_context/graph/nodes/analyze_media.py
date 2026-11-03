import re
from pathlib import Path

from langgraph.runtime import Runtime

from clear_context.domain.investigation import (
    MediaFinding,
    MediaOrigin,
    PriorChecks,
)
from clear_context.graph.state import InvestigationContext, InvestigationState
from clear_context.providers.reverse_image import ReverseImageFailure
from clear_context.services.video_analysis import analyze_video

# A line break inside a statement read from a screenshot is the page's layout, not part of the
# text. Claims quote the composed text literally, so a sentence wrapped as "visible from" and
# "space." would never match a quote of the sentence as it reads.
WRAPPED_LINE = re.compile(r"(?<![.!?:;])[ \t]*\n[ \t]*(?=\S)")


def unwrap(statement: str) -> str:
    """Join lines that a screenshot wrapped; a line that ends a sentence keeps its break."""
    return WRAPPED_LINE.sub(" ", statement.strip())


def clock(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def compose_analyzed_text(text: str, findings: list[MediaFinding]) -> str:
    """Join the user's text with statements read from media, each block labeled by its source.

    Only claim text (post text, headlines, captions shown in a video) and speech are joined;
    signs, labels and date stamps remain observations, so they are not extracted as claims.
    """
    # The label tells extraction and planning that the text describes the attached files, so
    # a caption such as "images from the 2023 earthquake" is read as a statement about them.
    # Unread files (preview mode) leave the text unchanged.
    read = any(finding.analysis.status == "analyzed" for finding in findings)
    label = "[Text the user sent with the attached media]\n" if read else ""
    parts = [label + text.strip()] if text.strip() else []
    for index, finding in enumerate(findings, 1):
        kind = finding.kind
        statements = "\n".join(unwrap(part) for part in finding.analysis.claim_text if part.strip())
        if statements:
            parts.append(f"[Text read from {kind} {index}]\n{statements}")
        for turn in finding.analysis.speech:
            span = f"{clock(turn.start)}-{clock(turn.end)}"
            parts.append(f"[Speech in video {index}, {span}]\n{turn.text}")
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


def check_prior_fact_checks(search, origin: MediaOrigin, text: str) -> PriorChecks:
    if search is None:
        return PriorChecks(status="not_checked", reason="Fact check search is not configured.")
    return search.lookup(origin, text)


def analyze_media(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict:
    findings, usage = [], []
    context = runtime.context
    reverse_image = context.reverse_image

    def search_frame(jpeg: bytes) -> MediaOrigin:
        return check_origin(reverse_image, jpeg, "image/jpeg")

    for item in state.get("media", []):
        frames = []
        if item["kind"] == "video":
            caption = item.get("caption", state["text"])
            result = analyze_video(
                Path(item["path"]),
                caption,
                context.media_analyzer,
                getattr(context, "transcriber", None),
                search_frame if reverse_image is not None else None,
                context.media_dir,
            )
            analysis, origin, frames = result.analysis, result.origin, result.frames
            usage += result.usage
            # The caption, or statements shown in the video when there is no caption.
            query = caption.strip() or "\n".join(analysis.claim_text)
            prior = (
                check_prior_fact_checks(getattr(context, "fact_checks", None), origin, query)
                if analysis.status == "analyzed"
                else PriorChecks(status="not_checked", reason="The video was not analyzed.")
            )
        else:
            data = Path(item["path"]).read_bytes()
            # An image from a linked page is compared with that page, not the user's note.
            caption = item.get("caption", state["text"])
            analysis, record = runtime.context.media_analyzer.analyze_image(
                data, item["mime_type"], caption
            )
            if record:
                usage.append(record)
            origin = check_origin(runtime.context.reverse_image, data, item["mime_type"])
            # The caption, or statements read from the image when there is no caption.
            query = caption.strip() or "\n".join(analysis.claim_text)
            prior = check_prior_fact_checks(
                getattr(runtime.context, "fact_checks", None), origin, query
            )
        findings.append(
            MediaFinding(
                id=item["id"],
                kind=item["kind"],
                mime_type=item["mime_type"],
                filename=item["filename"],
                analysis=analysis,
                origin=origin,
                prior_checks=prior,
                source_url=item.get("source_url"),
                frames=frames,
            )
        )
    return {
        "media_findings": findings,
        # Builds on text read from links, when there were any.
        "analyzed_text": compose_analyzed_text(state.get("analyzed_text", state["text"]), findings),
        "model_usage": usage,
    }

from uuid import UUID

from langgraph.runtime import Runtime

from clear_context.domain.investigation import LinkFinding
from clear_context.graph.state import InvestigationContext, InvestigationState
from clear_context.providers.link_reader import LinkFailure, find_links, host_label
from clear_context.services.media import store

# One main image per page; later images are usually logos, ads or related stories.
MAX_IMAGES_PER_LINK = 1
UNREADABLE = (
    "This link could not be read. Paste the post's text or attach a screenshot to check it."
)


def compose_link_text(text: str, pages: list[tuple[int, str]]) -> str:
    """Join the user's text with text read from links, each block labeled by its link."""
    parts = [text.strip()] if text.strip() else []
    parts += [f"[Text read from link {index}]\n{body}" for index, body in pages]
    return "\n\n".join(parts)


def fetch_links(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict:
    reader = runtime.context.link_reader
    findings, pages, media = [], [], list(state.get("media", []))
    for index, url in enumerate(find_links(state["text"]), 1):
        site = host_label(url)
        if reader is None:
            findings.append(
                LinkFinding(
                    url=url,
                    site=site,
                    status="not_read",
                    reason="Preview mode does not open links.",
                )
            )
            continue
        try:
            page = reader.read(url)
        except LinkFailure as error:
            findings.append(
                LinkFinding(
                    url=url, site=site, status="failed", reason=f"{UNREADABLE} ({error.code})"
                )
            )
            continue
        page.published_on = reader.published_on(page)
        pages.append((index, page.text))
        media_ids, notes = [], []
        for image_url in page.images[:MAX_IMAGES_PER_LINK]:
            try:
                mime_type, data = reader.download_image(image_url)
            except LinkFailure as error:
                notes.append(f"The page image could not be downloaded ({error.code}).")
                continue
            stored = store(
                runtime.context.media_dir, f"link-{index}-image", "image", mime_type, data
            )
            media_id = runtime.context.attach_media(stored, url)
            media_ids.append(UUID(media_id))
            media.append(
                {
                    "id": UUID(media_id),
                    "kind": "image",
                    "mime_type": mime_type,
                    "filename": stored.filename,
                    "path": str(runtime.context.media_dir / stored.storage_name),
                    "source_url": url,
                    # The image is compared with the page, not with the user's note.
                    "caption": " ".join(filter(None, [page.title, page.text[:600]])),
                }
            )
        findings.append(
            LinkFinding(
                url=url,
                site=site,
                status="read",
                title=page.title,
                published_on=page.published_on,
                text_chars=len(page.text),
                truncated=page.truncated,
                media_ids=media_ids,
                reason=" ".join(notes) or None,
            )
        )
    update = {"link_findings": findings, "media": media}
    if pages:
        update["analyzed_text"] = compose_link_text(state["text"], pages)
    return update

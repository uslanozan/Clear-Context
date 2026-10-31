import logging
from pathlib import Path
from uuid import UUID

from langsmith import tracing_context

from clear_context.domain.investigation import InvestigationReport, InvestigationStatus
from clear_context.graph.investigation import build_investigation_graph
from clear_context.graph.state import InvestigationContext
from clear_context.providers.errors import ProviderError
from clear_context.repositories.investigation import InvestigationRepository
from clear_context.services.continuation import continuation_state
from clear_context.services.runtime import Runtime

logger = logging.getLogger(__name__)


class InvestigationService:
    def __init__(
        self,
        repository: InvestigationRepository,
        runtime: Runtime,
        recursion_limit: int = 12,
        media_dir: Path | None = None,
    ):
        self.repository = repository
        self.runtime = runtime
        self.recursion_limit = recursion_limit
        self.media_dir = media_dir
        self.graph = build_investigation_graph()

    def replace_runtime(self, runtime: Runtime) -> None:
        """Use new settings from the next investigation on; running ones keep theirs."""
        previous, self.runtime = self.runtime, runtime
        previous.retire()

    def run(self, investigation_id: UUID) -> None:
        row = self.repository.get(investigation_id)
        if row is None or row.status != InvestigationStatus.QUEUED:
            return
        runtime = self.runtime.acquire()
        try:
            self.repository.transition(
                investigation_id, InvestigationStatus.RUNNING, "graph_started"
            )
            report: InvestigationReport | None = None
            # Keep local research out of remote tracing, including inherited environment settings.
            with tracing_context(enabled=False):
                media = [
                    {
                        "id": item.id,
                        "kind": item.kind,
                        "mime_type": item.mime_type,
                        "filename": item.filename,
                        "path": str(self.media_dir / item.storage_name),
                    }
                    for item in self.repository.media_for(investigation_id)
                ]
                graph_input = {"investigation_id": investigation_id, "text": row.text}
                if row.relation == "continue":
                    parent = self.repository.get_report(UUID(row.parent_id))
                    graph_input.update(continuation_state(parent, row.text))
                if media:
                    graph_input["media"] = media
                for update in self.graph.stream(
                    graph_input,
                    context=InvestigationContext(
                        provider=runtime.provider,
                        research=runtime.research,
                        progress=lambda stage: self.repository.record_step(investigation_id, stage),
                        research_mode=row.research_mode,
                        media_analyzer=runtime.media_analyzer,
                        reverse_image=runtime.reverse_image,
                        fact_checks=runtime.fact_checks,
                        link_reader=runtime.link_reader,
                        unread_link_reason=(
                            "Link reading is turned off in settings."
                            if runtime.live
                            else "Preview mode does not open links."
                        ),
                        attach_media=lambda stored, url: self.repository.add_media(
                            investigation_id, stored, source_url=url
                        ),
                        media_dir=self.media_dir,
                    ),
                    config={"recursion_limit": self.recursion_limit},
                    stream_mode="updates",
                ):
                    for node_name, values in update.items():
                        self.repository.record_step(
                            investigation_id, node_name, values.get("model_usage")
                        )
                        if node_name == "validate_report":
                            report = values["report"]
            if report is None:
                raise ValueError("Graph finished without a validated report.")
            self.repository.complete(report)
        except Exception as error:
            # The local server log gets the cause; the database keeps only a code, since raw
            # provider errors may contain secrets or input.
            logger.error(
                "Investigation %s failed: %s: %s",
                investigation_id,
                type(error).__name__,
                str(error)[:500],
            )
            current = self.repository.get(investigation_id)
            if current and current.status in {"queued", "running"}:
                self.repository.transition(
                    investigation_id,
                    InvestigationStatus.FAILED,
                    "investigation_failed",
                    error_code=error.code
                    if isinstance(error, ProviderError)
                    else "processing_failed",
                )
        finally:
            runtime.release()

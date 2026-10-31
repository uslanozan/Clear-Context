import logging
from pathlib import Path
from uuid import UUID

from langsmith import tracing_context

from clear_context.domain.investigation import InvestigationReport, InvestigationStatus
from clear_context.graph.investigation import build_investigation_graph
from clear_context.graph.state import InvestigationContext
from clear_context.providers.base import InvestigationProvider
from clear_context.providers.errors import ProviderError
from clear_context.repositories.investigation import InvestigationRepository

logger = logging.getLogger(__name__)


class InvestigationService:
    def __init__(
        self,
        repository: InvestigationRepository,
        provider: InvestigationProvider,
        recursion_limit: int = 12,
        research=None,
        media_analyzer=None,
        reverse_image=None,
        media_dir: Path | None = None,
        fact_checks=None,
    ):
        self.repository = repository
        self.provider = provider
        self.recursion_limit = recursion_limit
        self.research = research
        self.media_analyzer = media_analyzer
        self.reverse_image = reverse_image
        self.fact_checks = fact_checks
        self.media_dir = media_dir
        self.graph = build_investigation_graph()

    def run(self, investigation_id: UUID) -> None:
        row = self.repository.get(investigation_id)
        if row is None or row.status != InvestigationStatus.QUEUED:
            return
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
                if media:
                    graph_input["media"] = media
                for update in self.graph.stream(
                    graph_input,
                    context=InvestigationContext(
                        provider=self.provider,
                        research=self.research,
                        progress=lambda stage: self.repository.record_step(investigation_id, stage),
                        research_mode=row.research_mode,
                        media_analyzer=self.media_analyzer,
                        reverse_image=self.reverse_image,
                        fact_checks=self.fact_checks,
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

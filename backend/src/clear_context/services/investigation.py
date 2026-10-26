from uuid import UUID

from langsmith import tracing_context

from clear_context.domain.investigation import InvestigationReport, InvestigationStatus
from clear_context.graph.investigation import build_investigation_graph
from clear_context.graph.state import InvestigationContext
from clear_context.providers.base import InvestigationProvider
from clear_context.providers.errors import ProviderError
from clear_context.repositories.investigation import InvestigationRepository


class InvestigationService:
    def __init__(
        self,
        repository: InvestigationRepository,
        provider: InvestigationProvider,
        recursion_limit: int = 12,
    ):
        self.repository = repository
        self.provider = provider
        self.recursion_limit = recursion_limit
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
                for update in self.graph.stream(
                    {"investigation_id": investigation_id, "text": row.text},
                    context=InvestigationContext(provider=self.provider),
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
            # Do not persist raw provider errors, which may contain secrets or input.
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

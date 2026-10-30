from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from clear_context.domain.investigation import (
    Claim,
    Evidence,
    Finding,
    InvestigationReport,
    InvestigationStatus,
    MediaFinding,
    ModelUsage,
    Source,
    validate_transition,
)
from clear_context.models import (
    ClaimRow,
    EvidenceRow,
    FindingEvidenceRow,
    FindingRow,
    InvestigationRow,
    MediaRow,
    ResearchStepRow,
    SourceRow,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class InvestigationRepository:
    def __init__(self, session_factory):
        self.sessions = session_factory

    def create(
        self, text: str, mode: str = "mock", research_mode: str = "balanced", media=()
    ) -> InvestigationRow:
        now = utc_now()
        row = InvestigationRow(
            id=str(uuid4()),
            text=text,
            status=InvestigationStatus.QUEUED,
            mode=mode,
            research_mode=research_mode,
            revision=1,
            created_at=now,
            updated_at=now,
        )
        with self.sessions.begin() as session:
            session.add(row)
            session.flush()
            for position, item in enumerate(media):
                session.add(
                    MediaRow(
                        id=str(uuid4()),
                        investigation_id=row.id,
                        position=position,
                        kind=item.kind,
                        mime_type=item.mime_type,
                        size_bytes=item.size_bytes,
                        sha256=item.sha256,
                        filename=item.filename,
                        storage_name=item.storage_name,
                        created_at=now,
                    )
                )
        return row

    def media_for(self, investigation_id: UUID) -> list[MediaRow]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(MediaRow)
                    .where(MediaRow.investigation_id == str(investigation_id))
                    .order_by(MediaRow.position)
                )
            )

    def media(self, media_id: UUID) -> MediaRow | None:
        with self.sessions() as session:
            return session.get(MediaRow, str(media_id))

    def get(self, investigation_id: UUID) -> InvestigationRow | None:
        with self.sessions() as session:
            return session.get(InvestigationRow, str(investigation_id))

    def list_recent(self, limit: int, offset: int) -> list[InvestigationRow]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(InvestigationRow)
                    .order_by(InvestigationRow.created_at.desc(), InvestigationRow.id)
                    .limit(limit)
                    .offset(offset)
                )
            )

    def steps(self, investigation_id: UUID) -> list[ResearchStepRow]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(ResearchStepRow)
                    .where(ResearchStepRow.investigation_id == str(investigation_id))
                    .order_by(ResearchStepRow.id)
                )
            )

    def transition(
        self,
        investigation_id: UUID,
        target: InvestigationStatus,
        step_name: str,
        error_code: str | None = None,
    ) -> None:
        with self.sessions.begin() as session:
            row = session.get(InvestigationRow, str(investigation_id))
            if row is None:
                raise LookupError("Investigation not found.")
            validate_transition(InvestigationStatus(row.status), target)
            row.status = target
            row.updated_at = utc_now()
            row.error_code = error_code
            session.add(
                ResearchStepRow(
                    investigation_id=row.id,
                    name=step_name,
                    status=target,
                    created_at=row.updated_at,
                )
            )

    def fail_interrupted(self) -> None:
        with self.sessions.begin() as session:
            rows = session.scalars(
                select(InvestigationRow).where(InvestigationRow.status.in_(["queued", "running"]))
            )
            for row in rows:
                row.status = InvestigationStatus.FAILED
                row.error_code = "interrupted"
                row.updated_at = utc_now()
                session.add(
                    ResearchStepRow(
                        investigation_id=row.id,
                        name="startup_recovery",
                        status="failed",
                        created_at=row.updated_at,
                    )
                )

    def record_step(
        self, investigation_id: UUID, name: str, model_usage: list[ModelUsage] | None = None
    ) -> None:
        with self.sessions.begin() as session:
            row = session.get(InvestigationRow, str(investigation_id))
            if row is None or row.status != InvestigationStatus.RUNNING:
                raise ValueError("Graph steps require a running investigation.")
            row.updated_at = utc_now()
            if model_usage is not None:
                row.model_usage = [item.model_dump(mode="json") for item in model_usage]
            session.add(
                ResearchStepRow(
                    investigation_id=row.id,
                    name=name,
                    status="running",
                    created_at=row.updated_at,
                )
            )

    def complete(self, report: InvestigationReport) -> None:
        report = InvestigationReport.model_validate(report.model_dump())
        with self.sessions.begin() as session:
            row = session.get(InvestigationRow, str(report.investigation_id))
            if row is None:
                raise LookupError("Investigation not found.")
            validate_transition(InvestigationStatus(row.status), InvestigationStatus.COMPLETED)
            if report.revision != row.revision or report.mode != row.mode:
                raise ValueError("Report scope does not match the investigation.")
            # Claims from images point into the analyzed text, not the user's input.
            saved_text = report.analyzed_text if report.analyzed_text is not None else row.text
            row.analyzed_text = report.analyzed_text
            stored_media = {
                item.id: item
                for item in session.scalars(
                    select(MediaRow).where(MediaRow.investigation_id == row.id)
                )
            }
            if {str(item.id) for item in report.media} - set(stored_media):
                raise ValueError("Report references media outside this investigation.")
            for item in report.media:
                stored_media[str(item.id)].finding = {
                    "analysis": item.analysis.model_dump(mode="json"),
                    "origin": item.origin.model_dump(mode="json"),
                    "prior_checks": item.prior_checks.model_dump(mode="json"),
                }
            for claim in report.claims:
                for span in [claim.source_span, *claim.context_spans]:
                    if span and saved_text[span.start : span.end] != span.text:
                        raise ValueError("Claim provenance does not match saved input.")
                session.add(
                    ClaimRow(
                        id=str(claim.id),
                        investigation_id=row.id,
                        text=claim.text,
                        provenance=claim.model_dump(mode="json", exclude={"id", "text"}),
                    )
                )
            for source in report.sources:
                session.add(
                    SourceRow(
                        id=str(source.id),
                        investigation_id=row.id,
                        url=source.url,
                        title=source.title,
                        content=source.content,
                    )
                )
            session.flush()
            for item in report.evidence:
                session.add(
                    EvidenceRow(
                        id=str(item.id),
                        claim_id=str(item.claim_id),
                        source_id=str(item.source_id),
                        excerpt=item.excerpt,
                    )
                )
            for finding in report.findings:
                session.add(
                    FindingRow(
                        id=str(finding.id),
                        claim_id=str(finding.claim_id),
                        assessment=finding.assessment,
                        explanation=finding.explanation,
                        components=[item.model_dump(mode="json") for item in finding.components],
                    )
                )
            session.flush()
            for finding in report.findings:
                for evidence_id in finding.evidence_ids:
                    session.add(
                        FindingEvidenceRow(finding_id=str(finding.id), evidence_id=str(evidence_id))
                    )
            row.limitations = report.limitations
            row.model_usage = [item.model_dump(mode="json") for item in report.model_usage]
            row.extraction_coverage = (
                report.extraction_coverage.model_dump(mode="json")
                if report.extraction_coverage
                else None
            )
            row.status = InvestigationStatus.COMPLETED
            row.updated_at = utc_now()
            session.add(
                ResearchStepRow(
                    investigation_id=row.id,
                    name="report_saved",
                    status="completed",
                    created_at=row.updated_at,
                )
            )

    def get_report(self, investigation_id: UUID) -> InvestigationReport | None:
        with self.sessions() as session:
            row = session.get(InvestigationRow, str(investigation_id))
            if row is None or row.status != InvestigationStatus.COMPLETED:
                return None
            claims = list(
                session.scalars(select(ClaimRow).where(ClaimRow.investigation_id == row.id))
            )
            sources = list(
                session.scalars(select(SourceRow).where(SourceRow.investigation_id == row.id))
            )
            evidence = session.scalars(
                select(EvidenceRow).join(ClaimRow).where(ClaimRow.investigation_id == row.id)
            )
            findings = list(
                session.scalars(
                    select(FindingRow).join(ClaimRow).where(ClaimRow.investigation_id == row.id)
                )
            )
            references = session.execute(
                select(FindingEvidenceRow.finding_id, FindingEvidenceRow.evidence_id)
                .join(FindingRow)
                .join(ClaimRow)
                .where(ClaimRow.investigation_id == row.id)
            )
            media = [
                MediaFinding(
                    id=item.id,
                    kind=item.kind,
                    mime_type=item.mime_type,
                    filename=item.filename,
                    **item.finding,
                )
                for item in session.scalars(
                    select(MediaRow)
                    .where(MediaRow.investigation_id == row.id)
                    .order_by(MediaRow.position)
                )
                if item.finding
            ]
            evidence_by_finding: dict[str, list[str]] = {}
            for finding_id, evidence_id in references:
                evidence_by_finding.setdefault(finding_id, []).append(evidence_id)
            return InvestigationReport(
                investigation_id=investigation_id,
                mode=row.mode,
                revision=row.revision,
                claims=[Claim(id=item.id, text=item.text, **item.provenance) for item in claims],
                sources=[
                    Source(id=item.id, url=item.url, title=item.title, content=item.content)
                    for item in sources
                ],
                evidence=[
                    Evidence(
                        id=item.id,
                        claim_id=item.claim_id,
                        source_id=item.source_id,
                        excerpt=item.excerpt,
                    )
                    for item in evidence
                ],
                findings=[
                    Finding(
                        id=item.id,
                        claim_id=item.claim_id,
                        assessment=item.assessment,
                        explanation=item.explanation,
                        evidence_ids=evidence_by_finding.get(item.id, []),
                        components=item.components or [],
                    )
                    for item in findings
                ],
                limitations=row.limitations,
                model_usage=row.model_usage,
                extraction_coverage=row.extraction_coverage,
                analyzed_text=row.analyzed_text,
                media=media,
            )

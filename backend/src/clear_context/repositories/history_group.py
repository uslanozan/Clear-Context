from uuid import UUID, uuid4

from sqlalchemy import select, update

from clear_context.models import HistoryGroupRow, InvestigationRow
from clear_context.repositories.investigation import utc_now

MAX_GROUPS = 40


class HistoryGroupRepository:
    def __init__(self, session_factory):
        self.sessions = session_factory

    def list(self) -> list[HistoryGroupRow]:
        with self.sessions() as session:
            rows = session.scalars(
                select(HistoryGroupRow).order_by(
                    HistoryGroupRow.position, HistoryGroupRow.created_at
                )
            ).all()
            session.expunge_all()
            return list(rows)

    def create(self, name: str) -> HistoryGroupRow | None:
        """None when the limit of groups is reached."""
        with self.sessions.begin() as session:
            rows = session.scalars(select(HistoryGroupRow)).all()
            if len(rows) >= MAX_GROUPS:
                return None
            row = HistoryGroupRow(
                id=str(uuid4()),
                name=name,
                position=max((r.position for r in rows), default=-1) + 1,
                created_at=utc_now(),
            )
            session.add(row)
            session.flush()
            session.expunge(row)
            return row

    def rename(self, group_id: UUID, name: str) -> HistoryGroupRow | None:
        with self.sessions.begin() as session:
            row = session.get(HistoryGroupRow, str(group_id))
            if row is None:
                return None
            row.name = name
            session.flush()
            session.expunge(row)
            return row

    def delete(self, group_id: UUID) -> bool:
        """Remove the group; its investigations return to the ungrouped list, untouched."""
        with self.sessions.begin() as session:
            row = session.get(HistoryGroupRow, str(group_id))
            if row is None:
                return False
            session.execute(
                update(InvestigationRow)
                .where(InvestigationRow.group_id == row.id)
                .values(group_id=None)
            )
            session.delete(row)
            return True

    def retitle(self, investigation_id: UUID, title: str | None) -> bool:
        """False when the investigation is unknown."""
        with self.sessions.begin() as session:
            investigation = session.get(InvestigationRow, str(investigation_id))
            if investigation is None:
                return False
            investigation.title = title
            return True

    def assign(self, investigation_id: UUID, group_id: UUID | None) -> bool | None:
        """True when assigned, False when the group is unknown, None when the investigation is."""
        with self.sessions.begin() as session:
            investigation = session.get(InvestigationRow, str(investigation_id))
            if investigation is None:
                return None
            if group_id is not None and session.get(HistoryGroupRow, str(group_id)) is None:
                return False
            investigation.group_id = str(group_id) if group_id else None
            return True

from sqlalchemy import select

from clear_context.models import AppSettingRow
from clear_context.repositories.investigation import utc_now


class SettingsRepository:
    def __init__(self, session_factory):
        self.sessions = session_factory

    def load(self) -> dict[str, object]:
        with self.sessions() as session:
            return {row.key: row.value for row in session.scalars(select(AppSettingRow))}

    def save(self, changes: dict[str, object | None]) -> None:
        """Store changed values; None removes a value so the .env setting applies again."""
        now = utc_now()
        with self.sessions.begin() as session:
            for key, value in changes.items():
                row = session.get(AppSettingRow, key)
                if value is None:
                    if row is not None:
                        session.delete(row)
                elif row is None:
                    session.add(AppSettingRow(key=key, value=value, updated_at=now))
                else:
                    row.value, row.updated_at = value, now

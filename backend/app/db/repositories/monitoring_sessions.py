from sqlalchemy.orm import Session

from backend.app.db.models import MonitoringSession

from ._base import Repository


class MonitoringSessionRepository(Repository[MonitoringSession]):
    def __init__(self, session: Session):
        super().__init__(session, MonitoringSession)

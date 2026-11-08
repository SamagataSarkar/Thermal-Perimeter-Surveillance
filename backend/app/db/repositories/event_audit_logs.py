from sqlalchemy.orm import Session

from backend.app.db.models import EventAuditLog

from ._base import Repository


class EventAuditLogRepository(Repository[EventAuditLog]):
    def __init__(self, session: Session):
        super().__init__(session, EventAuditLog)

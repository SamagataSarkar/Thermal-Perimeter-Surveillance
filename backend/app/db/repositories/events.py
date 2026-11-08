from sqlalchemy.orm import Session

from backend.app.db.models import Event

from ._base import Repository


class EventRepository(Repository[Event]):
    def __init__(self, session: Session):
        super().__init__(session, Event)

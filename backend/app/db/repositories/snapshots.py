from sqlalchemy.orm import Session

from backend.app.db.models import Snapshot

from ._base import Repository


class SnapshotRepository(Repository[Snapshot]):
    def __init__(self, session: Session):
        super().__init__(session, Snapshot)

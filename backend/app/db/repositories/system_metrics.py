from sqlalchemy.orm import Session

from backend.app.db.models import SystemMetric

from ._base import Repository


class SystemMetricRepository(Repository[SystemMetric]):
    def __init__(self, session: Session):
        super().__init__(session, SystemMetric)

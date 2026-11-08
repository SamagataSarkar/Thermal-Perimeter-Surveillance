from sqlalchemy.orm import Session

from backend.app.db.models import Geofence

from ._base import Repository


class GeofenceRepository(Repository[Geofence]):
    def __init__(self, session: Session):
        super().__init__(session, Geofence)

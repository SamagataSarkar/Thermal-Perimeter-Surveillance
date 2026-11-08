from sqlalchemy.orm import Session

from backend.app.db.models import VideoSource

from ._base import Repository


class VideoSourceRepository(Repository[VideoSource]):
    def __init__(self, session: Session):
        super().__init__(session, VideoSource)

from typing import Generic, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class Repository(Generic[ModelT]):
    def __init__(self, session: Session, model: Type[ModelT]):
        self.session = session
        self.model = model

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        self.session.flush()
        return instance

    def get(self, identifier: int) -> Optional[ModelT]:
        return self.session.get(self.model, identifier)

    def list(self) -> list[ModelT]:
        return list(self.session.scalars(select(self.model)))

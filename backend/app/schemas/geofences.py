from typing import List, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeofenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    normalized_polygon: List[Tuple[float, float]] = Field(min_length=3)
    enabled: bool = True

    @field_validator("normalized_polygon")
    @classmethod
    def validate_polygon(cls, value):
        if any(not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0) for x, y in value):
            raise ValueError("polygon coordinates must be between 0 and 1")
        return value


class GeofenceRead(GeofenceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int

from enum import Enum
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class SourceTypeSchema(str, Enum):
    FILE = "FILE"
    RTSP = "RTSP"


def redact_source_uri(uri: str) -> str:
    parsed = urlsplit(uri)
    if parsed.scheme.lower() != "rtsp" or "@" not in parsed.netloc:
        return uri
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = "[{}]".format(host)
    try:
        port = ":{}".format(parsed.port) if parsed.port is not None else ""
    except ValueError:
        port = ""
    return urlunsplit((parsed.scheme, "REDACTED:REDACTED@{}{}".format(host, port),
                       parsed.path, parsed.query, parsed.fragment))


class VideoSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_type: SourceTypeSchema
    source_uri: str = Field(min_length=1, max_length=2000)
    enabled: bool = True


class VideoSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: SourceTypeSchema
    source_uri: str
    enabled: bool

    @field_serializer("source_uri")
    def serialize_source_uri(self, value: str) -> str:
        return redact_source_uri(value)

    @field_validator("source_uri")
    @classmethod
    def validate_source_uri(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source_uri must not be blank")
        return value

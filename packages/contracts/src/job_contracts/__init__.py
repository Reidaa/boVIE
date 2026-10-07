import hashlib
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid5

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)

EventType = Literal["discovered", "updated", "closed"]

# Changing this namespace changes every event ID and defeats republish deduplication.
EVENT_NAMESPACE = UUID("a29ccd0b-e431-445f-8881-a6ad4aa872bf")


class DisplayField(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    value: str = Field(min_length=1, max_length=1024)
    inline: bool = True


class OfferDetails(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    organization: str
    country: str
    city: str
    url: HttpUrl
    fields: list[DisplayField] = Field(default_factory=list, max_length=25)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


def stable_event_id(data: dict[str, Any]) -> UUID:
    """Republishing the same change yields the same ID, so consumers can drop it."""
    identity = f"{data['source']}:{data['source_offer_id']}:{data['type']}"
    if data["type"] == "updated":
        identity += f":{data['offer'].content_hash}"
    return uuid5(EVENT_NAMESPACE, identity)


class OfferEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    type: EventType = "discovered"
    source: Literal["business_france", "wttj"]
    source_offer_id: str = Field(min_length=1, max_length=255)
    offer: OfferDetails
    event_id: UUID = Field(default_factory=stable_event_id)
    observed_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("source_offer_id")
    @classmethod
    def unambiguous_identity(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("Source identity cannot have surrounding whitespace")
        return value

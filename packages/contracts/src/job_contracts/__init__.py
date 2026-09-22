from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)


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


class OfferDiscovered(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    event_id: UUID = Field(default_factory=uuid4)
    source: Literal["business_france", "wttj"]
    source_offer_id: str = Field(min_length=1, max_length=255)
    observed_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    offer: OfferDetails

    @field_validator("source_offer_id")
    @classmethod
    def unambiguous_identity(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("Source identity cannot have surrounding whitespace")
        return value

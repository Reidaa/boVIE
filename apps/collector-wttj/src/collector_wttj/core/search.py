"""Minimal v3 public API projections; historical v1 DTOs remain in types.py."""

from pydantic import BaseModel, Field


class Organization(BaseModel):
    name: str
    slug: str


class SearchHit(BaseModel):
    reference: str
    slug: str
    contract_type: str
    organization: Organization


class Pagination(BaseModel):
    page: int = Field(ge=1)
    page_count: int = Field(ge=0)


class SearchResponse(BaseModel):
    data: list[SearchHit]
    metadata: Pagination


class Office(BaseModel):
    city: str
    country_code: str


class JobDetail(BaseModel):
    wttj_reference: str
    slug: str
    name: str
    contract_type: str
    status: str
    organization: Organization
    offices: list[Office]
    published_at: str
    start_date: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    apply_url: str | None = None


class DetailResponse(BaseModel):
    job: JobDetail

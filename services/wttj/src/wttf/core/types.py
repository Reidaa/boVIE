from typing import Any

from pydantic import BaseModel, ConfigDict


class WttjModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class LocalizedText(WttjModel):
    cs: str | None = None
    en: str | None = None
    es: str | None = None
    fr: str | None = None
    sk: str | None = None


class ImageUrl(WttjModel):
    url: str


class ResponsiveImage(WttjModel):
    url: str
    small: ImageUrl | None = None
    medium: ImageUrl | None = None
    large: ImageUrl | None = None
    thumb: ImageUrl | None = None
    social: ImageUrl | None = None
    preload: ImageUrl | None = None


class FeaturedPage(WttjModel):
    type: str
    slug: str


class Benefit(WttjModel):
    name: LocalizedText
    preview_order: int | None
    reference: str


class BenefitPreview(WttjModel):
    name: LocalizedText
    reference: str


class BenefitCategory(WttjModel):
    benefits: list[Benefit]
    category_ref: str
    name: LocalizedText


class CountryBenefits(WttjModel):
    categories: list[BenefitCategory]
    count: int
    preview: list[BenefitPreview]


class EqualityIndexes(WttjModel):
    equality_among_highest_earners: int | None
    equality_index: int | None
    gap_in_annual_raises: int | None
    gap_in_annual_raises_excluding_promotions: int | None
    gap_in_promotions: int | None
    gender_pay_gap: int | None
    maternity_leave_return_raise: int | None
    published: bool
    workforce_range: str | None
    year: int | None


class Sector(WttjModel):
    name: str
    parent_name: str


class Location(WttjModel):
    address: str
    local_address: str | None
    city: str
    latitude: float
    longitude: float
    country_code: str
    district: str | None
    zip_code: str
    local_district: str | None
    local_city: str | None


class WebsiteOrganization(WttjModel):
    slug: str
    i18n_descriptions: dict[str, str]


class GdprSetting(WttjModel):
    application_message: str | None
    consent_duration: int
    privacy_policy_url: str | None


class ExpansionMetadata(WttjModel):
    expansion_company_url: str | None
    has_enriched_profile: bool


class Organization(WttjModel):
    cover_image: ResponsiveImage | None
    media_facebook: str
    media_website_url: str
    default_language: str
    media_pinterest: str
    equality_indexes: EqualityIndexes
    logo: ResponsiveImage
    media_youtube: str
    media_linkedin: str
    automatic_email: bool
    reference: str
    labels: list[Any]
    sectors: list[Sector]
    headquarter: Location
    turnover: str | None
    video_playlist_provider: str | None
    media_instagram: str
    website_organization: WebsiteOrganization
    playlist_id: str | None
    has_external_ats: bool
    gdpr_setting: GdprSetting
    nb_employees: int | None
    parity_women: int | None
    description: str
    creation_year: int | None
    expansion_metadata: ExpansionMetadata
    revenue: str
    jobs_count: int
    average_age: int | None
    name: str
    industry: str
    parity_men: int | None
    media_twitter: str
    profile_type: str


class ApplicationField(WttjModel):
    id: str
    mode: str
    name: str


class Profession(WttjModel):
    name: LocalizedText
    category: LocalizedText
    sub_category_reference: str
    sub_category_name: LocalizedText
    category_reference: str
    category_name: LocalizedText


class CtaContentProperties(WttjModel):
    title: str | None
    image: ResponsiveImage | None = None
    name: str | None = None
    reference: str | None = None
    source: str | None = None
    organization: Any | None = None
    subtitle: str | None = None
    external_reference: str | None = None
    display: str | None = None


class CtaContentItem(WttjModel):
    id: int
    position: int
    kind: str
    properties: CtaContentProperties


class CtaContent(WttjModel):
    links: list[str]
    contents: list[CtaContentItem]


class Video(WttjModel):
    name: str
    reference: str
    image: ResponsiveImage
    source: str
    external_reference: str


class Skill(WttjModel):
    name: LocalizedText
    reference: str


class Tool(WttjModel):
    name: str
    reference: str


class JobUrl(WttjModel):
    kind: str
    href: str
    language: str


class AtsQuestionBounds(WttjModel):
    max: int | None
    min: int | None


class AtsQuestionFormat(WttjModel):
    bounds: AtsQuestionBounds
    display: str
    type: str


class AtsQuestionText(WttjModel):
    description: str | None
    title: str


class AtsQuestion(WttjModel):
    format: AtsQuestionFormat
    id: str
    index: int
    parent: Any | None
    question: AtsQuestionText
    required: bool


class WttfJob(WttjModel):
    updated_at: str
    wttj_reference: str
    ats: str
    key_missions: list[Any]
    featured_page: FeaturedPage
    archived_at: str | None
    reference: str
    benefits: dict[str, CountryBenefits]
    experience_level: str | None
    team: str | None
    education_level: str | None
    contract_type: str
    organization: Organization
    language: str
    status: str
    is_default: bool
    company_description: str | None
    application_fields: list[ApplicationField]
    remote: str
    profession: Profession
    recruitment_process: str | None
    salary_period: str | None
    salary_currency: str | None
    description: str
    slug: str
    cta_content: CtaContent
    videos: list[Video]
    skills: list[Skill]
    contract_duration_max: int | None
    profile: str | None
    name: str
    urls: list[JobUrl]
    summary: str
    salary_max: int | None
    company_summary: str
    tools: list[Tool]
    offices: list[Location]
    social_image: str
    salary_min: int | None
    published_at: str
    ats_questions: list[AtsQuestion]
    recruiter_proposal: str | None
    start_date: str | None
    office: Location
    apply_url: str
    contract_duration_min: int | None


class WttfJobResponse(WttjModel):
    job: WttfJob


__all__ = [
    "ApplicationField",
    "AtsQuestion",
    "AtsQuestionBounds",
    "AtsQuestionFormat",
    "AtsQuestionText",
    "Benefit",
    "BenefitCategory",
    "BenefitPreview",
    "CountryBenefits",
    "CtaContent",
    "CtaContentItem",
    "CtaContentProperties",
    "EqualityIndexes",
    "ExpansionMetadata",
    "FeaturedPage",
    "GdprSetting",
    "ImageUrl",
    "JobUrl",
    "LocalizedText",
    "Location",
    "Organization",
    "Profession",
    "ResponsiveImage",
    "Sector",
    "Skill",
    "Tool",
    "Video",
    "WebsiteOrganization",
    "WttfJob",
    "WttfJobResponse",
]

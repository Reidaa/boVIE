package main

// Organization is the minimal WTTJ organization projection from the v3 public API.
type Organization struct {
	Name string `json:"name"`
	Slug string `json:"slug"`
}

// SearchHit is one item from GET /api/v3/public/jobs.
type SearchHit struct {
	Reference    string       `json:"reference"`
	Slug         string       `json:"slug"`
	ContractType string       `json:"contract_type"`
	Organization Organization `json:"organization"`
}

// Pagination is the pagination metadata from GET /api/v3/public/jobs.
type Pagination struct {
	Page      int `json:"page"`
	PageCount int `json:"page_count"`
}

// SearchResponse is the response envelope from GET /api/v3/public/jobs.
type SearchResponse struct {
	Data     []SearchHit `json:"data"`
	Metadata Pagination  `json:"metadata"`
}

// Office is an office location in a WTTJ job detail response.
type Office struct {
	// WTTJ sends null for some offices.
	City        *string `json:"city"`
	CountryCode string  `json:"country_code"`
}

// JobDetail is the v3 WTTJ job detail projection.
type JobDetail struct {
	WTTJReference  string       `json:"wttj_reference"`
	Slug           string       `json:"slug"`
	Name           string       `json:"name"`
	ContractType   string       `json:"contract_type"`
	Status         string       `json:"status"`
	Organization   Organization `json:"organization"`
	Offices        []Office     `json:"offices"`
	PublishedAt    string       `json:"published_at"`
	StartDate      *string      `json:"start_date"`
	SalaryMin      *float64     `json:"salary_min"`
	SalaryMax      *float64     `json:"salary_max"`
	SalaryCurrency *string      `json:"salary_currency"`
	SalaryPeriod   *string      `json:"salary_period"`
	ApplyURL       *string      `json:"apply_url"`
}

// DetailResponse is the envelope from GET /api/v3/organizations/{org}/jobs/{slug}.
type DetailResponse struct {
	Job JobDetail `json:"job"`
}

package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"strings"
)

// Board configures one Workday company career site, e.g. https://example.wd1.myworkdayjobs.com/Careers.
type Board struct {
	URL           string              `json:"url"`
	Company       string              `json:"company"`
	SearchText    string              `json:"searchText"`
	AppliedFacets map[string][]string `json:"appliedFacets"`

	host string
	path string
}

// UnmarshalJSON strictly validates Board configuration and rejects unknown fields.
func (b *Board) UnmarshalJSON(data []byte) error {
	type rawBoard struct {
		URL           string              `json:"url"`
		Company       string              `json:"company"`
		SearchText    string              `json:"searchText"`
		AppliedFacets map[string][]string `json:"appliedFacets"`
	}
	var raw rawBoard
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&raw); err != nil {
		return err
	}
	if raw.Company == "" {
		return errors.New("company must not be empty")
	}
	parsed, err := url.Parse(raw.URL)
	if err != nil {
		return errors.New("expected https://<tenant>.<wdN>.myworkdayjobs.com/<site>")
	}
	host := parsed.Hostname()
	labels := strings.Split(host, ".")
	if parsed.Scheme != "https" ||
		len(labels) != 4 ||
		labels[2] != "myworkdayjobs" ||
		labels[3] != "com" ||
		strings.Trim(parsed.Path, "/") == "" {
		return errors.New("expected https://<tenant>.<wdN>.myworkdayjobs.com/<site>")
	}
	facets := raw.AppliedFacets
	if facets == nil {
		facets = map[string][]string{}
	}
	*b = Board{
		URL:           raw.URL,
		Company:       raw.Company,
		SearchText:    raw.SearchText,
		AppliedFacets: facets,
		host:          host,
		path:          parsed.Path,
	}
	return nil
}

// Origin returns https://<host>.
func (b Board) Origin() string {
	return "https://" + b.host
}

// Tenant returns the Workday tenant prefix from the host.
func (b Board) Tenant() string {
	tenant, _, _ := strings.Cut(b.host, ".")
	return tenant
}

// Site returns the Workday site slug (the last path segment, stripping any locale prefix like /en-US/).
func (b Board) Site() string {
	trimmed := strings.TrimRight(b.path, "/")
	idx := strings.LastIndex(trimmed, "/")
	if idx < 0 {
		return trimmed
	}
	return trimmed[idx+1:]
}

// Name returns "<tenant>/<site>".
func (b Board) Name() string {
	return b.Tenant() + "/" + b.Site()
}

// APIURL returns the Workday CXS API base URL for this board.
func (b Board) APIURL() string {
	return fmt.Sprintf("%s/wday/cxs/%s/%s", b.Origin(), b.Tenant(), b.Site())
}

// Posting is one job summary returned by POST .../jobs.
type Posting struct {
	Title        string `json:"title"`
	ExternalPath string `json:"externalPath"`
}

// Validate checks that ExternalPath is a safe /job/... path.
func (p Posting) Validate() error {
	if !strings.HasPrefix(p.ExternalPath, "/job/") || strings.Contains(p.ExternalPath, "..") {
		return errors.New("unexpected workday job path")
	}
	return nil
}

// JobID returns the trailing segment of ExternalPath.
func (p Posting) JobID() string {
	idx := strings.LastIndex(p.ExternalPath, "/")
	if idx < 0 {
		return p.ExternalPath
	}
	return p.ExternalPath[idx+1:]
}

// SearchResponse is the response from POST .../jobs.
type SearchResponse struct {
	// Total is set only on the first page; later pages return 0.
	Total       int       `json:"total"`
	JobPostings []Posting `json:"jobPostings"`
}

// Country holds the ISO alpha-2 country code from a Workday requisition location.
type Country struct {
	Alpha2Code *string `json:"alpha2Code"`
}

// RequisitionLocation wraps Country on a Workday job detail.
type RequisitionLocation struct {
	Country *Country `json:"country"`
}

// JobDetail is the jobPostingInfo projection from GET .../job/...
type JobDetail struct {
	Title                  string               `json:"title"`
	JobPostingID           string               `json:"jobPostingId"`
	Posted                 bool                 `json:"posted"`
	Location               *string              `json:"location"`
	AdditionalLocations    []string             `json:"additionalLocations"`
	StartDate              *string              `json:"startDate"`
	EndDate                *string              `json:"endDate"`
	TimeType               *string              `json:"timeType"`
	JobReqID               *string              `json:"jobReqId"`
	JobRequisitionLocation *RequisitionLocation `json:"jobRequisitionLocation"`
}

// DetailResponse wraps JobDetail.
type DetailResponse struct {
	JobPostingInfo JobDetail `json:"jobPostingInfo"`
}

// Package models defines Business France API models and embedded reference datasets.
package models

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"net/url"
	"strings"
)

//go:embed data/countries.json
var countriesJSON []byte

//go:embed data/geozones.json
var geozonesJSON []byte

//go:embed data/specializations.json
var specializationsJSON []byte

// Country represents a Business France country lookup entry.
type Country struct {
	CountryID        string `json:"countryId"`
	Name             string `json:"countryNameEn"`
	GeographicZoneID string `json:"geographicZoneId"`
}

// GeographicZone represents a Business France region lookup entry.
type GeographicZone struct {
	ID   string `json:"geographicZoneId"`
	Name string `json:"geographicZoneLabelEn"`
}

// Specialization represents a Business France specialization entry.
type Specialization struct {
	ID                    string `json:"specializationId"`
	SpecializationLabel   string `json:"specializationLabel"`
	SpecializationLabelEn string `json:"specializationLabelEn"`
	ParentID              *int   `json:"specializationParentId"`
}

// SearchParameters is the camelCase JSON request body for Business France /search.
type SearchParameters struct {
	ActivitySectorID   []int    `json:"activitySectorId"`
	CompaniesSizes     []string `json:"companiesSizes"`
	CountriesIDs       []string `json:"countriesIds"`
	EntreprisesIDs     []int    `json:"entreprisesIds"`
	GeographicZones    []string `json:"geographicZones"`
	MissionsDurations  []string `json:"missionsDurations"`
	MissionsTypesIDs   []string `json:"missionsTypesIds"`
	SpecializationsIDs []string `json:"specializationsIds"`
	StudiesLevelID     []string `json:"studiesLevelId"`
	MissionStartDate   *string  `json:"missionStartDate"`
	Limit              int      `json:"limit"`
	Query              string   `json:"query"`
	Skip               int      `json:"skip"`
}

// DefaultSearchParameters returns SearchParameters initialized with non-nil empty slices and Limit=10.
func DefaultSearchParameters() SearchParameters {
	return SearchParameters{
		ActivitySectorID:   []int{},
		CompaniesSizes:     []string{},
		CountriesIDs:       []string{},
		EntreprisesIDs:     []int{},
		GeographicZones:    []string{},
		MissionsDurations:  []string{},
		MissionsTypesIDs:   []string{},
		SpecializationsIDs: []string{},
		StudiesLevelID:     []string{},
		Limit:              10,
	}
}

// Normalized returns a copy with nil slices replaced by empty slices so JSON matches the API contract.
func (p SearchParameters) Normalized() SearchParameters {
	if p.ActivitySectorID == nil {
		p.ActivitySectorID = []int{}
	}
	if p.CompaniesSizes == nil {
		p.CompaniesSizes = []string{}
	}
	if p.CountriesIDs == nil {
		p.CountriesIDs = []string{}
	}
	if p.EntreprisesIDs == nil {
		p.EntreprisesIDs = []int{}
	}
	if p.GeographicZones == nil {
		p.GeographicZones = []string{}
	}
	if p.MissionsDurations == nil {
		p.MissionsDurations = []string{}
	}
	if p.MissionsTypesIDs == nil {
		p.MissionsTypesIDs = []string{}
	}
	if p.SpecializationsIDs == nil {
		p.SpecializationsIDs = []string{}
	}
	if p.StudiesLevelID == nil {
		p.StudiesLevelID = []string{}
	}
	return p
}

var businessFranceHosts = map[string]struct{}{
	"businessfrance.fr":                 {},
	"mon-vie-via.businessfrance.fr":     {},
	"civiweb-api-prd.azurewebsites.net": {},
}

// Job holds the Business France offer fields read by the collector.
type Job struct {
	ActivitySectorN1 *string          `json:"activitySectorN1"`
	CityAffectation  string           `json:"cityAffectation"`
	CityName         *string          `json:"cityName"`
	ContactEmail     *string          `json:"contactEmail"`
	ContactName      *string          `json:"contactName"`
	CountryName      string           `json:"countryName"`
	CreationDate     string           `json:"creationDate"`
	ID               int              `json:"id"`
	Indemnite        float64          `json:"indemnite"`
	MissionDuration  int              `json:"missionDuration"`
	MissionEndDate   string           `json:"missionEndDate"`
	MissionStartDate string           `json:"missionStartDate"`
	MissionTitle     string           `json:"missionTitle"`
	OrganizationName string           `json:"organizationName"`
	Specializations  []Specialization `json:"specializations"`
	ContactURL       *string          `json:"contactURL"`
}

// UnmarshalJSON decodes Job, strips whitespace on string fields, and sanitizes ContactName.
func (j *Job) UnmarshalJSON(data []byte) error {
	type rawJob Job
	var raw rawJob
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}
	*j = Job(raw)
	j.Sanitize()
	return nil
}

// Sanitize trims whitespace on string fields and normalizes ContactName.
func (j *Job) Sanitize() {
	j.ActivitySectorN1 = trimStringPtr(j.ActivitySectorN1)
	j.CityAffectation = strings.TrimSpace(j.CityAffectation)
	j.CityName = trimStringPtr(j.CityName)
	j.ContactEmail = trimStringPtr(j.ContactEmail)
	j.CountryName = strings.TrimSpace(j.CountryName)
	j.CreationDate = strings.TrimSpace(j.CreationDate)
	j.MissionEndDate = strings.TrimSpace(j.MissionEndDate)
	j.MissionStartDate = strings.TrimSpace(j.MissionStartDate)
	j.MissionTitle = strings.TrimSpace(j.MissionTitle)
	j.OrganizationName = strings.TrimSpace(j.OrganizationName)
	j.ContactURL = trimStringPtr(j.ContactURL)

	if j.ContactName == nil {
		x := "X"
		j.ContactName = &x
		return
	}
	cleaned := strings.TrimSpace(*j.ContactName)
	cleaned = strings.ReplaceAll(cleaned, "Monsieur", "")
	cleaned = strings.ReplaceAll(cleaned, "Madame", "")
	cleaned = strings.TrimSpace(cleaned)
	if cleaned == "" {
		cleaned = "XXX"
	}
	j.ContactName = &cleaned
}

// ExternalApplicationURL returns ContactURL when it is a valid external http/https URL, else "".
func (j Job) ExternalApplicationURL() string {
	if j.ContactURL == nil || *j.ContactURL == "" {
		return ""
	}
	parsed, err := url.Parse(*j.ContactURL)
	if err != nil {
		return ""
	}
	if (parsed.Scheme != "http" && parsed.Scheme != "https") || parsed.Hostname() == "" {
		return ""
	}
	hostname := strings.TrimPrefix(strings.ToLower(parsed.Hostname()), "www.")
	if _, internal := businessFranceHosts[hostname]; internal {
		return ""
	}
	return *j.ContactURL
}

func trimStringPtr(s *string) *string {
	if s == nil {
		return nil
	}
	trimmed := strings.TrimSpace(*s)
	return &trimmed
}

// Countries, Zones, and Specializations are loaded from the embedded Business France datasets.
var (
	Countries       []Country
	Zones           []GeographicZone
	Specializations []Specialization
)

func init() {
	if err := json.Unmarshal(countriesJSON, &Countries); err != nil {
		panic(fmt.Sprintf("decode embedded countries: %v", err))
	}
	var geoWrapper struct {
		Result []GeographicZone `json:"result"`
	}
	if err := json.Unmarshal(geozonesJSON, &geoWrapper); err != nil {
		panic(fmt.Sprintf("decode embedded geozones: %v", err))
	}
	Zones = geoWrapper.Result

	var specWrapper struct {
		Specializations []Specialization `json:"specializations"`
	}
	if err := json.Unmarshal(specializationsJSON, &specWrapper); err != nil {
		panic(fmt.Sprintf("decode embedded specializations: %v", err))
	}
	Specializations = specWrapper.Specializations
}

// GetZoneNames returns lowercase geographic zone names.
func GetZoneNames() []string {
	names := make([]string, len(Zones))
	for i, z := range Zones {
		names[i] = strings.ToLower(z.Name)
	}
	return names
}

// GetZoneIDFromName returns the zone ID matching name (case-insensitive), or ("", false).
func GetZoneIDFromName(name string) (string, bool) {
	norm := strings.ToLower(strings.TrimSpace(name))
	for _, z := range Zones {
		if strings.ToLower(z.Name) == norm {
			return z.ID, true
		}
	}
	return "", false
}

// GetSpecializationNames returns lowercase specialization English names.
func GetSpecializationNames() []string {
	names := make([]string, len(Specializations))
	for i, s := range Specializations {
		names[i] = strings.ToLower(s.SpecializationLabelEn)
	}
	return names
}

// GetSpecializationIDFromName returns the specialization ID matching name (case-insensitive).
func GetSpecializationIDFromName(name string) (string, bool) {
	norm := strings.ToLower(strings.TrimSpace(name))
	for _, s := range Specializations {
		if strings.ToLower(s.SpecializationLabelEn) == norm {
			return s.ID, true
		}
	}
	return "", false
}

// GetCountriesIDByGeographicZone returns all country IDs belonging to zoneID.
func GetCountriesIDByGeographicZone(zoneID string) []string {
	var ids []string
	for _, c := range Countries {
		if c.GeographicZoneID == zoneID {
			ids = append(ids, c.CountryID)
		}
	}
	return ids
}

// GetCountryNames returns lowercase country names.
func GetCountryNames() []string {
	names := make([]string, len(Countries))
	for i, c := range Countries {
		names[i] = strings.ToLower(c.Name)
	}
	return names
}

// GetCountryIDs returns all known country IDs.
func GetCountryIDs() map[string]struct{} {
	ids := make(map[string]struct{}, len(Countries))
	for _, c := range Countries {
		ids[c.CountryID] = struct{}{}
	}
	return ids
}

// GetCountryCodeFromName returns the ISO country ID matching countryName (case-insensitive).
func GetCountryCodeFromName(countryName string) (string, bool) {
	norm := strings.ToLower(strings.TrimSpace(countryName))
	for _, c := range Countries {
		if strings.ToLower(c.Name) == norm {
			return c.CountryID, true
		}
	}
	return "", false
}

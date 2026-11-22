package main

import (
	"fmt"
	"slices"

	"github.com/Reidaa/boVIE/apps/collector-business-france/models"
)

// SearchConfig holds validated, deterministic search parameters.
type SearchConfig struct {
	Limit           int
	Countries       []string
	Specializations []string
}

// Config wraps the Business France collector search configuration.
type Config struct {
	Search SearchConfig
}

// ConfigFromParams validates CLI/env filter names and expands geographic zones into sorted country IDs.
func ConfigFromParams(limit int, regions, specializations, countries []string) (Config, error) {
	if limit < 1 {
		return Config{}, fmt.Errorf("invalid limit: %d (must be positive)", limit)
	}

	specSet := make(map[string]struct{})
	for _, spe := range specializations {
		speID, ok := models.GetSpecializationIDFromName(spe)
		if !ok {
			return Config{}, fmt.Errorf("invalid specialization: %s", spe)
		}
		specSet[speID] = struct{}{}
	}

	knownCountryIDs := models.GetCountryIDs()
	countrySet := make(map[string]struct{})
	for _, region := range regions {
		zoneID, ok := models.GetZoneIDFromName(region)
		if !ok {
			return Config{}, fmt.Errorf("invalid geographic zone: %s", region)
		}
		for _, countryID := range models.GetCountriesIDByGeographicZone(zoneID) {
			if _, valid := knownCountryIDs[countryID]; !valid {
				return Config{}, fmt.Errorf("invalid country from preset: %s", countryID)
			}
			countrySet[countryID] = struct{}{}
		}
	}

	for _, country := range countries {
		countryID, ok := models.GetCountryCodeFromName(country)
		if !ok {
			return Config{}, fmt.Errorf("invalid country: %s", country)
		}
		countrySet[countryID] = struct{}{}
	}

	// Sorted so the checkpoint scan hash is deterministic across runs.
	sortedSpecs := make([]string, 0, len(specSet))
	for id := range specSet {
		sortedSpecs = append(sortedSpecs, id)
	}
	slices.Sort(sortedSpecs)

	sortedCountries := make([]string, 0, len(countrySet))
	for id := range countrySet {
		sortedCountries = append(sortedCountries, id)
	}
	slices.Sort(sortedCountries)

	return Config{
		Search: SearchConfig{
			Limit:           limit,
			Specializations: sortedSpecs,
			Countries:       sortedCountries,
		},
	}, nil
}

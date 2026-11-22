package main

import (
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/Reidaa/boVIE/apps/collector-business-france/models"
	"github.com/Reidaa/boVIE/packages/offerevents"
)

// DisplayFields normalizes Business France offer fields for discovery events.
func DisplayFields(job models.Job) ([]offerevents.DisplayField, error) {
	start, err := formatISODate(job.MissionStartDate)
	if err != nil {
		return nil, fmt.Errorf("parse missionStartDate %q: %w", job.MissionStartDate, err)
	}
	end, err := formatISODate(job.MissionEndDate)
	if err != nil {
		return nil, fmt.Errorf("parse missionEndDate %q: %w", job.MissionEndDate, err)
	}

	specializations := "N/A"
	if len(job.Specializations) > 0 {
		labels := make([]string, len(job.Specializations))
		for i, s := range job.Specializations {
			labels[i] = s.SpecializationLabel
		}
		specializations = strings.Join(labels, ", ")
	}

	posted := "N/A"
	if job.CreationDate != "" {
		posted, err = formatISODate(job.CreationDate)
		if err != nil {
			return nil, fmt.Errorf("parse creationDate %q: %w", job.CreationDate, err)
		}
	}

	applicationValue := "Business France"
	if externalURL := job.ExternalApplicationURL(); externalURL != "" {
		applicationValue = fmt.Sprintf("[Site externe](%s)", externalURL)
	}

	rawFields := []struct {
		name  string
		value string
	}{
		{":hot_springs: Entreprise", job.OrganizationName},
		{":satellite_orbital: Posté le", posted},
		{":calendar: Durée", fmt.Sprintf("%d mois", job.MissionDuration)},
		{":gear: Secteur", strOrNA(job.ActivitySectorN1)},
		{":world_map: Pays", job.CountryName},
		{":cityscape: Ville", strOrNA(job.CityName)},
		{":money_with_wings: Salaire", strconv.FormatFloat(job.Indemnite, 'f', -1, 64) + "e"},
		{":person_running: Début", start},
		{":checkered_flag: Fin", end},
		{":e_mail: Email", strOrNA(job.ContactEmail)},
		{":person_bald: Contact", strOrNA(job.ContactName)},
		{":globe_with_meridians: Business France", fmt.Sprintf("[Voir offre](https://mon-vie-via.businessfrance.fr/offres/%d)", job.ID)},
		{":outbox_tray: Application", applicationValue},
		{":label: Specialization(s)", specializations},
	}

	// The event contract caps values at 1024 characters, like Discord's embed fields.
	fields := make([]offerevents.DisplayField, 0, len(rawFields))
	for _, f := range rawFields {
		if f.value == "" {
			continue
		}
		fields = append(fields, offerevents.NewDisplayField(
			f.name,
			offerevents.TruncateRunes(f.value, 1024),
		))
	}
	return fields, nil
}

func strOrNA(s *string) string {
	if s == nil || *s == "" {
		return "N/A"
	}
	return *s
}

var isoDateLayouts = []string{
	time.RFC3339Nano,
	time.RFC3339,
	"2006-01-02T15:04:05.999999999",
	"2006-01-02T15:04:05",
	"2006-01-02",
}

func formatISODate(raw string) (string, error) {
	trimmed := strings.TrimSpace(raw)
	for _, layout := range isoDateLayouts {
		if t, err := time.Parse(layout, trimmed); err == nil {
			return t.Format("02/01/2006"), nil
		}
	}
	return "", fmt.Errorf("unsupported ISO date %q", raw)
}

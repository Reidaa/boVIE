package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"github.com/Reidaa/boVIE/apps/collector-business-france/models"
	"github.com/Reidaa/boVIE/packages/collectorstore"
	"github.com/Reidaa/boVIE/packages/offerevents"
	"github.com/joho/godotenv"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(r *http.Request) (*http.Response, error) {
	return f(r)
}

func strPtr(s string) *string { return &s }

func sampleJob(id int) models.Job {
	return models.Job{
		ID:               id,
		MissionTitle:     "Engineer",
		OrganizationName: "Example",
		CountryName:      "Canada",
		CityName:         strPtr("Montreal"),
		MissionStartDate: "2026-06-01",
		MissionEndDate:   "2027-06-01",
		CreationDate:     "2026-05-01",
		MissionDuration:  12,
		ActivitySectorN1: strPtr("Tech"),
		Indemnite:        2500,
		ContactEmail:     strPtr("jobs@example.com"),
		ContactName:      strPtr("Example"),
		Specializations:  []models.Specialization{},
	}
}

func TestGeoZones(t *testing.T) {
	expected := []string{
		"afrique du nord",
		"afrique subsaharienne",
		"amerique du nord",
		"amerique latine",
		"asie et pacifique",
		"europe occidentale",
		"europe centrale et orientale",
		"proche et moyen orient",
	}
	got := models.GetZoneNames()
	slices.Sort(expected)
	slices.Sort(got)
	if !slices.Equal(got, expected) {
		t.Fatalf("GetZoneNames() = %v, want %v", got, expected)
	}
	if id, ok := models.GetZoneIDFromName("afrique du nord"); !ok || id != "7" {
		t.Fatalf("got (%q, %v), want (\"7\", true)", id, ok)
	}
	if id, ok := models.GetZoneIDFromName("EUROPE OCCIDenTALE"); !ok || id != "5" {
		t.Fatalf("got (%q, %v), want (\"5\", true)", id, ok)
	}
}

func TestCountriesByZone(t *testing.T) {
	expected := []string{"BS", "CA", "US"}
	got := models.GetCountriesIDByGeographicZone("2")
	slices.Sort(got)
	if !slices.Equal(got, expected) {
		t.Fatalf("zone 2 countries = %v, want %v", got, expected)
	}
	zoneID, ok := models.GetZoneIDFromName("Amerique du Nord")
	if !ok {
		t.Fatal("Amerique du Nord not found")
	}
	got2 := models.GetCountriesIDByGeographicZone(zoneID)
	slices.Sort(got2)
	if !slices.Equal(got2, expected) {
		t.Fatalf("zone %s countries = %v, want %v", zoneID, got2, expected)
	}
}

func TestConfigFromParams(t *testing.T) {
	cfg, err := ConfigFromParams(100, []string{"AMERIQUE DU NORD"}, []string{"Information Systems"}, nil)
	if err != nil {
		t.Fatalf("ConfigFromParams: %v", err)
	}
	if cfg.Search.Limit != 100 || len(cfg.Search.Specializations) != 1 || len(cfg.Search.Countries) != 3 {
		t.Fatalf("unexpected config: %+v", cfg)
	}

	if _, err := ConfigFromParams(100, []string{"Invalid Region"}, []string{"Information Systems"}, nil); err == nil || !strings.Contains(err.Error(), "invalid geographic zone") {
		t.Fatalf("expected invalid zone error, got %v", err)
	}
	if _, err := ConfigFromParams(100, []string{"AMERIQUE DU NORD"}, []string{"Invalid Specialization"}, nil); err == nil || !strings.Contains(err.Error(), "invalid specialization") {
		t.Fatalf("expected invalid specialization error, got %v", err)
	}
	if _, err := ConfigFromParams(100, []string{"AMERIQUE DU NORD"}, []string{"Information Systems"}, []string{"Invalid Country"}); err == nil || !strings.Contains(err.Error(), "invalid country") {
		t.Fatalf("expected invalid country error, got %v", err)
	}
	if _, err := ConfigFromParams(-10, []string{"AMERIQUE DU NORD"}, []string{"Information Systems"}, nil); err == nil {
		t.Fatal("expected invalid limit error")
	}

	// Verify countries lookup works case-insensitively (e.g. "canada").
	cfgCountry, err := ConfigFromParams(10, nil, nil, []string{"canada"})
	if err != nil || !slices.Equal(cfgCountry.Search.Countries, []string{"CA"}) {
		t.Fatalf("expected canada -> [CA], got %+v, err=%v", cfgCountry.Search.Countries, err)
	}

	// Verify sorted IDs.
	sortedCfg, err := ConfigFromParams(
		10,
		[]string{"Europe Occidentale", "Asie et Pacifique"},
		[]string{"Information Systems", "Business", "Marketing Communication"},
		nil,
	)
	if err != nil {
		t.Fatalf("sorted config: %v", err)
	}
	if !slices.IsSorted(sortedCfg.Search.Countries) || !slices.IsSorted(sortedCfg.Search.Specializations) {
		t.Fatalf("expected sorted IDs, got countries=%v specs=%v", sortedCfg.Search.Countries, sortedCfg.Search.Specializations)
	}
}

func TestJobModelAndExternalURL(t *testing.T) {
	ext := "https://prose.com/careers?ashby_jid=d93116e8"
	if got := (models.Job{ContactURL: strPtr(ext)}).ExternalApplicationURL(); got != ext {
		t.Fatalf("expected %q, got %q", ext, got)
	}
	if got := (models.Job{ContactURL: strPtr("https://mon-vie-via.businessfrance.fr/offres/244342")}).ExternalApplicationURL(); got != "" {
		t.Fatalf("expected empty for internal URL, got %q", got)
	}
	if got := (models.Job{ContactURL: strPtr("")}).ExternalApplicationURL(); got != "" {
		t.Fatalf("expected empty for blank URL, got %q", got)
	}

	raw := `{
		"id": 1,
		"missionTitle": "  Engineer  ",
		"organizationName": "Example",
		"countryName": "Canada",
		"cityName": "Montreal",
		"cityAffectation": "Montreal",
		"missionStartDate": "2026-06-01",
		"missionEndDate": "2027-06-01",
		"creationDate": "2026-05-01",
		"missionDuration": 12,
		"activitySectorN1": "Tech",
		"indemnite": 2500,
		"contactEmail": null,
		"contactName": null,
		"specializations": null,
		"viewCounter": "unexpected"
	}`
	var parsed models.Job
	if err := json.Unmarshal([]byte(raw), &parsed); err != nil {
		t.Fatalf("unmarshal job: %v", err)
	}
	if parsed.MissionTitle != "Engineer" {
		t.Fatalf("expected trimmed title 'Engineer', got %q", parsed.MissionTitle)
	}
	if parsed.ContactName == nil || *parsed.ContactName != "X" {
		t.Fatalf("expected sanitized nil contactName 'X', got %v", parsed.ContactName)
	}
}

func TestDisplayFieldsAndNormalization(t *testing.T) {
	j := sampleJob(123)
	j.MissionStartDate = "2026-06-01T00:00:00"
	j.MissionEndDate = "2027-06-01T00:00:00"
	j.CreationDate = "2026-05-31T00:00:00"
	j.Specializations = []models.Specialization{
		{ID: "24", SpecializationLabel: "SYSTEMES ET LOGICIELS INFORMATIQUES", SpecializationLabelEn: "INFORMATION SYSTEMS"},
		{ID: "216", SpecializationLabel: "MARKETING - COMMUNICATION", SpecializationLabelEn: "MARKETING COMMUNICATION"},
	}

	fields, err := DisplayFields(j)
	if err != nil {
		t.Fatalf("DisplayFields: %v", err)
	}
	if len(fields) != 14 {
		t.Fatalf("expected 14 display fields, got %d", len(fields))
	}
	fieldMap := make(map[string]offerevents.DisplayField, len(fields))
	for _, f := range fields {
		fieldMap[f.Name] = f
	}
	if got := fieldMap[":label: Specialization(s)"].Value; got != "SYSTEMES ET LOGICIELS INFORMATIQUES, MARKETING - COMMUNICATION" {
		t.Fatalf("unexpected specializations field: %q", got)
	}
	if got := fieldMap[":outbox_tray: Application"].Value; got != "Business France" {
		t.Fatalf("unexpected application field: %q", got)
	}

	extURL := "https://prose.com/careers?ashby_jid=d93116e8"
	j.ContactURL = strPtr(extURL)
	extFields, err := DisplayFields(j)
	if err != nil {
		t.Fatalf("DisplayFields external: %v", err)
	}
	var appVal string
	for _, f := range extFields {
		if f.Name == ":outbox_tray: Application" {
			appVal = f.Value
		}
	}
	if appVal != "[Site externe]("+extURL+")" {
		t.Fatalf("expected external link, got %q", appVal)
	}

	// Long display value truncation.
	longJob := sampleJob(1)
	longJob.ContactEmail = strPtr(strings.Repeat("x", 2000))
	ev, err := Normalize(longJob)
	if err != nil {
		t.Fatalf("Normalize long: %v", err)
	}
	maxLen := 0
	for _, f := range ev.Offer.Fields {
		if len(f.Value) > maxLen {
			maxLen = len(f.Value)
		}
	}
	if maxLen != 1024 {
		t.Fatalf("expected max field value length 1024, got %d", maxLen)
	}
}

func makeResponse(status int, body string) *http.Response {
	return &http.Response{
		StatusCode: status,
		Body:       io.NopCloser(strings.NewReader(body)),
		Header:     make(http.Header),
	}
}

func TestBusinessFranceAPIKeyRotationAndDetails(t *testing.T) {
	t.Run("public site key unescaping and camelCase fields", func(t *testing.T) {
		t.Setenv("BUSINESS_FRANCE_API_KEY", "")
		c := NewAPIClient()
		c.HTTPClient = &http.Client{
			Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
				if r.URL.String() == DefaultPublicOffersURL {
					return makeResponse(200, `<script>config:{API_KEY:"public\/key"}</script>`), nil
				}
				if !strings.HasSuffix(r.URL.Path, "/search") {
					t.Fatalf("unexpected path: %s", r.URL.Path)
				}
				if got := r.Header.Get("X-API-KEY"); got != "public/key" {
					t.Fatalf("X-API-KEY = %q, want public/key", got)
				}
				var body map[string]any
				if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
					t.Fatalf("decode search body: %v", err)
				}
				zones, ok := body["geographicZones"].([]any)
				if !ok || len(zones) != 1 || zones[0] != "5" {
					t.Fatalf("unexpected geographicZones: %#v", body["geographicZones"])
				}
				return makeResponse(200, `{"result":[{"id":42}]}`), nil
			}),
		}

		params := models.DefaultSearchParameters()
		params.GeographicZones = []string{"5"}
		ids, err := c.SearchID(context.Background(), params)
		if err != nil {
			t.Fatalf("SearchID: %v", err)
		}
		if !slices.Equal(ids, []int{42}) {
			t.Fatalf("ids = %v, want [42]", ids)
		}
	})

	t.Run("rotated key retried once with same body", func(t *testing.T) {
		t.Setenv("BUSINESS_FRANCE_API_KEY", "")
		keys := []string{"old", "new"}
		keyIdx := 0
		var sentKeys []string
		var sentBodies []map[string]any

		c := NewAPIClient()
		c.HTTPClient = &http.Client{
			Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
				if r.URL.String() == DefaultPublicOffersURL {
					k := keys[keyIdx]
					keyIdx++
					return makeResponse(200, `<script>config:{API_KEY:"`+k+`"}</script>`), nil
				}
				k := r.Header.Get("X-API-KEY")
				sentKeys = append(sentKeys, k)
				var body map[string]any
				_ = json.NewDecoder(r.Body).Decode(&body)
				sentBodies = append(sentBodies, body)
				if k == "old" {
					return makeResponse(401, ""), nil
				}
				return makeResponse(200, `{"result":[{"id":7}]}`), nil
			}),
		}

		params := models.DefaultSearchParameters()
		params.Limit = 3
		ids, err := c.SearchID(context.Background(), params)
		if err != nil {
			t.Fatalf("SearchID: %v", err)
		}
		if !slices.Equal(ids, []int{7}) {
			t.Fatalf("ids = %v, want [7]", ids)
		}
		if !slices.Equal(sentKeys, []string{"old", "new"}) {
			t.Fatalf("sentKeys = %v, want [old new]", sentKeys)
		}
		if sentBodies[0]["limit"] != float64(3) || sentBodies[1]["limit"] != float64(3) {
			t.Fatalf("retry lost body limit: %+v", sentBodies)
		}
	})

	t.Run("configured key used without hitting public site and stale key refreshed once", func(t *testing.T) {
		t.Setenv("BUSINESS_FRANCE_API_KEY", "stale")
		var sent []string
		siteHits := 0
		c := NewAPIClient()
		c.HTTPClient = &http.Client{
			Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
				if r.URL.String() == DefaultPublicOffersURL {
					siteHits++
					return makeResponse(200, `<script>config:{API_KEY:"public"}</script>`), nil
				}
				sent = append(sent, r.Header.Get("X-API-KEY"))
				if r.Header.Get("X-API-KEY") == "stale" {
					return makeResponse(401, ""), nil
				}
				return makeResponse(200, `{"result":[]}`), nil
			}),
		}

		if _, err := c.SearchID(context.Background(), models.DefaultSearchParameters()); err != nil {
			t.Fatalf("first SearchID: %v", err)
		}
		if _, err := c.SearchID(context.Background(), models.DefaultSearchParameters()); err != nil {
			t.Fatalf("second SearchID: %v", err)
		}
		if !slices.Equal(sent, []string{"stale", "public", "public"}) || siteHits != 1 {
			t.Fatalf("sent=%v siteHits=%d", sent, siteHits)
		}
	})

	t.Run("second 401 fails, 404 and 410 return nil, 503 fails", func(t *testing.T) {
		t.Setenv("BUSINESS_FRANCE_API_KEY", "")
		c := NewAPIClient()
		c.HTTPClient = &http.Client{
			Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
				if r.URL.String() == DefaultPublicOffersURL {
					return makeResponse(200, `<script>config:{API_KEY:"bad"}</script>`), nil
				}
				return makeResponse(401, ""), nil
			}),
		}
		if _, err := c.SearchID(context.Background(), models.DefaultSearchParameters()); err == nil {
			t.Fatal("expected error on repeated 401")
		}

		for _, status := range []int{404, 410} {
			c2 := NewAPIClient()
			c2.apiKey = "key"
			c2.HTTPClient = &http.Client{
				Transport: roundTripFunc(func(_ *http.Request) (*http.Response, error) {
					return makeResponse(status, ""), nil
				}),
			}
			got, err := c2.GetFromID(context.Background(), 9)
			if err != nil || got != nil {
				t.Fatalf("status %d: expected (nil, nil), got (%v, %v)", status, got, err)
			}
		}

		c3 := NewAPIClient()
		c3.apiKey = "key"
		c3.HTTPClient = &http.Client{
			Transport: roundTripFunc(func(_ *http.Request) (*http.Response, error) {
				return makeResponse(503, ""), nil
			}),
		}
		if _, err := c3.GetFromID(context.Background(), 9); err == nil {
			t.Fatal("expected error on 503")
		}
	})
}

type fakeStore struct {
	seenIDs    map[string]bool
	recorded   []offerevents.OfferEvent
	hasResults bool
	silent     bool
}

func (s *fakeStore) Seen(_ context.Context, id string) (bool, error) {
	return s.seenIDs[id], nil
}

func (s *fakeStore) RecordPage(_ context.Context, published []offerevents.OfferEvent, observed []string, _ string, _ int) error {
	for _, ev := range published {
		s.seenIDs[ev.SourceOfferID] = true
		s.recorded = append(s.recorded, ev)
	}
	if len(observed) > 0 {
		s.hasResults = true
	}
	return nil
}

func (s *fakeStore) RequireRecentResults(_ context.Context, _ string) error {
	if s.silent || !s.hasResults {
		return collectorstore.ErrSourceSilent
	}
	return nil
}

type fakeOfferSource struct {
	search func(models.SearchParameters) ([]int, error)
	get    func(int) (*models.Job, error)
}

func (s fakeOfferSource) SearchID(_ context.Context, p models.SearchParameters) ([]int, error) {
	return s.search(p)
}

func (s fakeOfferSource) GetFromID(_ context.Context, id int) (*models.Job, error) {
	return s.get(id)
}

func TestTaskReplayFailedPublishAndSilentSource(t *testing.T) {
	store := &fakeStore{seenIDs: map[string]bool{}}
	src := fakeOfferSource{
		search: func(p models.SearchParameters) ([]int, error) {
			if p.Skip == 0 {
				return []int{1, 2}, nil
			}
			return []int{3}, nil
		},
		get: func(id int) (*models.Job, error) {
			if id == 3 {
				return nil, errors.New("upstream failure")
			}
			j := sampleJob(id)
			return &j, nil
		},
	}

	var published []offerevents.OfferEvent
	params := models.DefaultSearchParameters()
	params.Limit = 3
	err := Task(context.Background(), params, store, src, func(_ context.Context, ev offerevents.OfferEvent) error {
		published = append(published, ev)
		return nil
	}, 2)
	if err == nil {
		t.Fatal("expected upstream failure")
	}
	if len(published) != 2 {
		t.Fatalf("expected 2 published offers before page 2 failure, got %d", len(published))
	}

	// Recover and replay: only offer 3 should be published.
	src.get = func(id int) (*models.Job, error) {
		j := sampleJob(id)
		return &j, nil
	}
	if err := Task(context.Background(), params, store, src, func(_ context.Context, ev offerevents.OfferEvent) error {
		published = append(published, ev)
		return nil
	}, 2); err != nil {
		t.Fatalf("replay Task: %v", err)
	}
	if len(published) != 3 || published[2].SourceOfferID != "3" {
		t.Fatalf("unexpected published offers after replay: %+v", published)
	}

	// First run with zero results fails with ErrSourceSilent.
	emptyStore := &fakeStore{seenIDs: map[string]bool{}}
	emptySrc := fakeOfferSource{
		search: func(_ models.SearchParameters) ([]int, error) { return []int{}, nil },
		get:    func(id int) (*models.Job, error) { return nil, nil },
	}
	params1 := models.DefaultSearchParameters()
	params1.Limit = 1
	err = Task(context.Background(), params1, emptyStore, emptySrc, func(_ context.Context, _ offerevents.OfferEvent) error { return nil }, 25)
	if !errors.Is(err, collectorstore.ErrSourceSilent) {
		t.Fatalf("expected ErrSourceSilent, got %v", err)
	}
}

func TestBusinessFranceCLI(t *testing.T) {
	// Loads .env before resolving options.
	tmp := t.TempDir()
	if err := os.WriteFile(filepath.Join(tmp, ".env"), []byte("BUSINESS_FRANCE_LIMIT=7\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	origWD, _ := os.Getwd()
	if err := os.Chdir(tmp); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = os.Chdir(origWD) }()

	for _, name := range []string{"BUSINESS_FRANCE_LIMIT", "BUSINESS_FRANCE_REGION", "BUSINESS_FRANCE_COUNTRY", "BUSINESS_FRANCE_SPECIALIZATION"} {
		t.Setenv(name, "")
		_ = os.Unsetenv(name)
	}

	var observedLimit int
	var stdout, stderr bytes.Buffer
	code := runCLI(nil, &stdout, &stderr, cliDeps{
		runTask: func(_ context.Context, params models.SearchParameters) error {
			observedLimit = params.Limit
			return nil
		},
	})
	if code != 0 || observedLimit != 7 {
		t.Fatalf("code=%d limit=%d stderr=%s", code, observedLimit, stderr.String())
	}

	// Version flag.
	stdout.Reset()
	stderr.Reset()
	code = runCLI([]string{"--version"}, &stdout, &stderr, cliDeps{})
	if code != 0 || strings.TrimSpace(stdout.String()) != "Bovie "+Version {
		t.Fatalf("version output = %q (code %d)", stdout.String(), code)
	}

	// Failure logs INFO on stdout and ERROR on stderr.
	stdout.Reset()
	stderr.Reset()
	code = runCLI(nil, &stdout, &stderr, cliDeps{
		runTask: func(_ context.Context, _ models.SearchParameters) error {
			return errors.New("source down")
		},
	})
	if code == 0 {
		t.Fatal("expected non-zero exit on task failure")
	}
	if !strings.Contains(stdout.String(), "| INFO     |") || !strings.Contains(stdout.String(), "Starting") {
		t.Fatalf("expected INFO Starting on stdout, got %q", stdout.String())
	}
	if !strings.Contains(stderr.String(), "| ERROR    |") || !strings.Contains(stderr.String(), "source down") {
		t.Fatalf("expected ERROR source down on stderr, got %q", stderr.String())
	}
	if strings.Contains(stdout.String(), "| ERROR    |") {
		t.Fatalf("ERROR leaked to stdout: %q", stdout.String())
	}

	// .env.example values are accepted.
	if err := os.Chdir(origWD); err != nil {
		t.Fatal(err)
	}
	exampleEnv, err := godotenv.Read(filepath.Join("..", "..", ".env.example"))
	if err != nil {
		t.Fatalf("read .env.example: %v", err)
	}
	for k, v := range exampleEnv {
		t.Setenv(k, v)
	}
	var exampleParams models.SearchParameters
	stdout.Reset()
	stderr.Reset()
	code = runCLI(nil, &stdout, &stderr, cliDeps{
		runTask: func(_ context.Context, params models.SearchParameters) error {
			exampleParams = params
			return nil
		},
	})
	if code != 0 {
		t.Fatalf(".env.example rejected: code=%d stderr=%s", code, stderr.String())
	}
	if exampleParams.Limit != 25 || len(exampleParams.CountriesIDs) == 0 {
		t.Fatalf("unexpected params from .env.example: %+v", exampleParams)
	}
}

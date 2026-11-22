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

	"github.com/Reidaa/boVIE/packages/collectorstore"
	"github.com/Reidaa/boVIE/packages/offerevents"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(r *http.Request) (*http.Response, error) {
	return f(r)
}

func jsonResponse(status int, payload any) *http.Response {
	raw, _ := json.Marshal(payload)
	return &http.Response{
		StatusCode: status,
		Body:       io.NopCloser(bytes.NewReader(raw)),
		Header:     http.Header{"Content-Type": []string{"application/json"}},
	}
}

func sampleHit(id, contract string) map[string]any {
	if contract == "" {
		contract = "vie"
	}
	return map[string]any{
		"reference":     id,
		"slug":          id,
		"contract_type": contract,
		"organization":  map[string]any{"name": "Example", "slug": "example"},
	}
}

func sampleDetail(id, contract string) map[string]any {
	if contract == "" {
		contract = "vie"
	}
	return map[string]any{
		"job": map[string]any{
			"wttj_reference": id,
			"slug":           id,
			"name":           "Engineer",
			"contract_type":  contract,
			"status":         "published",
			"organization":   map[string]any{"name": "Example", "slug": "example"},
			"offices":        []map[string]any{{"city": "Montreal", "country_code": "CA"}},
			"published_at":   "2026-09-01T00:00:00Z",
			"salary_min":     2500,
		},
	}
}

type fakeStore struct {
	seen       map[string]bool
	hasResults bool
}

func (s *fakeStore) Seen(_ context.Context, id string) (bool, error) { return s.seen[id], nil }
func (s *fakeStore) RecordPage(_ context.Context, published []offerevents.OfferEvent, observed []string, _ string, _ int) error {
	for _, ev := range published {
		s.seen[ev.SourceOfferID] = true
	}
	if len(observed) > 0 {
		s.hasResults = true
	}
	return nil
}
func (s *fakeStore) RequireRecentResults(_ context.Context, _ string) error {
	if !s.hasResults {
		return collectorstore.ErrSourceSilent
	}
	return nil
}

func TestAllContractTypesCollectedByDefault(t *testing.T) {
	contracts := []string{
		"full_time", "part_time", "temporary", "internship",
		"apprenticeship", "freelance", "vie", "future_contract_type",
	}
	for _, contract := range contracts {
		t.Run(contract, func(t *testing.T) {
			store := &fakeStore{seen: map[string]bool{}}
			client := &http.Client{
				Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
					if strings.HasSuffix(r.URL.Path, "/public/jobs") {
						if r.URL.Query().Get("job_title") != "" {
							t.Fatalf("expected empty job_title, got %q", r.URL.Query().Get("job_title"))
						}
						if r.URL.Query().Has("contract_type") {
							t.Fatal("contract_type must not be sent")
						}
						return jsonResponse(200, map[string]any{
							"data":     []any{sampleHit("job", contract)},
							"metadata": map[string]any{"page": 1, "page_count": 1},
						}), nil
					}
					return jsonResponse(200, sampleDetail("job", contract)), nil
				}),
			}
			var recorded []offerevents.OfferEvent
			err := Collect(context.Background(), store, "https://example.invalid", client, func(_ context.Context, ev offerevents.OfferEvent) error {
				recorded = append(recorded, ev)
				return nil
			}, CollectOptions{})
			if err != nil {
				t.Fatalf("Collect: %v", err)
			}
			if len(recorded) != 1 || recorded[0].SourceOfferID != "job" {
				t.Fatalf("unexpected recorded: %+v", recorded)
			}
			var gotContract string
			for _, f := range recorded[0].Offer.Fields {
				if f.Name == "Contrat" {
					gotContract = f.Value
				}
			}
			if gotContract != contract {
				t.Fatalf("Contrat = %q, want %q", gotContract, contract)
			}
		})
	}
}

func TestOptionalFiltersAndPublicationStatus(t *testing.T) {
	store := &fakeStore{seen: map[string]bool{"seen": true}}
	var fetched []string
	client := &http.Client{
		Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			if strings.HasSuffix(r.URL.Path, "/public/jobs") {
				if r.URL.Query().Get("job_title") != "engineer" {
					t.Fatalf("job_title = %q", r.URL.Query().Get("job_title"))
				}
				return jsonResponse(200, map[string]any{
					"data": []any{
						sampleHit("selected", "full_time"),
						sampleHit("intern", "internship"),
						sampleHit("excluded", "vie"),
						sampleHit("changed", "full_time"),
						sampleHit("draft", "full_time"),
						sampleHit("abroad", "full_time"),
						sampleHit("seen", "full_time"),
					},
					"metadata": map[string]any{"page": 1, "page_count": 1},
				}), nil
			}
			id := r.URL.Path[strings.LastIndex(r.URL.Path, "/")+1:]
			fetched = append(fetched, id)
			contract := "full_time"
			if id == "intern" {
				contract = "internship"
			}
			d := sampleDetail(id, contract)
			job := d["job"].(map[string]any)
			switch id {
			case "changed":
				job["contract_type"] = "vie"
			case "draft":
				job["status"] = "draft"
			case "abroad":
				job["offices"] = []map[string]any{{"city": "Paris", "country_code": "FR"}}
			case "selected":
				job["offices"] = []map[string]any{
					{"city": "Paris", "country_code": "FR"},
					{"city": "Montreal", "country_code": "CA"},
				}
			}
			return jsonResponse(200, d), nil
		}),
	}

	var ids []string
	err := Collect(context.Background(), store, "https://example.invalid", client, func(_ context.Context, ev offerevents.OfferEvent) error {
		ids = append(ids, ev.SourceOfferID)
		return nil
	}, CollectOptions{
		Query:     "engineer",
		Countries: []string{"CA"},
		Contracts: []string{"full_time", "internship"},
	})
	if err != nil {
		t.Fatalf("Collect: %v", err)
	}
	if !slices.Equal(ids, []string{"selected", "intern"}) {
		t.Fatalf("ids = %v, want [selected intern]", ids)
	}
	if slices.Contains(fetched, "excluded") || slices.Contains(fetched, "seen") {
		t.Fatalf("should not fetch excluded or seen hits: %v", fetched)
	}
}

func TestPlaceholderTitleAndNullCity(t *testing.T) {
	store := &fakeStore{seen: map[string]bool{}}
	client := &http.Client{
		Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			if strings.HasSuffix(r.URL.Path, "/public/jobs") {
				return jsonResponse(200, map[string]any{
					"data":     []any{sampleHit("derived", "vie"), sampleHit("unusable", "vie")},
					"metadata": map[string]any{"page": 1, "page_count": 1},
				}), nil
			}
			id := r.URL.Path[strings.LastIndex(r.URL.Path, "/")+1:]
			d := sampleDetail(id, "vie")
			job := d["job"].(map[string]any)
			job["name"] = " $1 "
			if id == "derived" {
				job["slug"] = "network-security-implementation-specialist_milan_ND_wZVZKeo"
			} else {
				job["slug"] = "_milan_ND_wZVZKeo"
			}
			return jsonResponse(200, d), nil
		}),
	}
	var recorded []offerevents.OfferEvent
	if err := Collect(context.Background(), store, "https://example.invalid", client, func(_ context.Context, ev offerevents.OfferEvent) error {
		recorded = append(recorded, ev)
		return nil
	}, CollectOptions{}); err != nil {
		t.Fatalf("Collect: %v", err)
	}
	if len(recorded) != 1 || recorded[0].SourceOfferID != "derived" {
		t.Fatalf("unexpected recorded: %+v", recorded)
	}
	if recorded[0].Offer.Title != "Network security implementation specialist" {
		t.Fatalf("title = %q", recorded[0].Offer.Title)
	}

	// Null office city -> N/A.
	job := JobDetail{
		WTTJReference: "no-city",
		Slug:          "no-city",
		Name:          "Engineer",
		ContractType:  "vie",
		Status:        "published",
		Organization:  Organization{Name: "Example", Slug: "example"},
		Offices:       []Office{{City: nil, CountryCode: "FR"}},
		PublishedAt:   "2026-09-01T00:00:00Z",
	}
	ev, err := Normalize(job, job.Name)
	if err != nil {
		t.Fatalf("Normalize: %v", err)
	}
	if ev.Offer.City != "N/A" || ev.Offer.Country != "FR" || ev.Offer.Fields[1].Value != "N/A (FR)" {
		t.Fatalf("unexpected null-city normalization: %+v", ev.Offer)
	}
}

func TestWTTJRemovedOfferSkippedAndSilentRunFails(t *testing.T) {
	store := &fakeStore{seen: map[string]bool{}}
	client := &http.Client{
		Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			if strings.HasSuffix(r.URL.Path, "/public/jobs") {
				return jsonResponse(200, map[string]any{
					"data":     []any{sampleHit("first", "vie"), sampleHit("second", "vie")},
					"metadata": map[string]any{"page": 1, "page_count": 1},
				}), nil
			}
			if strings.HasSuffix(r.URL.Path, "/first") {
				return jsonResponse(404, nil), nil
			}
			return jsonResponse(200, sampleDetail("second", "vie")), nil
		}),
	}
	var ids []string
	if err := Collect(context.Background(), store, "https://example.invalid", client, func(_ context.Context, ev offerevents.OfferEvent) error {
		ids = append(ids, ev.SourceOfferID)
		return nil
	}, CollectOptions{}); err != nil {
		t.Fatalf("Collect: %v", err)
	}
	if !slices.Equal(ids, []string{"second"}) {
		t.Fatalf("ids = %v, want [second]", ids)
	}

	emptyStore := &fakeStore{seen: map[string]bool{}}
	emptyClient := &http.Client{
		Transport: roundTripFunc(func(_ *http.Request) (*http.Response, error) {
			return jsonResponse(200, map[string]any{
				"data":     []any{},
				"metadata": map[string]any{"page": 1, "page_count": 1},
			}), nil
		}),
	}
	err := Collect(context.Background(), emptyStore, "https://example.invalid", emptyClient, func(_ context.Context, _ offerevents.OfferEvent) error { return nil }, CollectOptions{})
	if !errors.Is(err, collectorstore.ErrSourceSilent) {
		t.Fatalf("expected ErrSourceSilent, got %v", err)
	}
}

func TestWTTJCLI(t *testing.T) {
	tmp := t.TempDir()
	origWD, _ := os.Getwd()
	if err := os.Chdir(tmp); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = os.Chdir(origWD) }()

	for _, name := range []string{"WTTJ_QUERY", "WTTJ_CONTRACTS", "WTTJ_LIMIT", "WTTJ_MAX_PAGES"} {
		t.Setenv(name, "")
		_ = os.Unsetenv(name)
	}

	var got CollectOptions
	var stdout, stderr bytes.Buffer
	deps := cliDeps{
		runCollect: func(_ context.Context, opts CollectOptions) error {
			got = opts
			return nil
		},
	}

	if code := runCLI(nil, &stdout, &stderr, deps); code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr.String())
	}
	if got.Query != "" || len(got.Contracts) != 0 {
		t.Fatalf("unexpected defaults: %+v", got)
	}

	if err := os.WriteFile(filepath.Join(tmp, ".env"), []byte("WTTJ_QUERY=engineer\nWTTJ_CONTRACTS=full_time internship\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if code := runCLI(nil, &stdout, &stderr, deps); code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr.String())
	}
	if got.Query != "engineer" || !slices.Equal(got.Contracts, []string{"full_time", "internship"}) {
		t.Fatalf("unexpected dotenv opts: %+v", got)
	}

	if code := runCLI([]string{"--contract", "FREELANCE", "--country", "ca"}, &stdout, &stderr, deps); code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr.String())
	}
	if !slices.Equal(got.Contracts, []string{"freelance"}) || !slices.Equal(got.Countries, []string{"CA"}) {
		t.Fatalf("unexpected flag opts: %+v", got)
	}
}

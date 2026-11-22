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

func (f roundTripFunc) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

func jsonResponse(status int, payload any) *http.Response {
	raw, _ := json.Marshal(payload)
	return &http.Response{
		StatusCode: status,
		Body:       io.NopCloser(bytes.NewReader(raw)),
		Header:     http.Header{"Content-Type": []string{"application/json"}},
	}
}

func makeBoard(t *testing.T, raw string) Board {
	t.Helper()
	var b Board
	if err := json.Unmarshal([]byte(raw), &b); err != nil {
		t.Fatalf("unmarshal board: %v", err)
	}
	return b
}

func defaultBoard(t *testing.T) Board {
	t.Helper()
	return makeBoard(t, `{"url":"https://example.wd3.myworkdayjobs.com/en-US/Careers","company":"Example"}`)
}

func samplePosting(id string) map[string]any {
	return map[string]any{
		"title":         "Engineer",
		"externalPath":  "/job/Paris/" + id,
		"locationsText": "Paris",
		"postedOn":      "Posted Today",
	}
}

func sampleDetail(id string, posted bool) map[string]any {
	return map[string]any{
		"jobPostingInfo": map[string]any{
			"id":                  "0123456789abcdef",
			"title":               " Data Engineer ",
			"location":            "Paris",
			"additionalLocations": []string{"Lyon"},
			"startDate":           "2026-10-27",
			"endDate":             "2026-11-05",
			"timeType":            "Full time",
			"jobReqId":            "R1",
			"jobPostingId":        id,
			"posted":              posted,
			"jobRequisitionLocation": map[string]any{
				"descriptor": "Paris",
				"country":    map[string]any{"descriptor": "France", "alpha2Code": "FR"},
			},
		},
	}
}

func servePages(totalOverride *int, pages ...[]map[string]any) roundTripFunc {
	size := 0
	if len(pages) > 0 {
		size = len(pages[0])
	}
	return func(r *http.Request) (*http.Response, error) {
		if r.Method == http.MethodPost {
			var body map[string]any
			_ = json.NewDecoder(r.Body).Decode(&body)
			offset := int(body["offset"].(float64))
			idx := 0
			if size > 0 {
				idx = offset / size
			}
			var page []map[string]any
			if len(pages) > 0 {
				if idx < len(pages) {
					page = pages[idx]
				} else {
					page = pages[0]
				}
			}
			count := 0
			for _, p := range pages {
				count += len(p)
			}
			if totalOverride != nil {
				count = *totalOverride
			}
			respTotal := 0
			if offset == 0 {
				respTotal = count
			}
			return jsonResponse(200, map[string]any{
				"total":       respTotal,
				"jobPostings": page,
			}), nil
		}
		id := r.URL.Path[strings.LastIndex(r.URL.Path, "/")+1:]
		return jsonResponse(200, sampleDetail(id, true)), nil
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

func TestBoardParsingAndValidation(t *testing.T) {
	b := defaultBoard(t)
	if b.APIURL() != "https://example.wd3.myworkdayjobs.com/wday/cxs/example/Careers" {
		t.Fatalf("APIURL = %q", b.APIURL())
	}
	if b.Tenant() != "example" || b.Site() != "Careers" {
		t.Fatalf("tenant=%q site=%q", b.Tenant(), b.Site())
	}
	var bad Board
	if err := json.Unmarshal([]byte(`{"url":"https://example.com/Careers","company":"Ex"}`), &bad); err == nil {
		t.Fatal("expected error for non-workday host")
	}
	if err := json.Unmarshal([]byte(`{"url":"https://example.wd3.myworkdayjobs.com/","company":"Ex"}`), &bad); err == nil {
		t.Fatal("expected error for missing site")
	}
	for _, empty := range []string{"", "  ", "[]"} {
		if _, err := LoadBoards(empty); err == nil || !strings.Contains(err.Error(), "WORKDAY_BOARDS") {
			t.Fatalf("LoadBoards(%q) err = %v", empty, err)
		}
	}
}

func TestDetailNormalization(t *testing.T) {
	raw, _ := json.Marshal(sampleDetail("Data-Engineer_R1", true))
	var resp DetailResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatal(err)
	}
	ev, err := Normalize(defaultBoard(t), "/job/Paris/Data-Engineer_R1", resp.JobPostingInfo)
	if err != nil {
		t.Fatalf("Normalize: %v", err)
	}
	if ev.Source != offerevents.SourceWorkday ||
		ev.SourceOfferID != "example/Careers/Data-Engineer_R1" ||
		ev.Offer.Title != "Data Engineer" ||
		ev.Offer.Country != "FR" ||
		ev.Offer.City != "Paris" ||
		ev.Offer.URL != "https://example.wd3.myworkdayjobs.com/Careers/job/Paris/Data-Engineer_R1" {
		t.Fatalf("unexpected normalized event: %+v", ev)
	}
	gotFields := map[string]string{}
	for _, f := range ev.Offer.Fields {
		gotFields[f.Name] = f.Value
	}
	wantFields := map[string]string{
		"Entreprise":  "Example",
		"Lieu":        "Paris, Lyon",
		"Publié le":   "2026-10-27",
		"Contrat":     "Full time",
		"Date limite": "2026-11-05",
		"Référence":   "R1",
	}
	for k, v := range wantFields {
		if gotFields[k] != v {
			t.Fatalf("field %q = %q, want %q", k, gotFields[k], v)
		}
	}

	minimal := JobDetail{Title: "Engineer", JobPostingID: "Engineer_R2", Posted: true}
	ev2, err := Normalize(defaultBoard(t), "/job/x/Engineer_R2", minimal)
	if err != nil {
		t.Fatalf("Normalize minimal: %v", err)
	}
	if ev2.Offer.Country != "N/A" || ev2.Offer.City != "N/A" || len(ev2.Offer.Fields) != 2 {
		t.Fatalf("unexpected minimal event: %+v", ev2.Offer)
	}
}

func TestPaginationStopsAtLimitAndTotal(t *testing.T) {
	full := make([]map[string]any, 20)
	for i := range full {
		full[i] = samplePosting("job-" + string(rune('a'+i)))
	}
	total40 := 40
	serve := servePages(&total40, full, full, full)
	var offsets []int
	client := &http.Client{
		Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			if r.Method == http.MethodPost {
				raw, _ := io.ReadAll(r.Body)
				r.Body = io.NopCloser(bytes.NewReader(raw))
				var body map[string]any
				_ = json.Unmarshal(raw, &body)
				offsets = append(offsets, int(body["offset"].(float64)))
			}
			return serve(r)
		}),
	}
	store := &fakeStore{seen: map[string]bool{}}
	if err := Collect(context.Background(), store, client, func(_ context.Context, _ offerevents.OfferEvent) error { return nil }, []Board{defaultBoard(t)}, 100, 0); err != nil {
		t.Fatalf("Collect: %v", err)
	}
	if !slices.Equal(offsets, []int{0, 20}) {
		t.Fatalf("offsets = %v, want [0 20]", offsets)
	}

	offsets = nil
	count := 0
	neverSeen := &neverSeenStore{}
	if err := Collect(context.Background(), neverSeen, client, func(_ context.Context, _ offerevents.OfferEvent) error { count++; return nil }, []Board{defaultBoard(t)}, 25, 0); err != nil {
		t.Fatalf("Collect limit 25: %v", err)
	}
	if count != 25 || !slices.Equal(offsets, []int{0, 20}) {
		t.Fatalf("count=%d offsets=%v", count, offsets)
	}
}

type neverSeenStore struct{}

func (neverSeenStore) Seen(_ context.Context, _ string) (bool, error) { return false, nil }
func (neverSeenStore) RecordPage(_ context.Context, _ []offerevents.OfferEvent, _ []string, _ string, _ int) error {
	return nil
}
func (neverSeenStore) RequireRecentResults(_ context.Context, _ string) error { return nil }

func TestBoardIsolationRemovedUnpostedAndBrokerFailure(t *testing.T) {
	// Failed board does not stop others.
	serve := servePages(nil, []map[string]any{samplePosting("job")})
	client := &http.Client{
		Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			if strings.HasPrefix(r.URL.Host, "broken.") {
				return jsonResponse(422, nil), nil
			}
			return serve(r)
		}),
	}
	broken := makeBoard(t, `{"url":"https://broken.wd1.myworkdayjobs.com/Careers","company":"Broken"}`)
	var published []string
	err := Collect(context.Background(), &fakeStore{seen: map[string]bool{}}, client, func(_ context.Context, ev offerevents.OfferEvent) error {
		published = append(published, ev.SourceOfferID)
		return nil
	}, []Board{broken, defaultBoard(t)}, 40, 0)
	var failErr *CollectionFailedError
	if !errors.As(err, &failErr) || !strings.Contains(err.Error(), "broken/Careers") {
		t.Fatalf("expected CollectionFailedError mentioning broken/Careers, got %v", err)
	}
	if !slices.Equal(published, []string{"example/Careers/job"}) {
		t.Fatalf("published = %v", published)
	}

	// Removed (404) and unposted jobs are skipped.
	serve2 := servePages(nil, []map[string]any{samplePosting("gone"), samplePosting("draft"), samplePosting("open")})
	client2 := &http.Client{
		Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			if strings.HasSuffix(r.URL.Path, "/gone") {
				return jsonResponse(404, map[string]any{"errorCode": "S21"}), nil
			}
			if strings.HasSuffix(r.URL.Path, "/draft") {
				return jsonResponse(200, sampleDetail("draft", false)), nil
			}
			return serve2(r)
		}),
	}
	published = nil
	if err := Collect(context.Background(), &fakeStore{seen: map[string]bool{}}, client2, func(_ context.Context, ev offerevents.OfferEvent) error {
		published = append(published, ev.SourceOfferID)
		return nil
	}, []Board{defaultBoard(t)}, 40, 0); err != nil {
		t.Fatalf("Collect removed/draft: %v", err)
	}
	if !slices.Equal(published, []string{"example/Careers/open"}) {
		t.Fatalf("published = %v", published)
	}

	// Detail identity mismatch fails the board.
	client3 := &http.Client{
		Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			if r.Method == http.MethodGet {
				return jsonResponse(200, sampleDetail("other", true)), nil
			}
			return servePages(nil, []map[string]any{samplePosting("listed")})(r)
		}),
	}
	err = Collect(context.Background(), &fakeStore{seen: map[string]bool{}}, client3, func(_ context.Context, _ offerevents.OfferEvent) error { return nil }, []Board{defaultBoard(t)}, 40, 0)
	if !errors.As(err, &failErr) {
		t.Fatalf("expected CollectionFailedError on mismatch, got %v", err)
	}

	// Broker failure stops the run immediately without touching second board.
	var hosts []string
	client4 := &http.Client{
		Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			hosts = append(hosts, r.URL.Host)
			return serve(r)
		}),
	}
	second := makeBoard(t, `{"url":"https://second.wd1.myworkdayjobs.com/Careers","company":"Second"}`)
	brokerErr := errors.New("broker down")
	err = Collect(context.Background(), &fakeStore{seen: map[string]bool{}}, client4, func(_ context.Context, _ offerevents.OfferEvent) error {
		return brokerErr
	}, []Board{defaultBoard(t), second}, 40, 0)
	if !errors.Is(err, brokerErr) {
		t.Fatalf("expected brokerErr, got %v", err)
	}
	if slices.Contains(hosts, "second.wd1.myworkdayjobs.com") {
		t.Fatalf("second board should not have been queried after broker failure: %v", hosts)
	}
}

func TestWorkdayCLI(t *testing.T) {
	tmp := t.TempDir()
	origWD, _ := os.Getwd()
	if err := os.Chdir(tmp); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = os.Chdir(origWD) }()

	t.Setenv("WORKDAY_BOARDS", "")
	t.Setenv("WORKDAY_LIMIT", "")

	// Missing/empty/[] boards fail with exit code 2 before connecting.
	for _, val := range []string{"", "[]"} {
		t.Setenv("WORKDAY_BOARDS", val)
		var stdout, stderr bytes.Buffer
		called := false
		code := runCLI(nil, &stdout, &stderr, cliDeps{
			runCollect: func(_ context.Context, _ []Board, _ int) error {
				called = true
				return nil
			},
		})
		if code != 2 || called || !strings.Contains(stderr.String(), "WORKDAY_BOARDS") {
			t.Fatalf("val=%q: code=%d called=%v stderr=%s", val, code, called, stderr.String())
		}
	}

	// Reads WORKDAY_BOARDS and WORKDAY_LIMIT from .env.
	t.Setenv("WORKDAY_BOARDS", "")
	_ = os.Unsetenv("WORKDAY_BOARDS")
	t.Setenv("WORKDAY_LIMIT", "")
	_ = os.Unsetenv("WORKDAY_LIMIT")
	envContent := "WORKDAY_LIMIT=5\nWORKDAY_BOARDS='[{\"url\":\"https://example.wd1.myworkdayjobs.com/Careers\",\"company\":\"Example\",\"searchText\":\"data\"}]'\n"
	if err := os.WriteFile(filepath.Join(tmp, ".env"), []byte(envContent), 0o600); err != nil {
		t.Fatal(err)
	}
	var gotBoards []Board
	var gotLimit int
	var stdout, stderr bytes.Buffer
	code := runCLI(nil, &stdout, &stderr, cliDeps{
		runCollect: func(_ context.Context, boards []Board, limit int) error {
			gotBoards = boards
			gotLimit = limit
			return nil
		},
	})
	if code != 0 || len(gotBoards) != 1 || gotBoards[0].Name() != "example/Careers" || gotBoards[0].SearchText != "data" || gotLimit != 5 {
		t.Fatalf("code=%d boards=%+v limit=%d stderr=%s", code, gotBoards, gotLimit, stderr.String())
	}
}

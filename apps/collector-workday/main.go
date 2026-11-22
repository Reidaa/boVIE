package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/Reidaa/boVIE/packages/clicommon"
	"github.com/Reidaa/boVIE/packages/collectorstore"
	"github.com/Reidaa/boVIE/packages/mysqlcommon"
	"github.com/Reidaa/boVIE/packages/natsclient"
	"github.com/Reidaa/boVIE/packages/offerevents"
	"github.com/spf13/pflag"
)

// PageSize is the maximum page size Workday accepts without returning HTTP 400.
const PageSize = 20

// CollectionFailedError indicates at least one Workday board failed while the others completed.
type CollectionFailedError struct {
	Failed []string
}

func (e *CollectionFailedError) Error() string {
	return "Workday boards failed: " + strings.Join(e.Failed, ", ")
}

// BoardError wraps per-board HTTP or response-shape errors so Collect can isolate them
// from broker or database failures.
type BoardError struct {
	Err error
}

func (e *BoardError) Error() string { return e.Err.Error() }
func (e *BoardError) Unwrap() error { return e.Err }

// HTTPStatusError represents a non-2xx HTTP response from Workday.
type HTTPStatusError struct {
	StatusCode int
}

func (e *HTTPStatusError) Error() string {
	return fmt.Sprintf("Workday API returned HTTP %d", e.StatusCode)
}

// Store abstracts collector persistence for testing.
type Store interface {
	Seen(ctx context.Context, sourceOfferID string) (bool, error)
	RecordPage(ctx context.Context, published []offerevents.OfferEvent, observed []string, scan string, offset int) error
	RequireRecentResults(ctx context.Context, scan string) error
}

// PublishFunc publishes one OfferEvent and waits for JetStream acknowledgment.
type PublishFunc func(ctx context.Context, event offerevents.OfferEvent) error

// LoadBoards parses the JSON list of boards from WORKDAY_BOARDS; it must not be empty.
func LoadBoards(text string) ([]Board, error) {
	if strings.TrimSpace(text) == "" {
		return nil, errors.New("WORKDAY_BOARDS must be a JSON list of at least one board")
	}
	var boards []Board
	if err := json.Unmarshal([]byte(text), &boards); err != nil {
		return nil, fmt.Errorf("WORKDAY_BOARDS: %w", err)
	}
	if len(boards) == 0 {
		return nil, errors.New("WORKDAY_BOARDS must be a JSON list of at least one board")
	}
	return boards, nil
}

// Normalize converts a Workday JobDetail into a version-1 OfferEvent.
func Normalize(board Board, externalPath string, job JobDetail) (offerevents.OfferEvent, error) {
	locations := make([]string, 0, 1+len(job.AdditionalLocations))
	if job.Location != nil && *job.Location != "" {
		locations = append(locations, *job.Location)
	}
	for _, loc := range job.AdditionalLocations {
		if loc != "" {
			locations = append(locations, loc)
		}
	}
	lieu := offerevents.TruncateRunes(strings.Join(locations, ", "), 1024)
	if lieu == "" {
		lieu = "N/A"
	}

	fields := []offerevents.DisplayField{
		offerevents.NewDisplayField("Entreprise", offerevents.TruncateRunes(board.Company, 1024)),
		offerevents.NewDisplayField("Lieu", lieu),
	}

	optional := []struct {
		name  string
		value *string
	}{
		{"Publié le", job.StartDate},
		{"Contrat", job.TimeType},
		{"Date limite", job.EndDate},
		{"Référence", job.JobReqID},
	}
	for _, item := range optional {
		if item.value != nil && *item.value != "" {
			fields = append(fields, offerevents.NewDisplayField(
				item.name,
				offerevents.TruncateRunes(*item.value, 1024),
			))
		}
	}

	country := "N/A"
	if job.JobRequisitionLocation != nil &&
		job.JobRequisitionLocation.Country != nil &&
		job.JobRequisitionLocation.Country.Alpha2Code != nil &&
		*job.JobRequisitionLocation.Country.Alpha2Code != "" {
		country = *job.JobRequisitionLocation.Country.Alpha2Code
	}
	city := "N/A"
	if job.Location != nil && *job.Location != "" {
		city = *job.Location
	}

	return offerevents.NewOfferEvent(
		offerevents.EventDiscovered,
		offerevents.SourceWorkday,
		fmt.Sprintf("%s/%s", board.Name(), job.JobPostingID),
		offerevents.OfferDetails{
			Title:        offerevents.TruncateRunes(strings.TrimSpace(job.Title), 256),
			Organization: board.Company,
			Country:      country,
			City:         city,
			URL:          fmt.Sprintf("%s/%s%s", board.Origin(), board.Site(), externalPath),
			Fields:       fields,
		},
	)
}

func scanHash(board Board, limit int) string {
	facets := board.AppliedFacets
	if facets == nil {
		facets = map[string][]string{}
	}
	raw, _ := json.Marshal([]any{board.APIURL(), board.SearchText, facets, limit})
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

func sleepWithContext(ctx context.Context, d time.Duration) error {
	if d <= 0 {
		return nil
	}
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

// CollectBoard scans a single Workday career site up to limit postings.
func CollectBoard(
	ctx context.Context,
	store Store,
	httpClient *http.Client,
	publish PublishFunc,
	board Board,
	limit int,
	delay time.Duration,
) error {
	scan := scanHash(board, limit)
	inspected := 0
	offset := 0
	var total *int

	facets := board.AppliedFacets
	if facets == nil {
		facets = map[string][]string{}
	}

	// Restart at offset 0 each run: the newest postings come first.
	for inspected < limit {
		if err := sleepWithContext(ctx, delay); err != nil {
			return err
		}
		reqBody, err := json.Marshal(map[string]any{
			"limit":         PageSize,
			"offset":        offset,
			"searchText":    board.SearchText,
			"appliedFacets": facets,
		})
		if err != nil {
			return &BoardError{Err: err}
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodPost, board.APIURL()+"/jobs", bytes.NewReader(reqBody))
		if err != nil {
			return &BoardError{Err: err}
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Accept", "application/json")

		resp, err := httpClient.Do(req)
		if err != nil {
			return &BoardError{Err: err}
		}
		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			status := resp.StatusCode
			_ = resp.Body.Close()
			return &BoardError{Err: &HTTPStatusError{StatusCode: status}}
		}
		var result SearchResponse
		err = json.NewDecoder(resp.Body).Decode(&result)
		_ = resp.Body.Close()
		if err != nil {
			return &BoardError{Err: err}
		}
		if result.Total < 0 {
			return &BoardError{Err: errors.New("workday returned negative total")}
		}
		for _, p := range result.JobPostings {
			if err := p.Validate(); err != nil {
				return &BoardError{Err: err}
			}
		}
		if total == nil {
			t := result.Total
			total = &t
		}

		postings := result.JobPostings
		if remaining := limit - inspected; len(postings) > remaining {
			postings = postings[:remaining]
		}
		inspected += len(postings)

		events := make([]offerevents.OfferEvent, 0, len(postings))
		observed := make([]string, len(postings))
		for i, posting := range postings {
			identity := fmt.Sprintf("%s/%s", board.Name(), posting.JobID())
			observed[i] = identity

			alreadySeen, err := store.Seen(ctx, identity)
			if err != nil {
				return err
			}
			if alreadySeen {
				continue
			}

			if err := sleepWithContext(ctx, delay); err != nil {
				return err
			}
			dReq, err := http.NewRequestWithContext(ctx, http.MethodGet, board.APIURL()+posting.ExternalPath, nil)
			if err != nil {
				return &BoardError{Err: err}
			}
			dReq.Header.Set("Accept", "application/json")
			dResp, err := httpClient.Do(dReq)
			if err != nil {
				return &BoardError{Err: err}
			}
			if dResp.StatusCode == http.StatusNotFound || dResp.StatusCode == http.StatusGone {
				_ = dResp.Body.Close()
				// The job was removed after the list showed it.
				slog.Warn("Workday job is gone; skipping it", "job_id", posting.JobID())
				continue
			}
			if dResp.StatusCode < 200 || dResp.StatusCode >= 300 {
				status := dResp.StatusCode
				_ = dResp.Body.Close()
				return &BoardError{Err: &HTTPStatusError{StatusCode: status}}
			}
			var detail DetailResponse
			err = json.NewDecoder(dResp.Body).Decode(&detail)
			_ = dResp.Body.Close()
			if err != nil {
				return &BoardError{Err: err}
			}
			job := detail.JobPostingInfo
			if job.JobPostingID != posting.JobID() {
				return &BoardError{Err: errors.New("workday detail identity does not match its posting")}
			}
			if !job.Posted {
				continue
			}
			event, err := Normalize(board, posting.ExternalPath, job)
			if err != nil {
				return &BoardError{Err: err}
			}
			events = append(events, event)
		}

		// Publish before recording: an unrecorded offer is published again next run.
		for _, event := range events {
			if err := publish(ctx, event); err != nil {
				return err
			}
		}
		if err := store.RecordPage(ctx, events, observed, scan, offset); err != nil {
			return err
		}
		for _, event := range events {
			slog.Info("New Workday offer", "title", event.Offer.Title, "organization", event.Offer.Organization)
		}

		offset += len(result.JobPostings)
		// Workday serves the first page again past the end, so stop at `total`.
		if len(result.JobPostings) < PageSize || offset >= *total {
			break
		}
	}
	return store.RequireRecentResults(ctx, scan)
}

// Collect scans every configured board, isolating per-board HTTP, response-shape, and
// silent-source errors. Broker and database errors abort the run immediately.
func Collect(
	ctx context.Context,
	store Store,
	httpClient *http.Client,
	publish PublishFunc,
	boards []Board,
	limit int,
	delay time.Duration,
) error {
	if limit <= 0 {
		limit = 40
	}
	var failed []string
	for _, board := range boards {
		err := CollectBoard(ctx, store, httpClient, publish, board, limit, delay)
		if err == nil {
			continue
		}
		var boardErr *BoardError
		if errors.As(err, &boardErr) || errors.Is(err, collectorstore.ErrSourceSilent) {
			slog.Error("Workday board failed", "board", board.Name(), "error", err)
			failed = append(failed, board.Name())
			continue
		}
		// Broker and database errors affect every board, so stop the run at once.
		return err
	}
	if len(failed) > 0 {
		return &CollectionFailedError{Failed: failed}
	}
	return nil
}

type cliDeps struct {
	runCollect func(ctx context.Context, boards []Board, limit int) error
}

func defaultDeps() cliDeps {
	return cliDeps{
		runCollect: func(ctx context.Context, boards []Board, limit int) error {
			cfg, err := mysqlcommon.LoadEnv()
			if err != nil {
				return err
			}
			db, err := mysqlcommon.OpenDB(cfg)
			if err != nil {
				return err
			}
			defer func() { _ = db.Close() }()

			pub, err := natsclient.NewPublisher(ctx, 10*time.Second)
			if err != nil {
				return err
			}
			defer pub.Close()

			httpClient := &http.Client{Timeout: 15 * time.Second}
			return Collect(ctx, collectorstore.New(db), httpClient, pub.Publish, boards, limit, time.Second)
		},
	}
}

func runCLI(args []string, stdout, stderr io.Writer, deps cliDeps) int {
	clicommon.LoadDotEnv()

	defaultBoards := os.Getenv("WORKDAY_BOARDS")
	defaultLimit := 40
	if raw := strings.TrimSpace(os.Getenv("WORKDAY_LIMIT")); raw != "" {
		v, err := strconv.Atoi(raw)
		if err != nil || v < 1 {
			fmt.Fprintf(stderr, "Error: invalid WORKDAY_LIMIT: %q\n", raw)
			return 2
		}
		defaultLimit = v
	}

	var (
		boardsJSON string
		limit      int
	)

	flags := pflag.NewFlagSet("collector-workday", pflag.ContinueOnError)
	flags.SetOutput(stderr)
	flags.StringVar(&boardsJSON, "boards", defaultBoards, "Required JSON list of boards to collect.")
	flags.IntVar(&limit, "limit", defaultLimit, "Maximum job postings to inspect per board.")
	flags.Usage = func() {
		fmt.Fprintf(stderr, "Usage: collector-workday [OPTIONS]\n\nDiscover new jobs on the configured Workday career sites.\n\nOptions:\n%s", flags.FlagUsages())
	}

	if err := flags.Parse(args); err != nil {
		if err == pflag.ErrHelp {
			return 0
		}
		return 2
	}
	if limit < 1 {
		fmt.Fprintln(stderr, "Error: --limit must be >= 1")
		return 2
	}

	slog.SetDefault(clicommon.NewLogger(stdout, stderr, false))

	// Fail on configuration before connecting to MySQL or NATS.
	boards, err := LoadBoards(boardsJSON)
	if err != nil {
		fmt.Fprintf(stderr, "Error: Invalid value for WORKDAY_BOARDS: %v\n", err)
		return 2
	}

	if err := deps.runCollect(context.Background(), boards, limit); err != nil {
		slog.Error("Workday collection failed", "error", err)
		fmt.Fprintln(stderr, "Error: Workday collection failed; retry will replay discovery")
		return 1
	}
	return 0
}

func main() {
	os.Exit(runCLI(os.Args[1:], os.Stdout, os.Stderr, defaultDeps()))
}

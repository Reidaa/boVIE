package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"github.com/Reidaa/boVIE/packages/clicommon"
	"github.com/Reidaa/boVIE/packages/collectorstore"
	"github.com/Reidaa/boVIE/packages/mysqlcommon"
	"github.com/Reidaa/boVIE/packages/natsclient"
	"github.com/Reidaa/boVIE/packages/offerevents"
	"github.com/spf13/pflag"
)

// APIURL is the Welcome to the Jungle public API base URL.
const APIURL = "https://api.welcometothejungle.com"

var placeholderTitle = regexp.MustCompile(`^\$\d+$`)

// HTTPStatusError represents a non-2xx HTTP response from WTTJ.
type HTTPStatusError struct {
	StatusCode int
}

func (e *HTTPStatusError) Error() string {
	return fmt.Sprintf("WTTJ API returned HTTP %d", e.StatusCode)
}

// Store abstracts collector persistence for testing.
type Store interface {
	Seen(ctx context.Context, sourceOfferID string) (bool, error)
	RecordPage(ctx context.Context, published []offerevents.OfferEvent, observed []string, scan string, offset int) error
	RequireRecentResults(ctx context.Context, scan string) error
}

// PublishFunc publishes one OfferEvent and waits for JetStream acknowledgment.
type PublishFunc func(ctx context.Context, event offerevents.OfferEvent) error

// CollectOptions configures a WTTJ collection run.
type CollectOptions struct {
	Query     string
	Limit     int
	MaxPages  int
	Countries []string
	Contracts []string
}

// JobTitle returns the offer title, or ("", false) when WTTJ gives no usable title.
// WTTJ sometimes returns a "$1" placeholder as the name. The slug then holds the title
// before the first "_", e.g. "network-security-specialist_milan_ND_wZVZKeo".
func JobTitle(job JobDetail) (string, bool) {
	title := strings.TrimSpace(job.Name)
	if !placeholderTitle.MatchString(title) {
		return offerevents.TruncateRunes(title, 256), true
	}
	slugPrefix, _, _ := strings.Cut(job.Slug, "_")
	title = strings.TrimSpace(strings.ReplaceAll(slugPrefix, "-", " "))
	if title == "" {
		return "", false
	}
	slog.Warn("WTTJ offer has placeholder title; using its slug",
		"reference", job.WTTJReference,
		"name", job.Name,
	)
	first, size := utf8.DecodeRuneInString(title)
	capitalized := string(unicode.ToUpper(first)) + title[size:]
	return offerevents.TruncateRunes(capitalized, 256), true
}

// Normalize converts a WTTJ JobDetail into a version-1 OfferEvent.
func Normalize(job JobDetail, title string) (offerevents.OfferEvent, error) {
	officeParts := make([]string, len(job.Offices))
	for i, office := range job.Offices {
		city := "N/A"
		if office.City != nil && *office.City != "" {
			city = *office.City
		}
		officeParts[i] = fmt.Sprintf("%s (%s)", city, office.CountryCode)
	}
	lieu := offerevents.TruncateRunes(strings.Join(officeParts, ", "), 1024)
	if lieu == "" {
		lieu = "N/A"
	}

	fields := []offerevents.DisplayField{
		offerevents.NewDisplayField("Entreprise", offerevents.TruncateRunes(job.Organization.Name, 1024)),
		offerevents.NewDisplayField("Lieu", lieu),
		offerevents.NewDisplayField("Publié le", offerevents.TruncateRunes(job.PublishedAt, 1024)),
		offerevents.NewDisplayField("Contrat", job.ContractType),
	}

	if job.SalaryMin != nil || job.SalaryMax != nil {
		minStr := "?"
		if job.SalaryMin != nil && *job.SalaryMin != 0 {
			minStr = strconv.FormatFloat(*job.SalaryMin, 'f', -1, 64)
		}
		maxStr := "?"
		if job.SalaryMax != nil && *job.SalaryMax != 0 {
			maxStr = strconv.FormatFloat(*job.SalaryMax, 'f', -1, 64)
		}
		currency := ""
		if job.SalaryCurrency != nil {
			currency = *job.SalaryCurrency
		}
		period := "N/A"
		if job.SalaryPeriod != nil && *job.SalaryPeriod != "" {
			period = *job.SalaryPeriod
		}
		fields = append(fields, offerevents.NewDisplayField(
			"Salaire",
			fmt.Sprintf("%s \u2013 %s %s / %s", minStr, maxStr, currency, period),
		))
	}
	if job.StartDate != nil && *job.StartDate != "" {
		fields = append(fields, offerevents.NewDisplayField("Début", offerevents.TruncateRunes(*job.StartDate, 1024)))
	}
	if job.ApplyURL != nil && (strings.HasPrefix(*job.ApplyURL, "https://") || strings.HasPrefix(*job.ApplyURL, "http://")) {
		fields = append(fields, offerevents.NewDisplayField("Candidature", offerevents.TruncateRunes(*job.ApplyURL, 1024)))
	}

	country := "N/A"
	city := "N/A"
	if len(job.Offices) > 0 {
		country = job.Offices[0].CountryCode
		if job.Offices[0].City != nil && *job.Offices[0].City != "" {
			city = *job.Offices[0].City
		}
	}

	offerURL := fmt.Sprintf(
		"https://www.welcometothejungle.com/fr/companies/%s/jobs/%s",
		url.PathEscape(job.Organization.Slug),
		url.PathEscape(job.Slug),
	)

	return offerevents.NewOfferEvent(
		offerevents.EventDiscovered,
		offerevents.SourceWTTJ,
		job.WTTJReference,
		offerevents.OfferDetails{
			Title:        title,
			Organization: job.Organization.Name,
			Country:      country,
			City:         city,
			URL:          offerURL,
			Fields:       fields,
		},
	)
}

func scanHash(opts CollectOptions) string {
	countries := opts.Countries
	if countries == nil {
		countries = []string{}
	}
	contracts := opts.Contracts
	if contracts == nil {
		contracts = []string{}
	}
	raw, _ := json.Marshal([]any{opts.Query, countries, contracts, opts.Limit, opts.MaxPages})
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

// Collect paginates WTTJ public search, fetches unseen job details, publishes, and records each page.
func Collect(
	ctx context.Context,
	store Store,
	baseURL string,
	httpClient *http.Client,
	publish PublishFunc,
	opts CollectOptions,
) error {
	if opts.Limit <= 0 {
		opts.Limit = 50
	}
	if opts.MaxPages <= 0 {
		opts.MaxPages = 5
	}
	scan := scanHash(opts)
	inspected := 0
	base := strings.TrimRight(baseURL, "/")

	// Restart at page 1 because ranked search results can move between invocations.
	for page := 1; page <= opts.MaxPages; page++ {
		params := url.Values{}
		params.Set("job_title", opts.Query)
		params.Set("page", strconv.Itoa(page))
		searchURL := fmt.Sprintf("%s/api/v3/public/jobs?%s", base, params.Encode())

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, searchURL, nil)
		if err != nil {
			return err
		}
		resp, err := httpClient.Do(req)
		if err != nil {
			return err
		}
		var result SearchResponse
		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			_ = resp.Body.Close()
			return &HTTPStatusError{StatusCode: resp.StatusCode}
		}
		err = json.NewDecoder(resp.Body).Decode(&result)
		_ = resp.Body.Close()
		if err != nil {
			return err
		}
		if result.Metadata.Page < 1 || result.Metadata.PageCount < 0 {
			return errors.New("WTTJ returned invalid pagination metadata")
		}
		if result.Metadata.Page != page {
			return errors.New("WTTJ returned an unexpected page number")
		}

		remaining := opts.Limit - inspected
		hits := result.Data
		if len(hits) > remaining {
			hits = hits[:remaining]
		}

		events := make([]offerevents.OfferEvent, 0, len(hits))
		observed := make([]string, len(hits))
		for i, hit := range hits {
			observed[i] = hit.Reference
			inspected++
			if len(opts.Contracts) > 0 && !slices.Contains(opts.Contracts, hit.ContractType) {
				continue
			}
			alreadySeen, err := store.Seen(ctx, hit.Reference)
			if err != nil {
				return err
			}
			if alreadySeen {
				continue
			}

			detailURL := fmt.Sprintf(
				"%s/api/v3/organizations/%s/jobs/%s",
				base,
				url.PathEscape(hit.Organization.Slug),
				url.PathEscape(hit.Slug),
			)
			dReq, err := http.NewRequestWithContext(ctx, http.MethodGet, detailURL, nil)
			if err != nil {
				return err
			}
			dResp, err := httpClient.Do(dReq)
			if err != nil {
				return err
			}
			if dResp.StatusCode == http.StatusNotFound || dResp.StatusCode == http.StatusGone {
				_ = dResp.Body.Close()
				slog.Warn("WTTJ offer is gone; skipping it", "reference", hit.Reference)
				continue
			}
			if dResp.StatusCode < 200 || dResp.StatusCode >= 300 {
				status := dResp.StatusCode
				_ = dResp.Body.Close()
				return &HTTPStatusError{StatusCode: status}
			}
			var detail DetailResponse
			err = json.NewDecoder(dResp.Body).Decode(&detail)
			_ = dResp.Body.Close()
			if err != nil {
				return err
			}
			job := detail.Job
			if job.WTTJReference != hit.Reference {
				return errors.New("WTTJ detail identity does not match its search result")
			}
			if job.Status != "published" {
				continue
			}
			if len(opts.Contracts) > 0 && !slices.Contains(opts.Contracts, job.ContractType) {
				continue
			}
			if len(opts.Countries) > 0 && !matchesCountry(job.Offices, opts.Countries) {
				continue
			}
			title, ok := JobTitle(job)
			if !ok {
				slog.Warn("WTTJ offer has no usable title; skipping it", "reference", hit.Reference)
				continue
			}
			event, err := Normalize(job, title)
			if err != nil {
				return err
			}
			events = append(events, event)
		}

		// Publish before recording: an unrecorded offer is published again next run.
		for _, event := range events {
			if err := publish(ctx, event); err != nil {
				return err
			}
		}
		if err := store.RecordPage(ctx, events, observed, scan, page); err != nil {
			return err
		}
		for _, event := range events {
			slog.Info("New WTTJ offer", "title", event.Offer.Title, "organization", event.Offer.Organization)
		}

		if inspected >= opts.Limit || len(result.Data) == 0 || page >= result.Metadata.PageCount {
			break
		}
	}
	return store.RequireRecentResults(ctx, scan)
}

func matchesCountry(offices []Office, countries []string) bool {
	for _, office := range offices {
		if slices.Contains(countries, office.CountryCode) {
			return true
		}
	}
	return false
}

type cliDeps struct {
	runCollect func(ctx context.Context, opts CollectOptions) error
}

func defaultDeps() cliDeps {
	return cliDeps{
		runCollect: func(ctx context.Context, opts CollectOptions) error {
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
			return Collect(ctx, collectorstore.New(db), APIURL, httpClient, pub.Publish, opts)
		},
	}
}

func runCLI(args []string, stdout, stderr io.Writer, deps cliDeps) int {
	clicommon.LoadDotEnv()

	defaultQuery := os.Getenv("WTTJ_QUERY")
	defaultLimit := 50
	if raw := strings.TrimSpace(os.Getenv("WTTJ_LIMIT")); raw != "" {
		v, err := strconv.Atoi(raw)
		if err != nil || v < 1 {
			fmt.Fprintf(stderr, "Error: invalid WTTJ_LIMIT: %q\n", raw)
			return 2
		}
		defaultLimit = v
	}
	defaultMaxPages := 5
	if raw := strings.TrimSpace(os.Getenv("WTTJ_MAX_PAGES")); raw != "" {
		v, err := strconv.Atoi(raw)
		if err != nil || v < 1 {
			fmt.Fprintf(stderr, "Error: invalid WTTJ_MAX_PAGES: %q\n", raw)
			return 2
		}
		defaultMaxPages = v
	}

	var (
		query     string
		limit     int
		maxPages  int
		countries []string
		contracts []string
	)

	flags := pflag.NewFlagSet("collector-wttj", pflag.ContinueOnError)
	flags.SetOutput(stderr)
	flags.StringVar(&query, "query", defaultQuery, "Optional job title search; empty includes all titles.")
	flags.IntVar(&limit, "limit", defaultLimit, "Maximum search results to inspect.")
	flags.IntVar(&maxPages, "max-pages", defaultMaxPages, "Maximum search pages to inspect.")
	flags.StringArrayVar(&countries, "country", nil, "ISO country code, e.g. CA.")
	flags.StringArrayVar(&contracts, "contract", nil, "Optional WTTJ contract type (repeatable), e.g. full_time or internship.")
	flags.Usage = func() {
		fmt.Fprintf(stderr, "Usage: collector-wttj [OPTIONS]\n\nDiscover published jobs of any contract type on Welcome to the Jungle.\n\nOptions:\n%s", flags.FlagUsages())
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
	if maxPages < 1 {
		fmt.Fprintln(stderr, "Error: --max-pages must be >= 1")
		return 2
	}

	if !flags.Changed("contract") {
		contracts = strings.Fields(os.Getenv("WTTJ_CONTRACTS"))
	}

	normCountries := make([]string, len(countries))
	for i, c := range countries {
		normCountries[i] = strings.ToUpper(c)
	}
	normContracts := make([]string, len(contracts))
	for i, c := range contracts {
		normContracts[i] = strings.ToLower(c)
	}

	slog.SetDefault(clicommon.NewLogger(stdout, stderr, false))

	opts := CollectOptions{
		Query:     query,
		Limit:     limit,
		MaxPages:  maxPages,
		Countries: normCountries,
		Contracts: normContracts,
	}
	if err := deps.runCollect(context.Background(), opts); err != nil {
		slog.Error("WTTJ collection failed", "error", err)
		fmt.Fprintln(stderr, "Error: WTTJ collection failed; retry will replay discovery")
		return 1
	}
	return 0
}

func main() {
	os.Exit(runCLI(os.Args[1:], os.Stdout, os.Stderr, defaultDeps()))
}

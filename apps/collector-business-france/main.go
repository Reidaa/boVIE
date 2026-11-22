package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/Reidaa/boVIE/apps/collector-business-france/models"
	"github.com/Reidaa/boVIE/packages/clicommon"
	"github.com/Reidaa/boVIE/packages/collectorstore"
	"github.com/Reidaa/boVIE/packages/mysqlcommon"
	"github.com/Reidaa/boVIE/packages/natsclient"
	"github.com/Reidaa/boVIE/packages/offerevents"
	"github.com/spf13/pflag"
)

const (
	// Version is the CLI version printed by --version.
	Version = "0.4.0"
	// DefaultOfferLimit bounds search results inspected per run.
	DefaultOfferLimit = 25
)

// Store abstracts collector persistence for testing.
type Store interface {
	Seen(ctx context.Context, sourceOfferID string) (bool, error)
	RecordPage(ctx context.Context, published []offerevents.OfferEvent, observed []string, scan string, offset int) error
	RequireRecentResults(ctx context.Context, scan string) error
}

// OfferSource abstracts Business France API calls for testing.
type OfferSource interface {
	SearchID(ctx context.Context, params models.SearchParameters) ([]int, error)
	GetFromID(ctx context.Context, offerID int) (*models.Job, error)
}

// PublishFunc publishes one OfferEvent and waits for JetStream acknowledgment.
type PublishFunc func(ctx context.Context, event offerevents.OfferEvent) error

// Normalize converts a Business France Job into a version-1 OfferEvent.
func Normalize(job models.Job) (offerevents.OfferEvent, error) {
	fields, err := DisplayFields(job)
	if err != nil {
		return offerevents.OfferEvent{}, err
	}
	city := job.CityAffectation
	if job.CityName != nil && *job.CityName != "" {
		city = *job.CityName
	}
	return offerevents.NewOfferEvent(
		offerevents.EventDiscovered,
		offerevents.SourceBusinessFrance,
		strconv.Itoa(job.ID),
		offerevents.OfferDetails{
			Title:        offerevents.TruncateRunes(job.MissionTitle, 256),
			Organization: job.OrganizationName,
			Country:      job.CountryName,
			City:         city,
			URL:          fmt.Sprintf("https://mon-vie-via.businessfrance.fr/offres/%d", job.ID),
			Fields:       fields,
		},
	)
}

func scanHash(params models.SearchParameters) string {
	// Hash camelCase API keys in sorted order so struct renames do not create a new checkpoint.
	raw, _ := json.Marshal(params.Normalized())
	var m map[string]any
	_ = json.Unmarshal(raw, &m)
	canonical, _ := json.Marshal(m)
	sum := sha256.Sum256(canonical)
	return hex.EncodeToString(sum[:])
}

// Task collects Business France offers page by page, publishing before recording each page.
func Task(
	ctx context.Context,
	params models.SearchParameters,
	store Store,
	source OfferSource,
	publish PublishFunc,
	pageSize int,
) error {
	if pageSize <= 0 {
		pageSize = 25
	}
	scan := scanHash(params)
	offset := 0
	// Replaying from zero is intentional: offset-based results can move between runs.
	for offset < params.Limit {
		size := min(pageSize, params.Limit-offset)
		pageParams := params.Normalized()
		pageParams.Skip = offset
		pageParams.Limit = size

		ids, err := source.SearchID(ctx, pageParams)
		if err != nil {
			return err
		}

		events := make([]offerevents.OfferEvent, 0, len(ids))
		observed := make([]string, len(ids))
		for i, id := range ids {
			idStr := strconv.Itoa(id)
			observed[i] = idStr
			alreadySeen, err := store.Seen(ctx, idStr)
			if err != nil {
				return err
			}
			if alreadySeen {
				continue
			}
			job, err := source.GetFromID(ctx, id)
			if err != nil {
				return err
			}
			if job == nil {
				continue
			}
			event, err := Normalize(*job)
			if err != nil {
				return err
			}
			events = append(events, event)
		}
		offset += len(ids)

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
			slog.Info("New offer",
				"title", event.Offer.Title,
				"country", event.Offer.Country,
				"organization", event.Offer.Organization,
			)
		}
		if len(ids) < size {
			break
		}
	}
	return store.RequireRecentResults(ctx, scan)
}

type cliDeps struct {
	runTask func(ctx context.Context, params models.SearchParameters) error
}

func defaultDeps() cliDeps {
	return cliDeps{
		runTask: func(ctx context.Context, params models.SearchParameters) error {
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

			return Task(ctx, params, collectorstore.New(db), NewAPIClient(), pub.Publish, 25)
		},
	}
}

func splitCommaEnv(raw string) []string {
	if strings.TrimSpace(raw) == "" {
		return nil
	}
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		trimmed := strings.TrimSpace(p)
		if trimmed != "" {
			out = append(out, trimmed)
		}
	}
	return out
}

func runCLI(args []string, stdout, stderr io.Writer, deps cliDeps) int {
	clicommon.LoadDotEnv()

	defaultDebug := strings.EqualFold(os.Getenv("BUSINESS_FRANCE_DEBUG"), "true") || os.Getenv("BUSINESS_FRANCE_DEBUG") == "1"
	defaultLimit := DefaultOfferLimit
	if envLimit := strings.TrimSpace(os.Getenv("BUSINESS_FRANCE_LIMIT")); envLimit != "" {
		parsed, err := strconv.Atoi(envLimit)
		if err != nil || parsed < 1 {
			fmt.Fprintf(stderr, "Error: invalid BUSINESS_FRANCE_LIMIT: %q\n", envLimit)
			return 2
		}
		defaultLimit = parsed
	}

	var (
		debug           bool
		limit           int
		geozones        []string
		countries       []string
		specializations []string
		showVersion     bool
	)

	flags := pflag.NewFlagSet("collector-business-france", pflag.ContinueOnError)
	flags.SetOutput(stderr)
	flags.BoolVar(&debug, "debug", defaultDebug, "Enable debug logging")
	flags.IntVar(&limit, "limit", defaultLimit, "Maximum search results to inspect")
	flags.StringArrayVarP(&geozones, "geozone", "g", nil, "Regions to filter on")
	flags.StringArrayVarP(&countries, "country", "c", nil, "Countries to filter on")
	flags.StringArrayVarP(&specializations, "specialization", "s", nil, "Specializations to filter on")
	flags.BoolVar(&showVersion, "version", false, "Show the version and exit")
	flags.Usage = func() {
		fmt.Fprintf(stderr, "Usage: collector-business-france [OPTIONS]\n\nDiscover VIE/VIA opportunities from Business France.\n\nOptions:\n%s", flags.FlagUsages())
	}

	if err := flags.Parse(args); err != nil {
		if err == pflag.ErrHelp {
			return 0
		}
		return 2
	}
	if showVersion {
		fmt.Fprintf(stdout, "Bovie %s\n", Version)
		return 0
	}
	if limit < 1 {
		fmt.Fprintf(stderr, "Error: --limit must be >= 1\n")
		return 2
	}

	if !flags.Changed("geozone") {
		geozones = splitCommaEnv(os.Getenv("BUSINESS_FRANCE_REGION"))
	}
	if !flags.Changed("country") {
		countries = splitCommaEnv(os.Getenv("BUSINESS_FRANCE_COUNTRY"))
	}
	if !flags.Changed("specialization") {
		specializations = splitCommaEnv(os.Getenv("BUSINESS_FRANCE_SPECIALIZATION"))
	}

	slog.SetDefault(clicommon.NewLogger(stdout, stderr, debug))

	config, err := ConfigFromParams(limit, geozones, specializations, countries)
	if err != nil {
		fmt.Fprintf(stderr, "Error: %v\n", err)
		return 2
	}

	params := models.DefaultSearchParameters()
	params.Limit = config.Search.Limit
	params.SpecializationsIDs = config.Search.Specializations
	params.CountriesIDs = config.Search.Countries

	slog.Debug("Parsed search configuration",
		"limit", limit,
		"geozones", geozones,
		"specializations", specializations,
		"countries", countries,
	)

	slog.Info("Starting ...")
	if err := deps.runTask(context.Background(), params); err != nil {
		slog.Error("Business France collection failed", "error", err)
		return 1
	}
	slog.Info("Done ...")
	return 0
}

func main() {
	os.Exit(runCLI(os.Args[1:], os.Stdout, os.Stderr, defaultDeps()))
}
